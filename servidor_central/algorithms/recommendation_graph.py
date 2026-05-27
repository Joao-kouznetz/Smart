"""
Smart Cart 360 -- Grafo de Co-ocorrencia para Recomendacao (Etapa B)
=====================================================================

Modulo que constroi um grafo onde:
    - Cada NO e um produto do catalogo
    - Cada ARESTA conecta dois produtos que apareceram juntos em compras
    - O PESO da aresta e a quantidade de vezes que os dois produtos
      apareceram na mesma cesta (co-ocorrencia)

Este grafo e a representacao visual do conceito de Association Rules
(Negre, 2015, sec. 3.5.2): cada aresta com peso alto equivale a uma
regra de associacao com alto support.

O grafo e servido via API e renderizado no frontend com
react-force-graph-2d, no mesmo estilo do grafo de localizacao do Joao.

Diferenca entre os dois grafos:
    - Grafo de localizacao (Joao): arestas = transicoes fisicas entre
      corredores, peso = tempo medio de caminhada.
    - Grafo de co-ocorrencia (este): arestas = co-ocorrencia em cestas,
      peso = numero de compras contendo ambos os produtos.

Referencias:
    - Negre, E. (2015). Information and Recommender Systems, sec. 3.5.2
    - Agrawal & Srikant (1994). Fast Algorithms for Mining Association Rules.

Autores: [Seu nome aqui]
Projeto: Smart Cart 360 -- TCC Insper 2026
"""

import json
import math
import os
import random
import sqlite3
from collections import defaultdict
from pathlib import Path

from servidor_central.database import get_connection, get_db_path

DEFAULT_GRAPH_FILENAME = "recommendation_graph.json"
MIN_COOCCURRENCE = 3  # minimo de co-ocorrencias para criar uma aresta


def get_graph_path(path=None):
    if path is not None:
        return Path(path)
    configured = os.getenv("SMART_CART_RECOMMENDATION_GRAPH_PATH")
    if configured:
        return Path(configured)
    return get_db_path().resolve().parent / DEFAULT_GRAPH_FILENAME


