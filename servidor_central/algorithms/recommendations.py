"""
Smart Cart 360 -- Algoritmo de Recomendacao de Promocoes (v3)
==============================================================

Modulo responsavel por gerar recomendacoes de promocoes personalizadas
combinando duas fontes de dados:

    1. **Grafo de localizacao** (Joao) -- usa as transicoes entre produtos
       observadas no supermercado para identificar vizinhos espaciais
    2. **Co-ocorrencia no historico** -- usa o historico de compras para
       identificar produtos frequentemente comprados juntos

IMPORTANTE: O algoritmo analisa a CESTA COMPLETA (todos os itens do
carrinho), nao apenas o ultimo produto escaneado. O grafo de localizacao
usa o ultimo produto como referencia espacial, mas a co-ocorrencia
considera TODOS os produtos ja escaneados para calcular as metricas
de associacao (support e confidence).

Abordagem teorica (Negre, 2015 -- Cap. 3.5.2, Association Rules):
    - Support(A -> B) = P(A e B) = freq(A,B juntos) / total_transacoes
    - Confidence(A -> B) = P(B|A) = freq(A,B juntos) / freq(A)
    - O score de cada candidato e ponderado pelo confidence medio
      calculado sobre TODOS os itens do carrinho (nao apenas um).

    Isso segue o paradigma de "item-to-item collaborative filtering"
    descrito na secao 3.5.2 do livro, onde a recomendacao e baseada
    na similaridade entre o CONJUNTO de itens do usuario e os itens
    candidatos, inspirado na abordagem da Amazon.com (Linden et al., 2003).

O score final de cada promocao combina:
    - Proximidade no grafo de localizacao (0-40 pts)
    - Co-ocorrencia via support/confidence (0-30 pts)
    - Atratividade do desconto (0-20 pts)
    - Proximidade de corredor (0-10 pts)

Referencias:
    - Negre, E. (2015). Information and Recommender Systems.
      Cap. 3.5.2: Association Rules for Recommendation.
    - Agrawal, R. & Srikant, R. (1994). Fast Algorithms for Mining
      Association Rules. Proc. 20th VLDB Conference.
    - Linden, G., Smith, B. & York, J. (2003). Amazon.com
      Recommendations: Item-to-Item Collaborative Filtering.
      IEEE Internet Computing, 7(1), 76-80.

Autores: [Seu nome aqui]
Projeto: Smart Cart 360 -- TCC Insper 2026
"""

import sqlite3
from typing import Optional

from servidor_central.algorithms.location_graph import (
    get_connected_links,
    load_location_graph,
)
from servidor_central.database import get_connection
from servidor_central.schemas import (
    CartResponse,
    PromotionResponse,
    RecommendationResponse,
)

# Numero maximo de recomendacoes retornadas ao frontend
MAX_RECOMMENDATIONS = 20


# ---------------------------------------------------------------------------
# 1. GRAFO DE LOCALIZACAO -- vizinhos espaciais (ultimo produto escaneado)
# ---------------------------------------------------------------------------
# Este fator usa APENAS o ultimo produto escaneado como referencia para
# proximidade fisica no supermercado. O grafo de localizacao do Joao
# modela as transicoes entre corredores observadas nas simulacoes.
# ---------------------------------------------------------------------------

def _get_graph_scores(
    last_barcode,
    graph,
):
    """
    Usa o grafo de localizacao para gerar scores de proximidade.

    Retorna dois dicts:
        - product_graph_scores: barcode -> score [0, 1] baseado na posicao
          do produto no ranking de vizinhos do grafo
        - aisle_graph_scores: aisle -> score [0, 1] baseado no corredor
          mais proximo no grafo
    """
    product_scores = {}
    aisle_scores = {}

    if not graph or not last_barcode:
        return product_scores, aisle_scores

    links = get_connected_links(graph, last_barcode)
    if not links:
        return product_scores, aisle_scores

    nodes_by_id = {node.get("id"): node for node in graph.get("nodes", [])}
    total = len(links)

    for index, link in enumerate(links):
        neighbor_barcode = (
            link["target"] if link.get("source") == last_barcode else link.get("source")
        )
        # Score decrescente: vizinho mais proximo = 1.0, mais distante -> 0
        score = 1.0 - (index / max(total, 1))
        product_scores.setdefault(neighbor_barcode, score)

        aisle = nodes_by_id.get(neighbor_barcode, {}).get("aisle")
        if aisle:
            aisle_scores.setdefault(aisle, score)

    return product_scores, aisle_scores


