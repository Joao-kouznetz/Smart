from typing import Any

from servidor_central.schemas import CartResponse, LocationPromotionsResponse, PromotionResponse


def find_location_promotions(
    cart: CartResponse,
    location_result: dict[str, Any],
) -> LocationPromotionsResponse:
    # TODO: Implementar o algoritmo de promocoes por localizacao.
    inferred_location = location_result.get("inferred_location") or "Corredor sugerido"

    return LocationPromotionsResponse(
        cart_id=cart.cart_id,
        algorithm_status="not_implemented",
        inferred_location=inferred_location,
        promotions=[
            PromotionResponse(
                id=f"loc-{cart.cart_id}-1",
                title=f"Oferta proxima de {inferred_location}",
                description="Boilerplate para validar a experiencia de promocoes contextuais no carrinho.",
                product_barcode=None,
                discount_type="percentage",
                discount_value=8.0,
                aisle=inferred_location,
            ),
            PromotionResponse(
                id=f"loc-{cart.cart_id}-2",
                title="Destaque do corredor",
                description="Placeholder de promocao por localizacao enquanto o algoritmo nao existe.",
                product_barcode=None,
                discount_type="fixed",
                discount_value=4.0,
                aisle=inferred_location,
            ),
        ],
    )
