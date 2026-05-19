"""
Smart Cart 360 -- Comparacao: Association Rules vs Naive Bayes (Etapa C)
=========================================================================

Script que roda os DOIS algoritmos lado a lado sobre os mesmos dados
de teste e compara as metricas. Nenhum algoritmo e substituido --
ambos coexistem para fins de analise comparativa no TCC.

Algoritmos comparados:
    1. Association Rules + Grafo (recommendations.py)
       Baseado em co-ocorrencia/confidence (Negre, 2015, sec. 3.5.2)
       combinado com grafo de localizacao.

    2. Naive Bayes + Grafo (naive_bayes_recommendations.py)
       Baseado no Teorema de Bayes com suposicao naive de independencia
       (Domingos & Pazzani, 1997), combinado com grafo de localizacao.

A comparacao usa os mesmos dados de teste (mesmas cestas, mesmo split,
mesma seed) para garantir que a unica variavel e o algoritmo.

Uso:
    python scripts/compare_algorithms.py
    python scripts/compare_algorithms.py --num-tests 80 --sim-people 300
    python scripts/compare_algorithms.py --remove-last 1 2 3

Autores: [Seu nome aqui]
Projeto: Smart Cart 360 -- TCC Insper 2026
"""

import argparse
import csv
import json
import math
import random
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os

os.environ.setdefault(
    "SMART_CART_DB_PATH",
    str(ROOT / "servidor_central" / "smart_cart.db"),
)

from servidor_central.schemas import (
    CartResponse,
    CartItemResponse,
    PromotionResponse,
)

# Algoritmo 1: Association Rules (principal)
from servidor_central.algorithms.recommendations import (
    generate_recommendations as gen_rec_association,
)

# Algoritmo 2: Naive Bayes (alternativo)
from servidor_central.algorithms.naive_bayes_recommendations import (
    generate_recommendations_naive_bayes as gen_rec_naive_bayes,
    get_trained_model,
    NaiveBayesModel,
)

from servidor_central.algorithms.location_graph import rebuild_location_graph

from mock_supermercado.simulation.layout import AISLE_GAP_METERS, SUPERMARKET_LAYOUT
from mock_supermercado.simulation.personas import PERSONA_PROPORTIONS, PERSONAS
from mock_supermercado.simulation.purchase_simulator import (
    populate_simulated_purchases,
)

from scripts.populate_purchase_history import (
    load_catalog,
    generate_all_purchases,
    save_purchases,
    CATALOG_PATH,
    DB_PATH,
)

PROMOTIONS_PATH = ROOT / "mock_supermercado" / "promotions.csv"