def load_recommendation_graph(path=None):
    graph_path = get_graph_path(path)
    if not graph_path.exists():
        return None
    with graph_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_recommendation_graph(graph, path=None):
    graph_path = get_graph_path(path)
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    with graph_path.open("w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return graph_path


def build_recommendation_graph(
    min_cooccurrence=MIN_COOCCURRENCE,
    max_edges=500,
    db_path=None,
    output_path=None,
):
    """
    Constroi o grafo de co-ocorrencia a partir do historico de compras.

    Passo 1: Para cada par de produtos (A, B), conta em quantas
             compras ambos apareceram juntos.
    Passo 2: Filtra pares com co-ocorrencia >= min_cooccurrence.
    Passo 3: Calcula support e confidence para cada par.
    Passo 4: Monta o payload (nodes + links) no mesmo formato do
             grafo de localizacao do Joao.
    Passo 5: Aplica force-directed layout para posicionamento visual.

    Args:
        min_cooccurrence: minimo de co-ocorrencias para criar aresta.
        max_edges: maximo de arestas no grafo.
        db_path: caminho do banco de dados.
        output_path: caminho para salvar o grafo.

    Returns:
        dict com nodes, links e meta (mesmo formato do location_graph).
    """
    conn = get_connection() if db_path is None else sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # --- Total de transacoes ---
    total_transactions = conn.execute(
        "SELECT COUNT(DISTINCT purchase_id) FROM purchase_items"
    ).fetchone()[0]

    if total_transactions == 0:
        conn.close()
        return {"nodes": [], "links": [], "meta": {"error": "no_data"}}

    # --- Contagem por produto ---
    product_counts = {}
    rows = conn.execute(
        "SELECT barcode, name, category, aisle, COUNT(DISTINCT purchase_id) as cnt "
        "FROM purchase_items "
        "GROUP BY barcode"
    ).fetchall()
    product_info = {}
    for r in rows:
        product_counts[r["barcode"]] = r["cnt"]
        product_info[r["barcode"]] = {
            "barcode": r["barcode"],
            "name": r["name"],
            "category": r["category"],
            "aisle": r["aisle"],
            "purchase_count": r["cnt"],
        }

    # --- Co-ocorrencias (pares de produtos na mesma compra) ---
    # Usamos barcode1 < barcode2 para evitar duplicatas
    cooccurrence_rows = conn.execute(
        "SELECT pi1.barcode as b1, pi2.barcode as b2, "
        "       COUNT(DISTINCT pi1.purchase_id) as co_count "
        "FROM purchase_items pi1 "
        "JOIN purchase_items pi2 ON pi1.purchase_id = pi2.purchase_id "
        "WHERE pi1.barcode < pi2.barcode "
        "GROUP BY pi1.barcode, pi2.barcode "
        "HAVING co_count >= ? "
        "ORDER BY co_count DESC "
        "LIMIT ?",
        (min_cooccurrence, max_edges),
    ).fetchall()

    conn.close()

    # --- Montar links ---
    links = []
    node_ids = set()

    for r in cooccurrence_rows:
        b1 = r["b1"]
        b2 = r["b2"]
        co_count = r["co_count"]

        # Support: P(A e B) = co_count / total_transacoes
        support = co_count / total_transactions

        # Confidence: P(B|A) = co_count / count(A)
        conf_ab = co_count / product_counts.get(b1, 1)
        conf_ba = co_count / product_counts.get(b2, 1)

        # Lift: P(A e B) / (P(A) * P(B))
        pa = product_counts.get(b1, 1) / total_transactions
        pb = product_counts.get(b2, 1) / total_transactions
        lift = support / (pa * pb) if (pa * pb) > 0 else 0

        # Strength: usamos co_count pra determinar a espessura visual
        strength = co_count

        links.append({
            "source": b1,
            "target": b2,
            "co_occurrence_count": co_count,
            "support": round(support, 6),
            "confidence_ab": round(conf_ab, 4),
            "confidence_ba": round(conf_ba, 4),
            "lift": round(lift, 4),
            "strength": strength,
        })

        node_ids.add(b1)
        node_ids.add(b2)

    # --- Montar nodes ---
    nodes = []
    for barcode in sorted(node_ids):
        info = product_info.get(barcode, {})
        nodes.append({
            "id": barcode,
            "barcode": barcode,
            "name": info.get("name", barcode),
            "category": info.get("category"),
            "aisle": info.get("aisle"),
            "purchase_count": info.get("purchase_count", 0),
        })

    # --- Force-directed layout ---
    _apply_force_layout(nodes, links)

    # --- Visual distances (baseado em co-ocorrencia inversa) ---
    if links:
        max_co = max(l["co_occurrence_count"] for l in links)
        min_co = min(l["co_occurrence_count"] for l in links)
        co_range = max_co - min_co if max_co != min_co else 1
        for link in links:
            # Mais co-ocorrencia = mais perto visualmente
            ratio = (link["co_occurrence_count"] - min_co) / co_range
            link["visual_distance"] = round(250.0 - ratio * 180.0, 4)

    # --- Payload ---
    graph = {
        "nodes": nodes,
        "links": links,
        "meta": {
            "total_transactions": total_transactions,
            "total_products": len(product_info),
            "node_count": len(nodes),
            "edge_count": len(links),
            "min_cooccurrence": min_cooccurrence,
            "max_edges": max_edges,
            "graph_type": "cooccurrence",
            "description": "Grafo de co-ocorrencia: cada aresta representa "
                           "a frequencia com que dois produtos aparecem juntos "
                           "nas cestas de compra (Negre, 2015, sec. 3.5.2).",
        },
    }

    save_recommendation_graph(graph, output_path)
    graph["meta"]["cache_path"] = str(get_graph_path(output_path))

    return graph


def get_recommendation_graph_link_details(source, target, graph=None):
    """Retorna detalhes de uma aresta especifica do grafo."""
    if graph is None:
        graph = load_recommendation_graph()
    if graph is None:
        return None

    key = tuple(sorted((source, target)))
    for link in graph.get("links", []):
        link_key = tuple(sorted((link["source"], link["target"])))
        if link_key == key:
            node_map = {n["id"]: n for n in graph.get("nodes", [])}
            return {
                "source": source,
                "target": target,
                "source_node": node_map.get(source),
                "target_node": node_map.get(target),
                "link": link,
            }
    return None


def find_connected_products(graph, barcode, top_n=10):
    """Retorna os produtos mais conectados a um barcode no grafo."""
    if not graph or not barcode:
        return []

    connections = []
    for link in graph.get("links", []):
        if link["source"] == barcode:
            connections.append((link["target"], link))
        elif link["target"] == barcode:
            connections.append((link["source"], link))

    connections.sort(key=lambda x: x[1]["co_occurrence_count"], reverse=True)
    return connections[:top_n]


# ---------------------------------------------------------------------------
# FORCE-DIRECTED LAYOUT (mesmo estilo do Joao)
# ---------------------------------------------------------------------------

def _apply_force_layout(nodes, links):
    if not nodes:
        return

    node_ids = [str(n["id"]) for n in nodes]
    positions = _initial_positions(node_ids)
    target_distances = {}

    for link in links:
        s = str(link["source"])
        t = str(link["target"])
        # Mais co-ocorrencia = mais perto
        dist = link.get("visual_distance", 120.0)
        target_distances[(s, t)] = dist

    rng = random.Random(42)

    for _ in range(360):
        # Atracao pelas arestas
        for link in links:
            source = str(link["source"])
            target = str(link["target"])
            sx, sy = positions[source]
            tx, ty = positions[target]
            dx = tx - sx
            dy = ty - sy
            distance = math.hypot(dx, dy) or 0.001
            td = target_distances.get((source, target), 120.0)
            adjustment = (distance - td) * 0.035
            ux = dx / distance
            uy = dy / distance
            positions[source] = (sx + ux * adjustment, sy + uy * adjustment)
            positions[target] = (tx - ux * adjustment, ty - uy * adjustment)

        # Repulsao entre todos os nos
        for i, src in enumerate(node_ids):
            sx, sy = positions[src]
            for tgt in node_ids[i + 1:]:
                tx, ty = positions[tgt]
                dx = tx - sx
                dy = ty - sy
                dist_sq = max(dx * dx + dy * dy, 1.0)
                force = min(80.0 / dist_sq, 0.08)
                jx = rng.uniform(-0.001, 0.001)
                jy = rng.uniform(-0.001, 0.001)
                positions[src] = (positions[src][0] - dx * force + jx,
                                  positions[src][1] - dy * force + jy)
                positions[tgt] = (positions[tgt][0] + dx * force - jx,
                                  positions[tgt][1] + dy * force - jy)

        # Decaimento
        for nid in node_ids:
            x, y = positions[nid]
            positions[nid] = (x * 0.995, y * 0.995)

    for node in nodes:
        x, y = positions[str(node["id"])]
        node["x"] = round(x, 4)
        node["y"] = round(y, 4)


def _initial_positions(node_ids):
    radius = max(120.0, len(node_ids) * 4.0)
    positions = {}
    for i, nid in enumerate(node_ids):
        angle = 2 * math.pi * i / max(len(node_ids), 1)
        positions[nid] = (math.cos(angle) * radius, math.sin(angle) * radius)
    return positions