"""
Smart Cart 360 -- Script para construir o grafo de co-ocorrencia.

Uso:
    python scripts/build_recommendation_graph.py
    python scripts/build_recommendation_graph.py --min-cooccurrence 5
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os
os.environ.setdefault(
    "SMART_CART_DB_PATH",
    str(ROOT / "servidor_central" / "smart_cart.db"),
)

from servidor_central.algorithms.recommendation_graph import (
    build_recommendation_graph,
)


def main():
    parser = argparse.ArgumentParser(
        description="Constroi o grafo de co-ocorrencia para recomendacao.")
    parser.add_argument("--min-cooccurrence", type=int, default=3)
    parser.add_argument("--max-edges", type=int, default=500)
    args = parser.parse_args()

    print("Construindo grafo de co-ocorrencia...")
    print("  Min co-ocorrencia: %d" % args.min_cooccurrence)
    print("  Max arestas: %d" % args.max_edges)

    graph = build_recommendation_graph(
        min_cooccurrence=args.min_cooccurrence,
        max_edges=args.max_edges,
    )

    print("")
    print("  Nos: %d" % len(graph.get("nodes", [])))
    print("  Arestas: %d" % len(graph.get("links", [])))
    print("  Salvo em: %s" % graph["meta"].get("cache_path", "?"))

    if graph["links"]:
        top5 = sorted(graph["links"],
                       key=lambda l: l["co_occurrence_count"], reverse=True)[:5]
        print("")
        print("  Top 5 co-ocorrencias:")
        node_map = {n["id"]: n["name"] for n in graph["nodes"]}
        for link in top5:
            s = node_map.get(link["source"], link["source"])
            t = node_map.get(link["target"], link["target"])
            print("    %s <-> %s : %dx (support=%.1f%%, lift=%.2f)" % (
                s, t, link["co_occurrence_count"],
                link["support"] * 100, link["lift"]))


if __name__ == "__main__":
    main()