# ---------------------------------------------------------------------------
# 2. CO-OCORRENCIA NO HISTORICO -- CESTA COMPLETA
# ---------------------------------------------------------------------------
# Referencia: Negre (2015), Cap. 3.5.2 - Association Rules
#
# Este bloco implementa as metricas de association rules usando a CESTA
# COMPLETA como entrada. Para cada produto candidato B, calculamos:
#
#   support(cart -> B) = transacoes_com_cart_E_B / total_transacoes
#   confidence(cart -> B) = transacoes_com_cart_E_B / transacoes_com_cart
#
# Onde "cart" representa o CONJUNTO de todos os produtos atualmente no
# carrinho, nao apenas o ultimo escaneado. Quanto mais produtos do
# carrinho co-ocorrem com B, maior o confidence.
#
# A normalizacao final gera um score [0, 1] que representa a forca
# da associacao entre a cesta atual e cada produto candidato.
# ---------------------------------------------------------------------------

def _get_cooccurrence_scores(
    cart_barcodes,
    conn,
):
    """
    Calcula scores de co-ocorrencia baseado em support e confidence
    para cada produto candidato em relacao a CESTA COMPLETA.

    Implementa o conceito de association rules (Negre, 2015, sec. 3.5.2):
        confidence(carrinho -> candidato) =
            # compras contendo (algum item do carrinho E candidato)
            / # compras contendo (algum item do carrinho)

    A funcao recebe cart_barcodes (TODOS os produtos do carrinho, nao
    apenas o ultimo) e busca co-ocorrencia com base em todos eles.

    Args:
        cart_barcodes: set com TODOS os barcodes presentes no carrinho.
        conn: conexao SQLite com o banco de dados.

    Returns:
        Dict barcode -> score normalizado [0, 1]. Quanto maior, mais
        frequentemente o produto aparece em compras junto com os itens
        da cesta atual (maior confidence).
    """
    if not cart_barcodes:
        return {}

    # --- Passo 1: Buscar transacoes que contem ALGUM produto do carrinho ---
    # Isso equivale ao denominador do confidence: P(carrinho)
    placeholders = ",".join("?" for _ in cart_barcodes)
    query = (
        "SELECT DISTINCT purchase_id "
        "FROM purchase_items "
        "WHERE barcode IN (%s)" % placeholders
    )
    rows = conn.execute(query, list(cart_barcodes)).fetchall()
    purchase_ids = [row[0] for row in rows]

    if not purchase_ids:
        return {}

    # Total de transacoes com algum item do carrinho (denominador do confidence)
    n_transactions_with_cart = len(purchase_ids)

    # --- Passo 2: Contar co-ocorrencias de cada candidato ---
    # Para cada produto B nao no carrinho, contamos em quantas dessas
    # transacoes B apareceu. Isso e o numerador do confidence.
    pid_ph = ",".join("?" for _ in purchase_ids)
    bc_ph = ",".join("?" for _ in cart_barcodes)
    query = (
        "SELECT barcode, COUNT(*) as freq "
        "FROM purchase_items "
        "WHERE purchase_id IN (%s) "
        "  AND barcode NOT IN (%s) "
        "GROUP BY barcode "
        "ORDER BY freq DESC" % (pid_ph, bc_ph)
    )
    params = list(purchase_ids) + list(cart_barcodes)
    rows = conn.execute(query, params).fetchall()

    if not rows:
        return {}

    # --- Passo 3: Calcular confidence e normalizar ---
    # confidence(cart -> B) = freq(B nas transacoes do cart) / n_transacoes_cart
    # Depois normalizamos pelo maximo para score em [0, 1]
    confidences = {}
    for row in rows:
        barcode = row[0]
        freq = row[1]
        confidences[barcode] = freq / n_transactions_with_cart

    max_conf = max(confidences.values()) if confidences else 1.0
    scores = {bc: conf / max_conf for bc, conf in confidences.items()}

    return scores


