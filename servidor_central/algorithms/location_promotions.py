from typing import Any, Optional

from servidor_central.schemas import CartResponse, LocationPromotionsResponse, PromotionResponse


def find_location_promotions(
    cart: CartResponse,
    location_result: dict[str, Any],
    all_promotions: Optional[list[PromotionResponse]] = None,
) -> LocationPromotionsResponse:
    # TODO: Implementar o algoritmo de promocoes por localizacao.
    inferred_location = location_result.get("inferred_location")
    
    if all_promotions is None:
        all_promotions = []

    neighbor_aisles = {
        neighbor.get("aisle")
        for neighbor in location_result.get("neighbors", [])
        if neighbor.get("aisle")
    }
    neighbor_barcodes = {
        neighbor.get("barcode")
        for neighbor in location_result.get("neighbors", [])
        if neighbor.get("barcode")
    }

    promotions = [
        p for p in all_promotions 
        if not p.aisle
        or p.aisle == inferred_location
        or p.aisle in neighbor_aisles
        or p.product_barcode in neighbor_barcodes
    ]

    return LocationPromotionsResponse(
        cart_id=cart.cart_id,
        algorithm_status=location_result.get("algorithm_status", "insufficient_data"),
        inferred_location=inferred_location,
        current_product_barcode=location_result.get("current_product_barcode"),
        current_product_name=location_result.get("current_product_name"),
        graph_position=location_result.get("graph_position"),
        neighbors=location_result.get("neighbors", []),
        promotions=promotions,
    )
