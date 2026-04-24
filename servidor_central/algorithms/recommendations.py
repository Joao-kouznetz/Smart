from typing import Optional

from servidor_central.algorithms.location_graph import (
    get_connected_links,
    load_location_graph,
)
from servidor_central.schemas import (
    CartResponse,
    PromotionResponse,
    RecommendationResponse,
)

"""
Smart Cart 360° — Algoritmo de Recomendação de Promoções (v2)
==============================================================
>>>>>>> 97f335a (recommendation)

Módulo responsável por gerar recomendações de promoções personalizadas
com base na composição da cesta de compras e no histórico de compras
armazenado no banco de dados.

Abordagem: Market Basket Analysis via co-ocorrência de produtos
    1. Consulta o histórico de compras (purchase_history + purchase_items)
    2. Calcula a frequência de co-ocorrência entre os produtos do carrinho
       atual e todos os outros produtos no histórico
    3. Usa essas frequências para priorizar promoções de produtos que
       são frequentemente comprados junto com os itens da cesta
    4. Combina com fatores de desconto e proximidade para scoring final

Referências:
    - Agrawal & Srikant (1994) — Association Rules / Apriori
    - Negre (2015) — Information and Recommender Systems, Cap. 3.5.2

Autores: [Seu nome aqui]
Projeto: Smart Cart 360° — TCC Insper 2026
"""

import sqlite3
from collections import Counter
from typing import Optional

from servidor_central.database import get_connection
from servidor_central.schemas import (
    CartResponse,
    PromotionResponse,
    RecommendationResponse,
)

# Número máximo de recomendações retornadas ao frontend
MAX_RECOMMENDATIONS = 10


# ---------------------------------------------------------------------------
# 1. MINERAÇÃO DO HISTÓRICO — Co-ocorrência de produtos
# ---------------------------------------------------------------------------


def _get_cooccurrence_scores(
    cart_barcodes: set[str],
    conn: sqlite3.Connection,
) -> dict[str, float]:
    """
    Consulta o histórico de compras e calcula um score de co-ocorrência
    para cada produto que já foi comprado junto com algum dos produtos
    do carrinho atual.

    Lógica:
        1. Para cada produto no carrinho, busca todas as compras que
           continham esse produto
        2. Conta quantas vezes cada OUTRO produto apareceu nessas
           mesmas compras
        3. Normaliza pela frequência total para gerar um score [0, 1]

    Isso é equivalente a calcular:
        P(produto_candidato | produto_no_carrinho)
    para cada par, e agregar sobre todos os produtos do carrinho.

    Returns:
        Dict de barcode → score de co-ocorrência (quanto maior, mais
        frequentemente comprado junto com os itens do carrinho).
    """
    if not cart_barcodes:
        return {}

    # Buscar IDs de compras que contêm algum produto do carrinho
    placeholders = ",".join("?" for _ in cart_barcodes)
    query = f"""
        SELECT DISTINCT purchase_id
        FROM purchase_items
        WHERE barcode IN ({placeholders})
    """
    rows = conn.execute(query, list(cart_barcodes)).fetchall()
    purchase_ids = [row[0] for row in rows]

    if not purchase_ids:
        return {}

    # Buscar todos os produtos dessas compras (excluindo os do carrinho)
    pid_placeholders = ",".join("?" for _ in purchase_ids)
    barcode_placeholders = ",".join("?" for _ in cart_barcodes)
    query = f"""
        SELECT barcode, COUNT(*) as freq
        FROM purchase_items
        WHERE purchase_id IN ({pid_placeholders})
          AND barcode NOT IN ({barcode_placeholders})
        GROUP BY barcode
        ORDER BY freq DESC
    """
    params = list(purchase_ids) + list(cart_barcodes)
    rows = conn.execute(query, params).fetchall()

    if not rows:
        return {}

    # Normalizar: dividir pela frequência máxima para score em [0, 1]
    max_freq = max(row[1] for row in rows)
    scores = {}
    for row in rows:
        scores[row[0]] = row[1] / max_freq

    return scores