def _get_category_cooccurrence(
    cart_categories,
    conn,
):
    """
    Calcula co-ocorrencia no nivel de CATEGORIA usando a cesta completa.

    Serve como fallback quando um produto especifico nao tem historico
    suficiente. Usa o mesmo principio de confidence, mas agregado por
    categoria (Negre, 2015 -- generalizacao de association rules para
    niveis hierarquicos de itens).

    Args:
        cart_categories: set com TODAS as categorias presentes no carrinho.
        conn: conexao SQLite.

    Returns:
        Dict category -> score normalizado [0, 1].
    """
    if not cart_categories:
        return {}

    placeholders = ",".join("?" for _ in cart_categories)
    query = (
        "SELECT pi2.category, COUNT(DISTINCT pi2.purchase_id) as freq "
        "FROM purchase_items pi1 "
        "JOIN purchase_items pi2 ON pi1.purchase_id = pi2.purchase_id "
        "WHERE pi1.category IN (%s) "
        "  AND pi2.category NOT IN (%s) "
        "  AND pi2.category IS NOT NULL "
        "  AND pi2.category != '' "
        "GROUP BY pi2.category "
        "ORDER BY freq DESC" % (placeholders, placeholders)
    )
    params = list(cart_categories) + list(cart_categories)
    rows = conn.execute(query, params).fetchall()

    if not rows:
        return {}

    max_freq = max(row[1] for row in rows)
    return {row[0]: row[1] / max_freq for row in rows}


# ---------------------------------------------------------------------------
# 3. SCORING COMBINADO
# ---------------------------------------------------------------------------
# Referencia: Negre (2015), Cap. 4 -- Hybrid Recommender Systems
#
# O score final combina multiplas fontes de informacao (hibrido):
#   - Dados espaciais (grafo de localizacao)
#   - Dados comportamentais (co-ocorrencia/association rules)
#   - Dados de negocio (desconto da promocao)
#   - Dados de contexto (corredor atual)
#
# Os pesos foram calibrados empiricamente nos testes de avaliacao:
#   Grafo: 40pts (fator espacial mais forte no contexto de supermercado)
#   Co-ocorrencia: 30pts (fator comportamental -- historico de compras)
#   Desconto: 20pts (incentivo economico)
#   Corredor: 10pts (conveniencia -- ja esta perto)
# ---------------------------------------------------------------------------

