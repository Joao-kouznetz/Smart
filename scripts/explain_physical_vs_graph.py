import sys
from pathlib import Path
import numpy as np
import itertools

ROOT_DIR = Path(__file__).resolve().parents[0]
sys.path.insert(0, str(ROOT_DIR))

from mock_supermercado.simulation.layout import SUPERMARKET_LAYOUT
from mock_supermercado.simulation.purchase_simulator import WALKING_SPEED_MPS, SHELF_PICKUP_SECONDS, distance_between_products
from servidor_central.algorithms.location_graph import rebuild_location_graph, get_nearby_products
from servidor_central.database import get_db_path
from mock_supermercado.simulation.purchase_simulator import populate_simulated_purchases
from mock_supermercado.simulation.personas import PERSONAS, PERSONA_PROPORTIONS

db_path = get_db_path()

print("Recalculando Métricas Topologicas Reais...")

# Criando mapa de distancias fisicas absolutas do supermercado inteiro
all_barcodes = []
layout_flat = {}
for aisle, prods in SUPERMARKET_LAYOUT.items():
    for p in prods:
        all_barcodes.append(p["barcode"])
        layout_flat[p["barcode"]] = aisle

for dist in ["fixed", "bimodal"]:
    populate_simulated_purchases(
        people_count=1500,
        supermarket_layout=SUPERMARKET_LAYOUT,
        personas=PERSONAS,
        persona_proportions=PERSONA_PROPORTIONS,
        db_path=db_path,
        clear_existing_data=True,
        travel_time_distribution=dist,
        seed=42
    )
    graph = rebuild_location_graph(db_path=db_path)
    
    # 1. Realidade Fisica: Qual é o vizinho FISICAMENTE mais perto de cada produto?
    real_closest_same_aisle = 0
    
    # 2. Grafo Reconstruido: Qual é o vizinho TEMPORALMENTE mais perto (força)?
    graph_closest_same_aisle = 0
    total_nodes_evaluated = 0
    
    for barcode in all_barcodes:
        # Pega a aisle real
        my_aisle = layout_flat[barcode]
        
        # 1. Distancia Fisica
        closest_physical_barcode = None
        min_physical_dist = float('inf')
        for other in all_barcodes:
            if other == barcode: continue
            d = distance_between_products(barcode, other, SUPERMARKET_LAYOUT)
            if d < min_physical_dist:
                min_physical_dist = d
                closest_physical_barcode = other
                
        if closest_physical_barcode and layout_flat[closest_physical_barcode] == my_aisle:
            real_closest_same_aisle += 1
            
        # 2. Distancia no Grafo
        nearby = get_nearby_products(graph, barcode, limit=1)
        if nearby:
            total_nodes_evaluated += 1
            if nearby[0]["aisle"] == my_aisle:
                graph_closest_same_aisle += 1

    print(f"\n--- {dist.upper()} ---")
    print(f"Pela PLANTA FÍSICA REAL: O produto mais próximo fisicamente está no mesmo corredor em {(real_closest_same_aisle/len(all_barcodes))*100:.1f}% das vezes!")
    if total_nodes_evaluated > 0:
        print(f"Pelo GRAFO ({dist}): O produto vizinho inferido estava no mesmo corredor em {(graph_closest_same_aisle/total_nodes_evaluated)*100:.1f}% das vezes!")

