from servidor_central.schemas import CartResponse, RecommendationResponse


def generate_recommendations(cart: CartResponse) -> RecommendationResponse:
    # TODO: Implementar o algoritmo de recomendacao do Smart Cart.
    return RecommendationResponse(
        cart_id=cart.cart_id,
        algorithm_status="not_implemented",
        recommendations=[],
    )