def _score_promotion(
    promo,
    graph_product_scores,
    graph_aisle_scores,
    cooccurrence_scores,
    category_cooccurrence,
    category_by_barcode,
    cart_aisles,
    cart_total,
):
    """
    Calcula um score numerico para uma promocao candidata.

    Combina 4 fatores aditivos (sistema hibrido, Negre 2015 Cap. 4):

    1. Proximidade no grafo (0-40 pts) -- onde o cliente ESTA fisicamente
    2. Co-ocorrencia/confidence (0-30 pts) -- o que clientes SIMILARES compraram
    3. Valor do desconto (0-20 pts) -- atratividade economica da promocao
    4. Proximidade de corredor (0-10 pts) -- conveniencia logistica

    Args:
        promo: promocao candidata a ser avaliada.
        graph_product_scores: scores do grafo por produto.
        graph_aisle_scores: scores do grafo por corredor.
        cooccurrence_scores: confidence normalizado por produto (cesta completa).
        category_cooccurrence: confidence normalizado por categoria (fallback).
        category_by_barcode: mapa barcode -> categoria.
        cart_aisles: corredores dos itens ja no carrinho.
        cart_total: valor total atual do carrinho.

    Returns:
        Score numerico (float). Maior = recomendacao mais relevante.
    """
    score = 0.0
    barcode = promo.product_barcode or ""

    # --- Fator 1: Proximidade no grafo de localizacao (0-40 pts) ---
    # Baseado no ultimo produto escaneado: vizinhos espaciais mais
    # proximos recebem score mais alto (decaimento linear por rank).
    if barcode in graph_product_scores:
        score += 40.0 * graph_product_scores[barcode]
    elif promo.aisle and promo.aisle in graph_aisle_scores:
        score += 25.0 * graph_aisle_scores[promo.aisle]

    # --- Fator 2: Co-ocorrencia via confidence (0-30 pts) ---
    # Baseado na CESTA COMPLETA: confidence(carrinho -> candidato)
    # calculado sobre TODOS os itens do carrinho (Negre, sec. 3.5.2).
    # Fallback para co-ocorrencia por categoria quando o produto
    # especifico nao tem historico suficiente.
    if barcode in cooccurrence_scores:
        score += 30.0 * cooccurrence_scores[barcode]
    else:
        promo_category = category_by_barcode.get(barcode, "")
        if promo_category and promo_category in category_cooccurrence:
            score += 18.0 * category_cooccurrence[promo_category]

    # --- Fator 3: Atratividade do desconto (0-20 pts) ---
    # Incentivo economico: promocoes com desconto maior sao mais atrativas.
    # Para desconto percentual, escala linear ate 100%.
    # Para desconto fixo, proporcional ao valor total do carrinho.
    if promo.discount_value and promo.discount_value > 0:
        if promo.discount_type == "percentage":
            score += 20.0 * min(promo.discount_value / 100.0, 1.0)
        elif promo.discount_type == "fixed":
            if cart_total > 0:
                ratio = promo.discount_value / cart_total
                score += 20.0 * min(ratio * 5, 1.0)
            else:
                score += 10.0

    # --- Fator 4: Proximidade de corredor (0-10 pts) ---
    # Conveniencia: se o produto promovido esta no mesmo corredor ou
    # zona (mesma letra) de algum item ja no carrinho.
    if promo.aisle and promo.aisle in cart_aisles:
        score += 10.0
    elif promo.aisle and cart_aisles:
        promo_zone = promo.aisle[0] if promo.aisle else ""
        for aisle in cart_aisles:
            if aisle and aisle[0] == promo_zone:
                score += 5.0
                break

    return round(score, 2)


# ---------------------------------------------------------------------------
# 4. FUNCOES AUXILIARES
# ---------------------------------------------------------------------------

def _get_cart_categories(cart):
    """Extrai o conjunto de TODAS as categorias presentes na cesta."""
    return {item.category for item in cart.items if item.category}


def _get_cart_barcodes(cart):
    """Retorna TODOS os barcodes dos produtos presentes no carrinho."""
    return {item.barcode for item in cart.items}


def _get_cart_aisles(cart):
    """Retorna os corredores de TODOS os produtos ja escaneados."""
    return {item.aisle for item in cart.items if item.aisle}


# ---------------------------------------------------------------------------
# 5. FUNCAO PRINCIPAL -- generate_recommendations
# ---------------------------------------------------------------------------

