import random
from typing import Optional
from servidor_central.schemas import CartResponse, PromotionResponse, RecommendationResponse


def generate_recommendations(
    cart: CartResponse,
    all_promotions: Optional[list[PromotionResponse]] = None,
) -> RecommendationResponse:
    # TODO: Implementar o algoritmo de recomendacao do Smart Cart.
    if not all_promotions:
        all_promotions = []
        
    # Return 20 random promotions or all of them if less than 20
    count = min(20, len(all_promotions))
    recommendations = random.sample(all_promotions, count) if all_promotions else []

    return RecommendationResponse(
        cart_id=cart.cart_id,
        algorithm_status="not_implemented",
        recommendations=recommendations,
    )
