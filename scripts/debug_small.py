import sys
from pathlib import Path
import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[0]
sys.path.insert(0, str(ROOT_DIR))

from mock_supermercado.simulation.layout import SUPERMARKET_LAYOUT
from mock_supermercado.simulation.purchase_simulator import WALKING_SPEED_MPS, SHELF_PICKUP_SECONDS, distance_between_products
from servidor_central.algorithms.location_graph import rebuild_location_graph
from servidor_central.database import get_db_path

graph = rebuild_location_graph(db_path=get_db_path())
errors = []
for link in graph.get("links", []):
    barcode_a = link["source"]
    barcode_b = link["target"]
    inferred_time = link.get("avg_elapsed_seconds", link.get("weight_seconds", link.get("strength")))
    if inferred_time is None: continue
    
    try:
        real_distance = distance_between_products(barcode_a, barcode_b, SUPERMARKET_LAYOUT)
        real_time = (real_distance / WALKING_SPEED_MPS) + SHELF_PICKUP_SECONDS
        
        error_perc = abs(inferred_time - real_time) / real_time
        errors.append((real_time, inferred_time, error_perc, link.get("transition_count")))
    except:
        pass

errors.sort(key=lambda x: x[3])

small_errors = [x for x in errors if x[3] <= 15]

print("--- Small Volumes (Count <= 15) ---")
for r, i, e, c in small_errors[-15:]:
    print(f"Real: {r:.2f}s | Inferred: {i:.2f}s | Error: {e*100:.2f}% | Count: {c}")

print("\n--- Summary ---")
print(f"Mean Error Total: {np.mean([e for r, i, e, c in errors])*100:.2f}%")
print(f"Mean Error KDE: {np.mean([e for r, i, e, c in errors if c >= 50])*100:.2f}%")
print(f"Mean Error IQR: {np.mean([e for r, i, e, c in errors if 16 <= c <= 49])*100:.2f}%")
print(f"Mean Error Small: {np.mean([e for r, i, e, c in small_errors])*100:.2f}%")
