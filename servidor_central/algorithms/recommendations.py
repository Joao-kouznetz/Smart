from servidor_central.schemas import CartResponse, PromotionResponse, RecommendationResponse


def generate_recommendations(cart: CartResponse) -> RecommendationResponse:
    # TODO: Implementar o algoritmo de recomendacao do Smart Cart.
    lead_item = cart.items[0] if cart.items else None
    lead_name = lead_item.name if lead_item else "sua compra"
    lead_barcode = lead_item.barcode if lead_item else None

    return RecommendationResponse(
        cart_id=cart.cart_id,
        algorithm_status="not_implemented",
        recommendations=[
            PromotionResponse(
                id=f"rec-{cart.cart_id}-combo",
                title=f"Combine com {lead_name}",
                description="Boilerplate de recomendacao para demonstrar a interface touch.",
                product_barcode=lead_barcode,
                discount_type="percentage",
                discount_value=12.0,
                aisle="A1",
            ),
            PromotionResponse(
                id=f"rec-{cart.cart_id}-economia",
                title="Oferta personalizada do carrinho",
                description="Placeholder retornado enquanto o algoritmo real ainda nao foi implementado.",
                product_barcode=None,
                discount_type="fixed",
                discount_value=7.0,
                aisle="B2",
            ),
        ],
    )