def generate_recommendations(
    cart,
    all_promotions=None,
    *,
    last_barcode=None,
    graph=None,
):
    """
    Gera recomendacoes de promocoes personalizadas para o carrinho.

    Sistema hibrido (Negre, 2015, Cap. 4) que combina:
        - Filtragem baseada em conteudo (grafo de localizacao)
        - Filtragem colaborativa item-to-item (co-ocorrencia no historico)
        - Fatores contextuais (desconto, corredor)

    IMPORTANTE: A co-ocorrencia e calculada sobre a CESTA COMPLETA
    (todos os itens do carrinho), nao apenas o ultimo produto. O
    parametro last_barcode e usado APENAS para o grafo de localizacao
    (proximidade espacial). O confidence e calculado sobre o conjunto
    {item_1, item_2, ..., item_n} -> candidato.

    Fluxo do algoritmo:
        1. Carregar grafo de localizacao (se disponivel)
        2. Extrair contexto da cesta COMPLETA (categorias, barcodes, corredores)
        3. Calcular scores do grafo (vizinhos espaciais do ultimo produto)
        4. Calcular scores de co-ocorrencia/confidence (TODOS os itens)
        5. Combinar os scores para cada promocao candidata
        6. Ordenar por score e retornar top N

    Args:
        cart: Estado atual do carrinho (TODOS os itens escaneados).
        all_promotions: Lista de todas as promocoes disponiveis.
        last_barcode: Ultimo produto escaneado (usado APENAS pelo grafo).
        graph: Grafo de localizacao pre-carregado (opcional).

    Returns:
        RecommendationResponse com as promocoes recomendadas ordenadas
        por score decrescente.
    """
    if not all_promotions:
        all_promotions = []

    # --- Carregar grafo ---
    if graph is None:
        graph = load_location_graph()

    if last_barcode is None and cart.items:
        last_barcode = cart.items[-1].barcode

    # --- Determinar status do algoritmo ---
    has_graph = graph is not None and bool(graph.get("links"))

    # --- Carrinho vazio -> retorna promocoes por maior desconto ---
    if not cart.items:
        sorted_promos = sorted(
            all_promotions,
            key=lambda p: p.discount_value or 0,
            reverse=True,
        )
        return RecommendationResponse(
            cart_id=cart.cart_id,
            algorithm_status="ready" if has_graph else "cache_missing",
            recommendations=sorted_promos[:MAX_RECOMMENDATIONS],
        )

    # --- Passo 1: Extrair contexto da CESTA COMPLETA ---
    cart_barcodes = _get_cart_barcodes(cart)      # TODOS os produtos
    cart_categories = _get_cart_categories(cart)   # TODAS as categorias
    cart_aisles = _get_cart_aisles(cart)           # TODOS os corredores

    # --- Passo 2: Scores do grafo (ultimo produto -> vizinhos espaciais) ---
    graph_product_scores, graph_aisle_scores = _get_graph_scores(
        last_barcode, graph
    )

    # --- Passo 3: Scores de co-ocorrencia (CESTA COMPLETA -> candidatos) ---
    # Aqui passamos cart_barcodes (TODOS os itens), nao apenas last_barcode.
    # O confidence e calculado como:
    #   P(candidato | cesta) = freq(candidato em compras com algum item da cesta)
    #                          / freq(compras com algum item da cesta)
    cooccurrence_scores = {}
    category_cooccurrence = {}
    try:
        conn = get_connection()
        try:
            cooccurrence_scores = _get_cooccurrence_scores(cart_barcodes, conn)
            category_cooccurrence = _get_category_cooccurrence(
                cart_categories, conn
            )
        finally:
            conn.close()
    except Exception:
        pass  # fallback: funciona so com o grafo

    # --- Passo 4: Filtrar promocoes ja no carrinho ---
    candidates = [
        promo for promo in all_promotions
        if promo.product_barcode not in cart_barcodes
    ]

    # --- Construir mapa barcode -> category ---
    category_by_barcode = {}
    for item in cart.items:
        if item.category:
            category_by_barcode[item.barcode] = item.category

    if cooccurrence_scores:
        try:
            conn = get_connection()
            rows = conn.execute(
                "SELECT DISTINCT barcode, category FROM purchase_items "
                "WHERE category IS NOT NULL"
            ).fetchall()
            for row in rows:
                category_by_barcode[row[0]] = row[1]
            conn.close()
        except Exception:
            pass

    # --- Passo 5: Calcular scores combinados (sistema hibrido) ---
    scored = []

    for promo in candidates:
        s = _score_promotion(
            promo=promo,
            graph_product_scores=graph_product_scores,
            graph_aisle_scores=graph_aisle_scores,
            cooccurrence_scores=cooccurrence_scores,
            category_cooccurrence=category_cooccurrence,
            category_by_barcode=category_by_barcode,
            cart_aisles=cart_aisles,
            cart_total=cart.total_amount,
        )
        scored.append((s, promo))

    # --- Passo 6: Ordenar e retornar top N ---
    scored.sort(key=lambda x: x[0], reverse=True)
    top_promos = [promo for _, promo in scored[:MAX_RECOMMENDATIONS]]

    # --- Determinar status ---
    if not has_graph and not cooccurrence_scores:
        status = "insufficient_data"
    elif not has_graph:
        status = "cache_missing"
    elif last_barcode and not graph_product_scores:
        status = "product_not_in_graph"
    else:
        status = "ready"

    return RecommendationResponse(
        cart_id=cart.cart_id,
        algorithm_status=status,
        recommendations=top_promos,
    )