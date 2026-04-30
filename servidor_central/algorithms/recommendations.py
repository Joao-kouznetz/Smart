from typing import Optional

from servidor_central.algorithms.location_graph import get_connected_links, load_location_graph
from servidor_central.schemas import CartResponse, PromotionResponse, RecommendationResponse


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
            algorithm_status="product_not_in_graph" if last_barcode else "insufficient_data",
            recommendations=all_promotions[:20],
        )

    nodes_by_id = {node.get("id"): node for node in graph.get("nodes", [])}
    product_rank: dict[str, int] = {}
    aisle_rank: dict[str, int] = {}
    for index, link in enumerate(links):
        neighbor_barcode = link["target"] if link.get("source") == last_barcode else link.get("source")
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
