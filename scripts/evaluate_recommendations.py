"""
Smart Cart 360° — Avaliação do Algoritmo de Recomendação (v2)
==============================================================

Script que avalia a qualidade do algoritmo de recomendação usando
o método de split de cesta (basket split evaluation).

Adaptado para funcionar com o sistema de simulação do João
(mock_supermercado/simulation/) e com o algoritmo unificado
que combina grafo de localização + co-ocorrência.

Métricas calculadas:
    - Precision@K  = |hits| / K
    - Recall@K     = |hits| / |ground_truth|
    - F1@K         = média harmônica de precision e recall
    - Hit Rate     = % de testes com pelo menos 1 acerto
    - MRR          = Mean Reciprocal Rank

Uso:
    python scripts/evaluate_recommendations.py
    python scripts/evaluate_recommendations.py --sizes 50 100 200 --num-tests 60
    python scripts/evaluate_recommendations.py --no-graph

Autores: [Seu nome aqui]
Projeto: Smart Cart 360° — TCC Insper 2026
"""

import argparse
import csv
import json
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
from servidor_central.algorithms.location_graph import (
    load_location_graph,
    rebuild_location_graph,
)
from servidor_central.database import get_db_path

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


def load_promotions() -> list[PromotionResponse]:
    promos = []
    with open(PROMOTIONS_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            promos.append(
                PromotionResponse(
                    id=row["id"],
                    title=row["title"],
                    description=row["description"],
                    product_barcode=row["product_barcode"],
                    discount_type=row["discount_type"],
                    discount_value=float(row["discount_value"]),
                    aisle=row["aisle"] if row["aisle"] else None,
                )
            )
    return promos


def populate_with_simulation(people_count: int, seed: int, clear: bool = True):
    return populate_simulated_purchases(
        people_count=people_count,
        supermarket_layout=SUPERMARKET_LAYOUT,
        personas=PERSONAS,
        persona_proportions=PERSONA_PROPORTIONS,
        seed=seed,
        clear_existing_data=clear,
        aisle_gap_m=AISLE_GAP_METERS,
    )


def populate_purchase_history(num_purchases: int, seed: int):
    catalog = load_catalog(CATALOG_PATH)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("DELETE FROM purchase_items")
    conn.execute("DELETE FROM purchase_history")
    conn.commit()
    purchases = generate_all_purchases(catalog, num_purchases)
    save_purchases(conn, purchases)
    conn.close()


def generate_test_purchases(num_tests: int, seed: int):
    rng = random.Random(seed + 9999)
    test_purchases = []
    testable = [p for p in PERSONAS if p["name"] != "Quer Tudo"]
    weights = PERSONA_PROPORTIONS[1:]

    for _ in range(num_tests * 3):
        persona = rng.choices(testable, weights=weights, k=1)[0]
        products = [dict(p) for p in persona["products"]]
        if len(products) >= 4:
            test_purchases.append((persona["name"], products))
        if len(test_purchases) >= num_tests:
            break

    return test_purchases


def evaluate_at_size(
    sim_people, history_purchases, num_tests, promos, catalog, seed, use_graph=True
):
    promo_barcodes = {p.product_barcode for p in promos}
    catalog_by_barcode = {p["barcode"]: p for p in catalog}
    now = datetime.now(timezone.utc)

    print(f"    Populando {sim_people} carrinhos simulados...")
    populate_with_simulation(sim_people, seed, clear=True)

    print(f"    Populando {history_purchases} compras no histórico...")
    populate_purchase_history(history_purchases, seed)

    graph = None
    if use_graph:
        print("    Reconstruindo grafo de localização...")
        try:
            graph = rebuild_location_graph()
            print(
                f"    Grafo: {len(graph.get('nodes', []))} nós, "
                f"{len(graph.get('links', []))} arestas"
            )
        except Exception as e:
            print(f"    Aviso: grafo não disponível ({e})")

    test_purchases = generate_test_purchases(num_tests, seed)
    rng = random.Random(seed)

    precisions, recalls, f1s, hit_rates, mrrs = [], [], [], [], []
    per_persona: dict[str, dict] = {}

    for persona_name, products in test_purchases:
        rng.shuffle(products)
        half = len(products) // 2
        cart_half = products[:half]
        gt_half = products[half:]

        gt_barcodes = {p["barcode"] for p in gt_half} & promo_barcodes
        if not gt_barcodes:
            continue

        cart_items = []
        for i, p in enumerate(cart_half):
            info = catalog_by_barcode.get(p["barcode"], {})
            cart_items.append(
                CartItemResponse(
                    item_id=i + 1,
                    barcode=p["barcode"],
                    name=p["name"],
                    quantity=1,
                    unit_price=info.get("price", 10.0),
                    subtotal=info.get("price", 10.0),
                    category=info.get("category"),
                    aisle=info.get("aisle"),
                )
            )

        cart = CartResponse(
            cart_id=f"eval-{persona_name}",
            items=cart_items,
            total_items=len(cart_items),
            total_amount=sum(i.subtotal for i in cart_items),
            updated_at=now.isoformat(),
        )

        result = generate_recommendations(cart, promos, graph=graph)
        rec_barcodes = [r.product_barcode for r in result.recommendations]
        rec_set = set(rec_barcodes)

        hits = gt_barcodes & rec_set
        k = len(rec_set)
        n_gt = len(gt_barcodes)

        precision = len(hits) / k if k else 0
        recall = len(hits) / n_gt if n_gt else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        hit_rate = 1.0 if hits else 0.0

        mrr = 0.0
        for rank, bc in enumerate(rec_barcodes, 1):
            if bc in gt_barcodes:
                mrr = 1.0 / rank
                break

        precisions.append(precision)
        recalls.append(recall)
        f1s.append(f1)
        hit_rates.append(hit_rate)
        mrrs.append(mrr)

        per_persona.setdefault(persona_name, {"p": [], "r": [], "f1": [], "hr": [], "mrr": []})
        pp = per_persona[persona_name]
        pp["p"].append(precision)
        pp["r"].append(recall)
        pp["f1"].append(f1)
        pp["hr"].append(hit_rate)
        pp["mrr"].append(mrr)

    avg = lambda lst: sum(lst) / len(lst) if lst else 0

    result_dict = {
        "sim_people": sim_people,
        "history_purchases": history_purchases,
        "use_graph": use_graph,
        "num_tests": len(precisions),
        "precision": round(avg(precisions), 4),
        "recall": round(avg(recalls), 4),
        "f1": round(avg(f1s), 4),
        "hit_rate": round(avg(hit_rates), 4),
        "mrr": round(avg(mrrs), 4),
        "per_persona": {},
    }

    for pname, vals in per_persona.items():
        result_dict["per_persona"][pname] = {
            "precision": round(avg(vals["p"]), 4),
            "recall": round(avg(vals["r"]), 4),
            "f1": round(avg(vals["f1"]), 4),
            "hit_rate": round(avg(vals["hr"]), 4),
            "mrr": round(avg(vals["mrr"]), 4),
            "n_tests": len(vals["p"]),
        }

    return result_dict


def main():
    parser = argparse.ArgumentParser(
        description="Avalia o algoritmo de recomendação do Smart Cart."
    )
    parser.add_argument("--sizes", type=int, nargs="+", default=[50, 100, 200])
    parser.add_argument("--history-multiplier", type=int, default=5)
    parser.add_argument("--num-tests", type=int, default=60)
    parser.add_argument("--no-graph", action="store_true")
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    use_graph = not args.no_graph
    random.seed(args.seed)
    catalog = load_catalog(CATALOG_PATH)
    promos = load_promotions()

    print("=" * 60)
    print("  SMART CART 360° — AVALIAÇÃO DO ALGORITMO v2")
    print("=" * 60)
    print(f"  Catálogo: {len(catalog)} produtos")
    print(f"  Promoções: {len(promos)} promoções")
    print(f"  Personas (João): {len(PERSONAS)} personas")
    print(f"  Grafo de localização: {'SIM' if use_graph else 'NÃO'}")
    print(f"  Testes por tamanho: {args.num_tests}")
    print(f"  Tamanhos (pessoas): {args.sizes}")
    print("=" * 60)

    all_results = []

    for size in args.sizes:
        hist = size * args.history_multiplier
        print(f"\n{'─' * 60}")
        print(f"  {size} pessoas simuladas + {hist} compras histórico")
        print(f"{'─' * 60}")

        r = evaluate_at_size(size, hist, args.num_tests, promos, catalog, args.seed, use_graph)
        all_results.append(r)

        print(f"\n  Precision@20:  {r['precision']:.2%}")
        print(f"  Recall@20:     {r['recall']:.2%}")
        print(f"  F1@20:         {r['f1']:.2%}")
        print(f"  Hit Rate:      {r['hit_rate']:.2%}")
        print(f"  MRR:           {r['mrr']:.4f}")
        print(f"  Testes: {r['num_tests']}")
        print()
        print(f"  {'Persona':<30} {'Prec':>7} {'Rec':>7} {'F1':>7} {'HR':>7} {'N':>4}")
        print(f"  {'─' * 62}")
        for pname, pv in sorted(r["per_persona"].items()):
            print(
                f"  {pname:<30} {pv['precision']:>6.1%} {pv['recall']:>6.1%} "
                f"{pv['f1']:>6.1%} {pv['hit_rate']:>6.1%} {pv['n_tests']:>4}"
            )

    print(f"\n{'=' * 60}")
    print(f"  COMPARAÇÃO")
    print(f"{'=' * 60}")
    print(f"  {'Pessoas':>8} {'Hist':>8} {'Prec':>10} {'Rec':>10} {'F1':>10} {'HR':>10} {'MRR':>10}")
    print(f"  {'─' * 66}")
    for r in all_results:
        print(
            f"  {r['sim_people']:>8} {r['history_purchases']:>8} "
            f"{r['precision']:>9.2%} {r['recall']:>9.2%} {r['f1']:>9.2%} "
            f"{r['hit_rate']:>9.2%} {r['mrr']:>9.4f}"
        )
    print(f"{'=' * 60}")

    output_path = Path(args.output) if args.output else ROOT / "scripts" / "eval_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n  Resultados salvos em: {output_path}")


if __name__ == "__main__":
    main()