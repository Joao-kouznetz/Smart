import argparse
import sys
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mock_supermercado.simulation.layout import SUPERMARKET_LAYOUT
from mock_supermercado.simulation.purchase_simulator import populate_simulated_purchases, WALKING_SPEED_MPS, SHELF_PICKUP_SECONDS, distance_between_products
from mock_supermercado.simulation.personas import PERSONAS, PERSONA_PROPORTIONS
from servidor_central.algorithms.location_graph import rebuild_location_graph, get_nearby_products

def evaluate_graph_accuracy(graph, layout):
    """Mede tempo estimado, vizinhos e agrupamento de corredor contra a planta real."""
    errors = []
    nodes_by_id = {str(node["id"]): node for node in graph.get("nodes", [])}

    for link in graph.get("links", []):
        barcode_a = link["source"]
        barcode_b = link["target"]
        inferred_time = link.get("avg_elapsed_seconds", link.get("weight_seconds", link.get("strength")))
        if inferred_time is None: continue
        
        try:
            # Distancia Fisica
            real_distance = distance_between_products(barcode_a, barcode_b, layout)
            # Tempo original deterministico
            real_time = (real_distance / WALKING_SPEED_MPS) + SHELF_PICKUP_SECONDS
            
            # Erro em % (abs)
            error_perc = abs(inferred_time - real_time) / real_time
            errors.append(error_perc)

        except Exception:
            continue

    total_products = 0
    top1_same_aisle = 0
    top3_same_aisle = 0
    for node in graph.get("nodes", []):
        total_products += 1
        barcode = node["id"]
        true_aisle = node["aisle"]

        nearby = get_nearby_products(graph, barcode, limit=5)
        if nearby and nearby[0].get("aisle") == true_aisle:
            top1_same_aisle += 1
        if any(nb.get("aisle") == true_aisle for nb in nearby[:3]):
            top3_same_aisle += 1

    same_real_pairs = 0
    same_real_allocated_pairs = 0
    same_allocated_pairs = 0
    same_allocated_real_pairs = 0
    node_ids = sorted(nodes_by_id)
    for index, source in enumerate(node_ids):
        for target in node_ids[index + 1 :]:
            source_node = nodes_by_id[source]
            target_node = nodes_by_id[target]
            same_real_aisle = source_node.get("aisle") == target_node.get("aisle")
            same_allocated_corridor = (
                source_node.get("allocated_corridor")
                and source_node.get("allocated_corridor") == target_node.get("allocated_corridor")
            )
            if same_real_aisle:
                same_real_pairs += 1
                if same_allocated_corridor:
                    same_real_allocated_pairs += 1
            if same_allocated_corridor:
                same_allocated_pairs += 1
                if same_real_aisle:
                    same_allocated_real_pairs += 1

    mean_error = float(np.mean(errors) * 100) if errors else 0.0
    median_error = float(np.median(errors) * 100) if errors else 0.0
    top1_accuracy = (top1_same_aisle / total_products) * 100 if total_products > 0 else 0.0
    top3_accuracy = (top3_same_aisle / total_products) * 100 if total_products > 0 else 0.0
    same_corridor_recall = (
        (same_real_allocated_pairs / same_real_pairs) * 100 if same_real_pairs else 0.0
    )
    same_corridor_precision = (
        (same_allocated_real_pairs / same_allocated_pairs) * 100 if same_allocated_pairs else 0.0
    )

    return {
        "mean_time_error": mean_error,
        "median_time_error": median_error,
        "top1_same_aisle": top1_accuracy,
        "top3_same_aisle": top3_accuracy,
        "same_corridor_pair_recall": same_corridor_recall,
        "same_corridor_pair_precision": same_corridor_precision,
        "same_real_pairs": same_real_pairs,
        "same_real_allocated_pairs": same_real_allocated_pairs,
        "same_allocated_pairs": same_allocated_pairs,
        "same_allocated_real_pairs": same_allocated_real_pairs,
    }

def main():
    parser = argparse.ArgumentParser(description="Avalia o grafo de localizacao por distribuicao simulada.")
    parser.add_argument("--people-count", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    print("Iniciando validacao do algoritmo de grafos...")

    distributions = ["fixed", "normal", "right-tail", "bimodal"]
    results = {}

    with TemporaryDirectory(prefix="smart-cart-eval-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        db_path = tmp_path / "smart_cart_eval.db"
        graph_path = tmp_path / "location_graph_eval.json"

        for dist in distributions:
            print(f"\nTestando distribuicao: {dist}")

            populate_simulated_purchases(
                people_count=args.people_count,
                supermarket_layout=SUPERMARKET_LAYOUT,
                personas=PERSONAS,
                persona_proportions=PERSONA_PROPORTIONS,
                db_path=db_path,
                clear_existing_data=True,
                travel_time_distribution=dist,
                seed=args.seed,
            )

            graph = rebuild_location_graph(db_path=db_path, output_path=graph_path)
            metrics = evaluate_graph_accuracy(graph, SUPERMARKET_LAYOUT)
            links_count = len(graph.get("links", []))

            results[dist] = {
                "Erro médio do tempo (%)": round(metrics["mean_time_error"], 2),
                "Erro mediano do tempo (%)": round(metrics["median_time_error"], 2),
                "Top-1 vizinho no mesmo corredor real (%)": round(metrics["top1_same_aisle"], 2),
                "Top-3 contém mesmo corredor real (%)": round(metrics["top3_same_aisle"], 2),
                "Recall pares reais mesmo corredor alocados juntos (%)": round(metrics["same_corridor_pair_recall"], 2),
                "Precisão pares alocados juntos realmente mesmo corredor (%)": round(metrics["same_corridor_pair_precision"], 2),
                "Pares reais mesmo corredor alocados juntos": f"{metrics['same_real_allocated_pairs']}/{metrics['same_real_pairs']}",
                "Pares alocados juntos corretos": f"{metrics['same_allocated_real_pairs']}/{metrics['same_allocated_pairs']}",
                "Arestas válidas mantidas": links_count,
                "Corredores estimados": graph.get("meta", {}).get("allocated_corridor_count"),
            }

            print(
                "Erro médio: "
                f"{metrics['mean_time_error']:.2f}% | "
                "Top-1 mesmo corredor: "
                f"{metrics['top1_same_aisle']:.2f}% | "
                "Recall pares mesmo corredor: "
                f"{metrics['same_corridor_pair_recall']:.2f}%"
            )
        
    print("\nResumo Final:")
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
