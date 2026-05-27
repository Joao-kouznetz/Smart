import sys
from pathlib import Path
import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[0]
sys.path.insert(0, str(ROOT_DIR))

from mock_supermercado.simulation.layout import SUPERMARKET_LAYOUT
from mock_supermercado.simulation.purchase_simulator import WALKING_SPEED_MPS, SHELF_PICKUP_SECONDS, distance_between_products
from servidor_central.algorithms.location_graph import rebuild_location_graph, get_nearby_products
from servidor_central.database import get_db_path
from mock_supermercado.simulation.purchase_simulator import populate_simulated_purchases
from mock_supermercado.simulation.personas import PERSONAS, PERSONA_PROPORTIONS

db_path = get_db_path()

print("Recalculando para explicar o fenônemo do Fixed vs Bimodal...")
for dist in ["fixed", "bimodal"]:
    populate_simulated_purchases(
        people_count=1000,
        supermarket_layout=SUPERMARKET_LAYOUT,
        personas=PERSONAS,
        persona_proportions=PERSONA_PROPORTIONS,
        db_path=db_path,
        clear_existing_data=True,
        travel_time_distribution=dist,
        seed=42
    )
    graph = rebuild_location_graph(db_path=db_path)
    
    total_nodes = 0
    top1_same_aisle = 0
    top3_same_aisle = 0
    
    same_aisle_edges_count = 0
    total_edges = 0
    
    for link in graph.get("links", []):
        total_edges += 1
        source_node = next((n for n in graph["nodes"] if n["id"] == link["source"]), None)
        target_node = next((n for n in graph["nodes"] if n["id"] == link["target"]), None)
        if source_node and target_node and source_node["aisle"] == target_node["aisle"]:
            same_aisle_edges_count += 1
            
    for node in graph.get("nodes", []):
        total_nodes += 1
        barcode = node["id"]
        true_aisle = node["aisle"]
        
        nearby = get_nearby_products(graph, barcode, limit=3)
        if not nearby: continue
        
        if nearby[0]["aisle"] == true_aisle:
            top1_same_aisle += 1
            
        if any(nb["aisle"] == true_aisle for nb in nearby):
            top3_same_aisle += 1
            
    print(f"\n--- {dist.upper()} ---")
    print(f"Total de arestas no grafo: {total_edges}")
    print(f"Arestas que conectam mesmo corredor (comportamento): {same_aisle_edges_count} ({(same_aisle_edges_count/total_edges)*100:.1f}%)")
    print(f"O 1º vizinho mais próximo inferido estava no mesmo corredor? {(top1_same_aisle/total_nodes)*100:.1f}%")
    print(f"Algum dos 3 vizinhos inferidos estava no mesmo corredor? {(top3_same_aisle/total_nodes)*100:.1f}%")
