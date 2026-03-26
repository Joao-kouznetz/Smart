from typing import Any

from servidor_central.schemas import CartResponse, LocationPromotionsResponse


def find_location_promotions(
    cart: CartResponse,
    location_result: dict[str, Any],
) -> LocationPromotionsResponse:
    # TODO: Implementar o algoritmo de promocoes por localizacao.
    return LocationPromotionsResponse(
        cart_id=cart.cart_id,
        algorithm_status="not_implemented",
        inferred_location=location_result.get("inferred_location"),
        promotions=[],
    )
