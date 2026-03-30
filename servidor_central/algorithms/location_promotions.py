from typing import Any, Optional

from servidor_central.schemas import CartResponse, LocationPromotionsResponse, PromotionResponse


def find_location_promotions(
    cart: CartResponse,
    location_result: dict[str, Any],
    all_promotions: Optional[list[PromotionResponse]] = None,
) -> LocationPromotionsResponse:
    # TODO: Implementar o algoritmo de promocoes por localizacao.
    inferred_location = location_result.get("inferred_location") or "Corredor sugerido"
    
    if all_promotions is None:
        all_promotions = []
        
    # Filter promotions by location (aisle)
    promotions = [
        p for p in all_promotions 
        if p.aisle == inferred_location or not p.aisle
    ]

    return LocationPromotionsResponse(
        cart_id=cart.cart_id,
        algorithm_status="not_implemented",
        inferred_location=inferred_location,
        promotions=promotions,
    )