def load_promotions():
    promos = []
    with open(PROMOTIONS_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            promos.append(
                PromotionResponse(
                    id=row["id"], title=row["title"],
                    description=row["description"],
                    product_barcode=row["product_barcode"],
                    discount_type=row["discount_type"],
                    discount_value=float(row["discount_value"]),
                    aisle=row["aisle"] if row["aisle"] else None,
                )
            )
    return promos


def dcg(relevances, k):
    score = 0.0
    for i, rel in enumerate(relevances[:k]):
        score += rel / math.log2(i + 2)
    return score


def ndcg(relevances, k):
    actual = dcg(relevances, k)
    ideal = dcg(sorted(relevances, reverse=True), k)
    return actual / ideal if ideal > 0 else 0.0


def get_real_scan_sequences(conn, max_carts=500):
    cart_ids = conn.execute(
        "SELECT DISTINCT cart_id FROM cart_interactions ORDER BY cart_id LIMIT ?",
        (max_carts,),
    ).fetchall()
    sequences = []
    for (cart_id,) in cart_ids:
        rows = conn.execute(
            "SELECT barcode, payload_json FROM cart_interactions "
            "WHERE cart_id = ? AND event_type = 'item_added' ORDER BY created_at ASC",
            (cart_id,),
        ).fetchall()
        if len(rows) < 3:
            continue
        persona = "unknown"
        if rows[0][1]:
            try:
                persona = json.loads(rows[0][1]).get("persona", "unknown")
            except (json.JSONDecodeError, AttributeError):
                pass
        barcodes = [r[0] for r in rows]
        sequences.append((persona, barcodes))
    return sequences


def evaluate_single_test(rec_barcodes, gt_barcodes, promo_categories, catalog_map, gt_products):
    """Calcula todas as metricas para um unico teste."""
    metrics = {}

    for k in [1, 5, 10, 20]:
        top_k = set(rec_barcodes[:k])
        hits_k = gt_barcodes & top_k
        metrics["p@%d" % k] = len(hits_k) / k if k else 0
        metrics["r@%d" % k] = len(hits_k) / len(gt_barcodes) if gt_barcodes else 0
        metrics["hr@%d" % k] = 1.0 if hits_k else 0.0

    # F1 @20
    p20 = metrics["p@20"]
    r20 = metrics["r@20"]
    metrics["f1@20"] = 2 * p20 * r20 / (p20 + r20) if (p20 + r20) > 0 else 0

    # MRR
    mrr = 0.0
    for rank, bc in enumerate(rec_barcodes, 1):
        if bc in gt_barcodes:
            mrr = 1.0 / rank
            break
    metrics["mrr"] = mrr

    # NDCG@20
    rels = [1.0 if bc in gt_barcodes else 0.0 for bc in rec_barcodes[:20]]
    metrics["ndcg@20"] = ndcg(rels, 20)

    # Category recall
    gt_categories = set()
    for p in gt_products:
        cat = catalog_map.get(p["barcode"], {}).get("category")
        if cat:
            gt_categories.add(cat)
    rec_cats = set()
    for bc in rec_barcodes[:20]:
        c = promo_categories.get(bc)
        if c:
            rec_cats.add(c)
    cat_h = len(gt_categories & rec_cats)
    cat_t = len(gt_categories) if gt_categories else 1
    metrics["cat_recall"] = cat_h / cat_t if cat_t > 0 else 0

    return metrics


def run_comparison(
    sim_people, history_purchases, remove_last_counts, num_tests,
    promos, catalog, seed,
):
    promo_barcodes = {p.product_barcode for p in promos}
    catalog_map = {p["barcode"]: p for p in catalog}
    promo_categories = {}
    for p in promos:
        bc = p.product_barcode
        if bc and bc in catalog_map:
            cat = catalog_map[bc].get("category")
            if cat:
                promo_categories[bc] = cat
    now = datetime.now(timezone.utc)

    # --- Popular ---
    print("  Populando %d carrinhos simulados..." % sim_people)
    populate_simulated_purchases(
        people_count=sim_people, supermarket_layout=SUPERMARKET_LAYOUT,
        personas=PERSONAS, persona_proportions=PERSONA_PROPORTIONS,
        seed=seed, clear_existing_data=True, aisle_gap_m=AISLE_GAP_METERS,
    )

    print("  Populando %d compras no historico..." % history_purchases)
    cat_data = load_catalog(CATALOG_PATH)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("DELETE FROM purchase_items")
    conn.execute("DELETE FROM purchase_history")
    conn.commit()
    purchases = generate_all_purchases(cat_data, history_purchases)
    save_purchases(conn, purchases)

    print("  Buscando sequencias reais...")
    conn2 = sqlite3.connect(str(DB_PATH))
    conn2.row_factory = sqlite3.Row
    real_sequences = get_real_scan_sequences(conn2, max_carts=500)
    conn2.close()
    conn.close()
    print("  Encontradas %d sequencias" % len(real_sequences))

    print("  Reconstruindo grafo...")
    graph = None
    try:
        graph = rebuild_location_graph()
        print("  Grafo: %d nos, %d arestas" % (
            len(graph.get("nodes", [])), len(graph.get("links", []))))
    except Exception as e:
        print("  Aviso: grafo nao disponivel (%s)" % str(e))

    print("  Treinando modelo Naive Bayes...")
    nb_model = get_trained_model(force_retrain=True)
    print("  Modelo NB: %d produtos, %d transacoes, %d pares de co-ocorrencia" % (
        nb_model.n_products, nb_model.n_transactions, len(nb_model.likelihoods)))

    rng = random.Random(seed + 7777)
    results = []

    for remove_n in remove_last_counts:
        # Metricas separadas por algoritmo
        algo_metrics = {
            "association_rules": defaultdict(list),
            "naive_bayes": defaultdict(list),
        }

        test_count = 0
        available = [(p, seq) for p, seq in real_sequences
                     if p != "Quer Tudo" and len(seq) > remove_n + 1]

        for persona_name, sequence in available:
            if test_count >= num_tests:
                break

            seq_products = [
                {"barcode": bc, "name": catalog_map.get(bc, {}).get("name", bc)}
                for bc in sequence
            ]

            if len(seq_products) <= remove_n:
                continue

            cart_products = seq_products[:-remove_n]
            gt_products = seq_products[-remove_n:]
            gt_barcodes = {p["barcode"] for p in gt_products} & promo_barcodes
            if not gt_barcodes:
                continue

            test_count += 1

            # Montar carrinho (igual pra ambos)
            cart_items = []
            for i, p in enumerate(cart_products):
                info = catalog_map.get(p["barcode"], {})
                cart_items.append(CartItemResponse(
                    item_id=i + 1, barcode=p["barcode"], name=p.get("name", "?"),
                    quantity=1, unit_price=info.get("price", 10.0),
                    subtotal=info.get("price", 10.0),
                    category=info.get("category"), aisle=info.get("aisle"),
                ))

            last_bc = cart_products[-1]["barcode"] if cart_products else None
            cart = CartResponse(
                cart_id="cmp-%d" % test_count, items=cart_items,
                total_items=len(cart_items),
                total_amount=sum(it.subtotal for it in cart_items),
                updated_at=now.isoformat(),
            )

            # --- Algoritmo 1: Association Rules ---
            result_ar = gen_rec_association(cart, promos, last_barcode=last_bc, graph=graph)
            rec_ar = [r.product_barcode for r in result_ar.recommendations]
            m_ar = evaluate_single_test(rec_ar, gt_barcodes, promo_categories, catalog_map, gt_products)
            for key, val in m_ar.items():
                algo_metrics["association_rules"][key].append(val)

            # --- Algoritmo 2: Naive Bayes ---
            result_nb = gen_rec_naive_bayes(cart, promos, last_barcode=last_bc, graph=graph, model=nb_model)
            rec_nb = [r.product_barcode for r in result_nb.recommendations]
            m_nb = evaluate_single_test(rec_nb, gt_barcodes, promo_categories, catalog_map, gt_products)
            for key, val in m_nb.items():
                algo_metrics["naive_bayes"][key].append(val)

        avg = lambda lst: sum(lst) / len(lst) if lst else 0

        r = {"remove_last": remove_n, "num_tests": test_count}
        for algo_name in ["association_rules", "naive_bayes"]:
            m = algo_metrics[algo_name]
            r[algo_name] = {
                "p@1": round(avg(m["p@1"]), 4),
                "p@5": round(avg(m["p@5"]), 4),
                "p@10": round(avg(m["p@10"]), 4),
                "p@20": round(avg(m["p@20"]), 4),
                "r@20": round(avg(m["r@20"]), 4),
                "hr@1": round(avg(m["hr@1"]), 4),
                "hr@5": round(avg(m["hr@5"]), 4),
                "hr@20": round(avg(m["hr@20"]), 4),
                "f1@20": round(avg(m["f1@20"]), 4),
                "mrr": round(avg(m["mrr"]), 4),
                "ndcg@20": round(avg(m["ndcg@20"]), 4),
                "cat_recall": round(avg(m["cat_recall"]), 4),
            }

        results.append(r)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Compara Association Rules vs Naive Bayes.")
    parser.add_argument("--sim-people", type=int, default=200)
    parser.add_argument("--history", type=int, default=1000)
    parser.add_argument("--remove-last", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--num-tests", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    random.seed(args.seed)
    catalog = load_catalog(CATALOG_PATH)
    promos = load_promotions()

    print(SEP2)
    print("  SMART CART 360 -- COMPARACAO DE ALGORITMOS")
    print(SEP2)
    print("  Algoritmo 1: Association Rules + Grafo (co-ocorrencia/confidence)")
    print("  Algoritmo 2: Naive Bayes + Grafo (probabilidade posterior)")
    print(SEP2)
    print("  Simulacao: %d pessoas" % args.sim_people)
    print("  Historico: %d compras" % args.history)
    print("  Remove ultimos: %s" % str(args.remove_last))
    print("  Testes: %d" % args.num_tests)
    print(SEP2)

    results = run_comparison(
        sim_people=args.sim_people, history_purchases=args.history,
        remove_last_counts=args.remove_last, num_tests=args.num_tests,
        promos=promos, catalog=catalog, seed=args.seed,
    )

    for r in results:
        print("")
        print(SEP)
        print("  REMOVIDOS: ultimos %d itens | Testes: %d" % (r["remove_last"], r["num_tests"]))
        print(SEP)

        ar = r["association_rules"]
        nb = r["naive_bayes"]

        print("")
        print("  %-25s %12s %12s %10s" % ("Metrica", "Assoc.Rules", "NaiveBayes", "Melhor"))
        print("  " + "-" * 62)

        comparisons = [
            ("P@1", ar["p@1"], nb["p@1"]),
            ("P@5", ar["p@5"], nb["p@5"]),
            ("P@10", ar["p@10"], nb["p@10"]),
            ("P@20", ar["p@20"], nb["p@20"]),
            ("Recall@20", ar["r@20"], nb["r@20"]),
            ("Hit Rate@1", ar["hr@1"], nb["hr@1"]),
            ("Hit Rate@5", ar["hr@5"], nb["hr@5"]),
            ("Hit Rate@20", ar["hr@20"], nb["hr@20"]),
            ("F1@20", ar["f1@20"], nb["f1@20"]),
            ("MRR", ar["mrr"], nb["mrr"]),
            ("NDCG@20", ar["ndcg@20"], nb["ndcg@20"]),
            ("Category Recall", ar["cat_recall"], nb["cat_recall"]),
        ]

        ar_wins = 0
        nb_wins = 0
        ties = 0

        for name, val_ar, val_nb in comparisons:
            if val_ar > val_nb + 0.001:
                winner = "AR"
                ar_wins += 1
            elif val_nb > val_ar + 0.001:
                winner = "NB"
                nb_wins += 1
            else:
                winner = "="
                ties += 1

            if name in ("MRR", "NDCG@20"):
                print("  %-25s %11.4f %11.4f %10s" % (name, val_ar, val_nb, winner))
            else:
                print("  %-25s %10.1f%% %10.1f%% %10s" % (
                    name, val_ar * 100, val_nb * 100, winner))

        print("")
        print("  Placar: Association Rules %d x %d Naive Bayes (empates: %d)" % (
            ar_wins, nb_wins, ties))

    # --- Tabela resumo ---
    print("")
    print(SEP2)
    print("  RESUMO COMPARATIVO")
    print(SEP2)
    print("  %4s | %-18s | %7s %7s %7s %7s %7s" % (
        "Rem", "Algoritmo", "P@1", "P@5", "HR@5", "MRR", "NDCG"))
    print("  " + "-" * 68)
    for r in results:
        for algo_key, algo_label in [("association_rules", "Association Rules"), ("naive_bayes", "Naive Bayes")]:
            a = r[algo_key]
            print("  %4d | %-18s | %6.1f%% %6.1f%% %6.1f%% %6.3f %6.3f" % (
                r["remove_last"], algo_label,
                a["p@1"] * 100, a["p@5"] * 100, a["hr@5"] * 100,
                a["mrr"], a["ndcg@20"]))
        print("  " + "-" * 68)
    print(SEP2)

    output_path = (
        Path(args.output) if args.output
        else ROOT / "scripts" / "comparison_results.json"
    )
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("")
    print("  Resultados salvos em: %s" % str(output_path))


SEP = "-" * 70
SEP2 = "=" * 70


if __name__ == "__main__":
    main()