def _get_category_cooccurrence(
    cart_categories: set[str],
    conn: sqlite3.Connection,
) -> dict[str, float]:
    """
    Calcula co-ocorrência no nível de CATEGORIA.

    Para cada categoria no carrinho, identifica quais outras categorias
    aparecem frequentemente nas mesmas compras. Isso serve como fallback
    quando um produto específico não tem histórico suficiente.

    Returns:
        Dict de category → score de co-ocorrência normalizado.
    """
    if not cart_categories:
        return {}

    placeholders = ",".join("?" for _ in cart_categories)
    query = f"""
        SELECT pi2.category, COUNT(DISTINCT pi2.purchase_id) as freq
        FROM purchase_items pi1
        JOIN purchase_items pi2 ON pi1.purchase_id = pi2.purchase_id
        WHERE pi1.category IN ({placeholders})
          AND pi2.category NOT IN ({placeholders})
          AND pi2.category IS NOT NULL
          AND pi2.category != ''
        GROUP BY pi2.category
        ORDER BY freq DESC
    """
    params = list(cart_categories) + list(cart_categories)
    rows = conn.execute(query, params).fetchall()

    if not rows:
        return {}

    max_freq = max(row[1] for row in rows)
    return {row[0]: row[1] / max_freq for row in rows}


# ---------------------------------------------------------------------------
# 2. SCORING — cálculo do score de cada promoção candidata
# ---------------------------------------------------------------------------


def _score_promotion(
    promo: PromotionResponse,
    cooccurrence_scores: dict[str, float],
    category_cooccurrence: dict[str, float],
    category_by_barcode: dict[str, str],
    cart_aisles: set[str],
    cart_total: float,
) -> float:
    """
    Calcula um score numérico para uma promoção candidata.

    O score é composto por 3 fatores aditivos:

    1. **Co-ocorrência no histórico** (0-50 pts)
       Baseado em quantas vezes o produto promovido apareceu em compras
       junto com os produtos do carrinho atual. Usa co-ocorrência por
       produto (se disponível) ou por categoria (fallback).

    2. **Valor do desconto relativo** (0-30 pts)
       Promoções com desconto mais atrativo ganham mais pontos.

    3. **Proximidade de localização** (0-20 pts)
       Se a promoção está no mesmo corredor ou zona do cliente.
    """
    score = 0.0
    barcode = promo.product_barcode or ""

    # --- Fator 1: Co-ocorrência (0-50 pts) ---
    if barcode in cooccurrence_scores:
        # Co-ocorrência direta por produto (fonte mais confiável)
        score += 50.0 * cooccurrence_scores[barcode]
    else:
        # Fallback: co-ocorrência por categoria
        promo_category = category_by_barcode.get(barcode, "")
        if promo_category and promo_category in category_cooccurrence:
            # Peso menor porque é menos preciso
            score += 30.0 * category_cooccurrence[promo_category]

    # --- Fator 2: Atratividade do desconto (0-30 pts) ---
    if promo.discount_value and promo.discount_value > 0:
        if promo.discount_type == "percentage":
            score += 30.0 * min(promo.discount_value / 100.0, 1.0)
        elif promo.discount_type == "fixed":
            if cart_total > 0:
                ratio = promo.discount_value / cart_total
                score += 30.0 * min(ratio * 5, 1.0)
            else:
                score += 15.0

    # --- Fator 3: Proximidade de localização (0-20 pts) ---
    if promo.aisle and promo.aisle in cart_aisles:
        score += 20.0
    elif promo.aisle and cart_aisles:
        promo_zone = promo.aisle[0] if promo.aisle else ""
        for aisle in cart_aisles:
            if aisle and aisle[0] == promo_zone:
                score += 10.0
                break

    return round(score, 2)


# ---------------------------------------------------------------------------
# 3. FUNÇÕES AUXILIARES
# ---------------------------------------------------------------------------


def _get_cart_categories(cart: CartResponse) -> set[str]:
    """Extrai o conjunto de categorias presentes na cesta."""
    return {item.category for item in cart.items if item.category}


def _get_cart_barcodes(cart: CartResponse) -> set[str]:
    """Retorna os barcodes dos produtos já presentes no carrinho."""
    return {item.barcode for item in cart.items}


def _get_cart_aisles(cart: CartResponse) -> set[str]:
    """Retorna os corredores dos produtos já escaneados."""
    return {item.aisle for item in cart.items if item.aisle}


# ---------------------------------------------------------------------------
# 4. FUNÇÃO PRINCIPAL — generate_recommendations
# ---------------------------------------------------------------------------


