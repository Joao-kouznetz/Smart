"""
Smart Cart 360 - Avaliacao Sequencial Refinada (Etapa A)
==========================================================

Avaliacao refinada que evolui a metodologia de testes:

    v1 (evaluate_recommendations.py): split aleatorio, mede P/R/F1
        conforme a base cresce.
    v2 (este script): remocao sequencial na ORDEM REAL de escaneamento,
        multiplos K, NDCG, analise por categoria, e escala de ruido.

Melhorias sobre v1:
    1. Usa a ordem real de escaneamento do simulador (timestamps do
       cart_interactions).
    2. Remove os N ultimos itens da sequencia (nao aleatoriamente).
    3. Mede Precision@1, @5, @10, @20 separadamente.
    4. Calcula NDCG (Normalized Discounted Cumulative Gain).
    5. Analisa acerto por produto exato vs acerto por categoria.
    6. Testa com diferentes niveis de ruido (0%, 25%, 50%).

Uso:
    python scripts/evaluate_sequential.py
    python scripts/evaluate_sequential.py --noise 0 25 50 75
    python scripts/evaluate_sequential.py --remove-last 1 2 3

Autores: [Seu nome aqui]
Projeto: Smart Cart 360 - TCC Insper 2026
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
from servidor_central.algorithms.recommendations import generate_recommendations
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

SEP = "-" * 70
SEP2 = "=" * 70
SEP3 = "-" * 72
SEP4 = "-" * 66


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


def add_noise_to_sequence(products, noise_pct, all_barcodes, catalog_map, rng):
    if noise_pct <= 0 or not products:
        return list(products)
    noisy = list(products)
    n_to_replace = max(1, int(len(noisy) * noise_pct / 100))
    n_to_replace = min(n_to_replace, len(noisy) - 2)
    if n_to_replace <= 0:
        return noisy
    indices = rng.sample(range(len(noisy)), n_to_replace)
    for idx in indices:
        bc = rng.choice(all_barcodes)
        info = catalog_map.get(bc, {})
        noisy[idx] = {"barcode": bc, "name": info.get("name", "Random-" + bc[-4:])}
    return noisy


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


def evaluate_sequential(
    sim_people, history_purchases, remove_last_counts, noise_levels,
    num_tests, promos, catalog, seed,
):
    promo_barcodes = {p.product_barcode for p in promos}
    catalog_map = {p["barcode"]: p for p in catalog}
    all_barcodes = list(catalog_map.keys())
    promo_categories = {}
    for p in promos:
        bc = p.product_barcode
        if bc and bc in catalog_map:
            cat = catalog_map[bc].get("category")
            if cat:
                promo_categories[bc] = cat
    now = datetime.now(timezone.utc)

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

    print("  Buscando sequencias reais de escaneamento...")
    conn2 = sqlite3.connect(str(DB_PATH))
    conn2.row_factory = sqlite3.Row
    real_sequences = get_real_scan_sequences(conn2, max_carts=500)
    conn2.close()
    conn.close()
    print("  Encontradas %d sequencias reais" % len(real_sequences))

    print("  Reconstruindo grafo de localizacao...")
    graph = None
    try:
        graph = rebuild_location_graph()
        n_nodes = len(graph.get("nodes", []))
        n_edges = len(graph.get("links", []))
        print("  Grafo: %d nos, %d arestas" % (n_nodes, n_edges))
    except Exception as e:
        print("  Aviso: grafo nao disponivel (%s)" % str(e))

    rng = random.Random(seed + 7777)
    results = []

    for noise_pct in noise_levels:
        for remove_n in remove_last_counts:
            metrics_by_k = {k: {"p": [], "r": [], "hr": []} for k in [1, 5, 10, 20]}
            f1_list, hit_rate_list, mrr_list, ndcg_list = [], [], [], []
            category_hits, category_total = [], []
            per_persona = {}
            test_count = 0

            available = [(p, seq) for p, seq in real_sequences
                         if p != "Quer Tudo" and len(seq) > remove_n + 1]

            for persona_name, sequence in available:
                if test_count >= num_tests:
                    break
                noisy_seq = add_noise_to_sequence(
                    [{"barcode": bc, "name": catalog_map.get(bc, {}).get("name", bc)}
                     for bc in sequence],
                    noise_pct, all_barcodes, catalog_map, rng,
                )
                if len(noisy_seq) <= remove_n:
                    continue

                cart_products = noisy_seq[:-remove_n]
                gt_products = noisy_seq[-remove_n:]
                gt_barcodes = {p["barcode"] for p in gt_products} & promo_barcodes
                if not gt_barcodes:
                    continue

                gt_categories = set()
                for p in gt_products:
                    cat = catalog_map.get(p["barcode"], {}).get("category")
                    if cat:
                        gt_categories.add(cat)

                test_count += 1
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
                    cart_id="seq-%d" % test_count, items=cart_items,
                    total_items=len(cart_items),
                    total_amount=sum(it.subtotal for it in cart_items),
                    updated_at=now.isoformat(),
                )

                result = generate_recommendations(cart, promos, last_barcode=last_bc, graph=graph)
                rec_barcodes = [r.product_barcode for r in result.recommendations]

                for k in [1, 5, 10, 20]:
                    top_k = set(rec_barcodes[:k])
                    hits_k = gt_barcodes & top_k
                    metrics_by_k[k]["p"].append(len(hits_k) / k if k else 0)
                    metrics_by_k[k]["r"].append(len(hits_k) / len(gt_barcodes) if gt_barcodes else 0)
                    metrics_by_k[k]["hr"].append(1.0 if hits_k else 0.0)

                hits_20 = gt_barcodes & set(rec_barcodes[:20])
                p20 = len(hits_20) / 20
                r20 = len(hits_20) / len(gt_barcodes) if gt_barcodes else 0
                f1_val = 2 * p20 * r20 / (p20 + r20) if (p20 + r20) > 0 else 0
                f1_list.append(f1_val)
                hit_rate_list.append(1.0 if hits_20 else 0.0)

                mrr = 0.0
                for rank, bc in enumerate(rec_barcodes, 1):
                    if bc in gt_barcodes:
                        mrr = 1.0 / rank
                        break
                mrr_list.append(mrr)

                rels = [1.0 if bc in gt_barcodes else 0.0 for bc in rec_barcodes[:20]]
                ndcg_list.append(ndcg(rels, 20))

                rec_cats = set()
                for bc in rec_barcodes[:20]:
                    c = promo_categories.get(bc)
                    if c:
                        rec_cats.add(c)
                cat_h = len(gt_categories & rec_cats)
                cat_t = len(gt_categories) if gt_categories else 1
                category_hits.append(cat_h)
                category_total.append(cat_t)

                per_persona.setdefault(persona_name, {
                    "p1": [], "p5": [], "p10": [], "p20": [],
                    "r20": [], "f1": [], "hr": [], "mrr": [], "ndcg": [], "cat_recall": [],
                })
                pp = per_persona[persona_name]
                pp["p1"].append(metrics_by_k[1]["p"][-1])
                pp["p5"].append(metrics_by_k[5]["p"][-1])
                pp["p10"].append(metrics_by_k[10]["p"][-1])
                pp["p20"].append(metrics_by_k[20]["p"][-1])
                pp["r20"].append(r20)
                pp["f1"].append(f1_val)
                pp["hr"].append(1.0 if hits_20 else 0.0)
                pp["mrr"].append(mrr)
                pp["ndcg"].append(ndcg_list[-1])
                pp["cat_recall"].append(cat_h / cat_t if cat_t > 0 else 0)

            avg = lambda lst: sum(lst) / len(lst) if lst else 0
            r = {
                "noise_pct": noise_pct, "remove_last": remove_n, "num_tests": test_count,
                "precision_at_1": round(avg(metrics_by_k[1]["p"]), 4),
                "precision_at_5": round(avg(metrics_by_k[5]["p"]), 4),
                "precision_at_10": round(avg(metrics_by_k[10]["p"]), 4),
                "precision_at_20": round(avg(metrics_by_k[20]["p"]), 4),
                "recall_at_1": round(avg(metrics_by_k[1]["r"]), 4),
                "recall_at_5": round(avg(metrics_by_k[5]["r"]), 4),
                "recall_at_10": round(avg(metrics_by_k[10]["r"]), 4),
                "recall_at_20": round(avg(metrics_by_k[20]["r"]), 4),
                "hit_rate_at_1": round(avg(metrics_by_k[1]["hr"]), 4),
                "hit_rate_at_5": round(avg(metrics_by_k[5]["hr"]), 4),
                "hit_rate_at_10": round(avg(metrics_by_k[10]["hr"]), 4),
                "hit_rate_at_20": round(avg(metrics_by_k[20]["hr"]), 4),
                "f1_at_20": round(avg(f1_list), 4),
                "mrr": round(avg(mrr_list), 4),
                "ndcg_at_20": round(avg(ndcg_list), 4),
                "category_recall": round(sum(category_hits) / max(sum(category_total), 1), 4),
                "per_persona": {},
            }
            for pname, vals in per_persona.items():
                r["per_persona"][pname] = {
                    "p@1": round(avg(vals["p1"]), 4), "p@5": round(avg(vals["p5"]), 4),
                    "p@10": round(avg(vals["p10"]), 4), "p@20": round(avg(vals["p20"]), 4),
                    "recall@20": round(avg(vals["r20"]), 4), "f1@20": round(avg(vals["f1"]), 4),
                    "hit_rate": round(avg(vals["hr"]), 4), "mrr": round(avg(vals["mrr"]), 4),
                    "ndcg@20": round(avg(vals["ndcg"]), 4),
                    "category_recall": round(avg(vals["cat_recall"]), 4),
                    "n_tests": len(vals["f1"]),
                }
            results.append(r)
    return results


def main():
    parser = argparse.ArgumentParser(description="Avaliacao sequencial refinada.")
    parser.add_argument("--sim-people", type=int, default=200)
    parser.add_argument("--history", type=int, default=1000)
    parser.add_argument("--remove-last", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--noise", type=int, nargs="+", default=[0, 25, 50])
    parser.add_argument("--num-tests", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    random.seed(args.seed)
    catalog = load_catalog(CATALOG_PATH)
    promos = load_promotions()

    print(SEP2)
    print("  SMART CART 360 -- AVALIACAO SEQUENCIAL REFINADA")
    print(SEP2)
    print("  Simulacao: %d pessoas" % args.sim_people)
    print("  Historico: %d compras" % args.history)
    print("  Remove ultimos: %s" % str(args.remove_last))
    print("  Niveis de ruido: %s%%" % str(args.noise))
    print("  Testes por config: %d" % args.num_tests)
    print(SEP2)

    results = evaluate_sequential(
        sim_people=args.sim_people, history_purchases=args.history,
        remove_last_counts=args.remove_last, noise_levels=args.noise,
        num_tests=args.num_tests, promos=promos, catalog=catalog, seed=args.seed,
    )

    for r in results:
        print("")
        print(SEP)
        print("  RUIDO: %d%% | REMOVIDOS: ultimos %d itens" % (r["noise_pct"], r["remove_last"]))
        print("  Testes: %d" % r["num_tests"])
        print(SEP)

        print("")
        print("  Metricas por K (acerto por produto exato):")
        print("           %8s %8s %8s %8s" % ("P@1", "P@5", "P@10", "P@20"))
        print("  Prec     %7.1f%% %7.1f%% %7.1f%% %7.1f%%" % (
            r["precision_at_1"] * 100, r["precision_at_5"] * 100,
            r["precision_at_10"] * 100, r["precision_at_20"] * 100))
        print("           %8s %8s %8s %8s" % ("R@1", "R@5", "R@10", "R@20"))
        print("  Recall   %7.1f%% %7.1f%% %7.1f%% %7.1f%%" % (
            r["recall_at_1"] * 100, r["recall_at_5"] * 100,
            r["recall_at_10"] * 100, r["recall_at_20"] * 100))
        print("           %8s %8s %8s %8s" % ("HR@1", "HR@5", "HR@10", "HR@20"))
        print("  HitRate  %7.1f%% %7.1f%% %7.1f%% %7.1f%%" % (
            r["hit_rate_at_1"] * 100, r["hit_rate_at_5"] * 100,
            r["hit_rate_at_10"] * 100, r["hit_rate_at_20"] * 100))

        print("")
        print("  Metricas de ranking:")
        print("    MRR:        %.4f" % r["mrr"])
        print("    NDCG@20:    %.4f" % r["ndcg_at_20"])
        print("    F1@20:      %.2f%%" % (r["f1_at_20"] * 100))

        print("")
        print("  Acerto por categoria:")
        print("    Cat Recall: %.2f%%" % (r["category_recall"] * 100))

        print("")
        header = "  %-28s %6s %6s %6s %7s %7s %6s %4s" % (
            "Persona", "P@1", "P@5", "HR", "MRR", "NDCG", "CatR", "N")
        print(header)
        print("  " + SEP3)
        for pname, pv in sorted(r["per_persona"].items()):
            print("  %-28s %5.0f%% %5.0f%% %5.0f%% %6.3f %6.3f %5.0f%% %4d" % (
                pname, pv["p@1"] * 100, pv["p@5"] * 100,
                pv["hit_rate"] * 100, pv["mrr"], pv["ndcg@20"],
                pv["category_recall"] * 100, pv["n_tests"]))

    print("")
    print(SEP2)
    print("  RESUMO: RUIDO x ITENS REMOVIDOS")
    print(SEP2)
    print("  %6s %4s %7s %7s %7s %7s %7s %7s %7s" % (
        "Ruido", "Rem", "P@1", "P@5", "HR@5", "R@20", "MRR", "NDCG", "CatR"))
    print("  " + SEP4)
    for r in results:
        print("  %5d%% %4d %6.1f%% %6.1f%% %6.1f%% %6.1f%% %6.3f %6.3f %6.1f%%" % (
            r["noise_pct"], r["remove_last"],
            r["precision_at_1"] * 100, r["precision_at_5"] * 100,
            r["hit_rate_at_5"] * 100, r["recall_at_20"] * 100,
            r["mrr"], r["ndcg_at_20"], r["category_recall"] * 100))
    print(SEP2)

    output_path = (
        Path(args.output) if args.output
        else ROOT / "scripts" / "eval_sequential_results.json"
    )
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("")
    print("  Resultados salvos em: %s" % str(output_path))


if __name__ == "__main__":
    main()