def generate_recommendations(
    cart: CartResponse,
    all_promotions: Optional[list[PromotionResponse]] = None,
    *,
    last_barcode: str | None = None,
    graph: dict | None = None,
) -> RecommendationResponse:
    if not all_promotions:
        all_promotions = []

    if graph is None:
        graph = load_location_graph()

    if last_barcode is None and cart.items:
        last_barcode = cart.items[-1].barcode

    if graph is None:
        return RecommendationResponse(
            cart_id=cart.cart_id,
            algorithm_status="cache_missing",
            recommendations=all_promotions[:20],
        )

    links = get_connected_links(graph, last_barcode)
    if not links:
        return RecommendationResponse(
            cart_id=cart.cart_id,
            algorithm_status=(
                "product_not_in_graph" if last_barcode else "insufficient_data"
            ),
            recommendations=all_promotions[:20],
        )

    nodes_by_id = {node.get("id"): node for node in graph.get("nodes", [])}
    product_rank: dict[str, int] = {}
    aisle_rank: dict[str, int] = {}
    for index, link in enumerate(links):
        neighbor_barcode = (
            link["target"] if link.get("source") == last_barcode else link.get("source")
        )
        product_rank.setdefault(neighbor_barcode, index)
        aisle = nodes_by_id.get(neighbor_barcode, {}).get("aisle")
        if aisle:
            aisle_rank.setdefault(aisle, index)

    def score(promotion: PromotionResponse) -> tuple[int, int, str]:
        barcode_score = product_rank.get(promotion.product_barcode or "", 10_000)
        aisle_score = aisle_rank.get(promotion.aisle or "", 10_000)
        best_score = min(barcode_score, aisle_score)
        if best_score == 10_000 and promotion.aisle is None:
            best_score = 20_000
        return (best_score, barcode_score, promotion.id)

    recommendations = sorted(all_promotions, key=score)[:20]

    return RecommendationResponse(
        cart_id=cart.cart_id,
        algorithm_status="ready",
        recommendations=recommendations,
    )
    """
    Gera recomendações de promoções personalizadas para o carrinho.

    Fluxo do algoritmo:
        1. Extrair contexto da cesta (categorias, barcodes, corredores)
        2. Consultar histórico de compras no banco de dados
        3. Calcular co-ocorrência por produto e por categoria
        4. Filtrar promoções (remover produtos já no carrinho)
        5. Calcular score de cada promoção candidata
        6. Ordenar por score (decrescente) e retornar top N

    Args:
        cart: Estado atual do carrinho (produtos, quantidades, total).
        all_promotions: Lista de todas as promoções disponíveis.

    Returns:
        RecommendationResponse com as promoções recomendadas ordenadas.
    """
    if not all_promotions:
        all_promotions = []

    # --- Carrinho vazio → retorna promoções por maior desconto ---
    if not cart.items:
        sorted_promos = sorted(
            all_promotions,
            key=lambda p: p.discount_value or 0,
            reverse=True,
        )
        return RecommendationResponse(
            cart_id=cart.cart_id,
            algorithm_status="active",
            recommendations=sorted_promos[:MAX_RECOMMENDATIONS],
        )

    # --- Passo 1: Extrair contexto da cesta ---
    cart_barcodes = _get_cart_barcodes(cart)
    cart_categories = _get_cart_categories(cart)
    cart_aisles = _get_cart_aisles(cart)

    # --- Passo 2-3: Consultar histórico e calcular co-ocorrência ---
    conn = get_connection()
    try:
        cooccurrence_scores = _get_cooccurrence_scores(cart_barcodes, conn)
        category_cooccurrence = _get_category_cooccurrence(cart_categories, conn)
    finally:
        conn.close()

    # --- Passo 4: Filtrar promoções ---
    candidates = [
        promo for promo in all_promotions if promo.product_barcode not in cart_barcodes
    ]

    # --- Construir mapa barcode → category ---
    # Usando dados do carrinho + promoções para ter o máximo de cobertura
    category_by_barcode: dict[str, str] = {}
    for item in cart.items:
        if item.category:
            category_by_barcode[item.barcode] = item.category

    # Enriquecer com dados do histórico (se disponível)
    if cooccurrence_scores:
        try:
            conn = get_connection()
            rows = conn.execute(
                "SELECT DISTINCT barcode, category FROM purchase_items WHERE category IS NOT NULL"
            ).fetchall()
            for row in rows:
                category_by_barcode[row[0]] = row[1]
            conn.close()
        except Exception:
            pass  # fallback silencioso

    # --- Passo 5: Calcular scores ---
    scored: list[tuple[float, PromotionResponse]] = []

    for promo in candidates:
        s = _score_promotion(
            promo=promo,
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

    return RecommendationResponse(
        cart_id=cart.cart_id,
        algorithm_status="active",
        recommendations=top_promos,
    )
