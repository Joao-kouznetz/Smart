from typing import Any

from servidor_central.schemas import CartResponse


def infer_location(cart: CartResponse) -> dict[str, Any]:
    # TODO: Implementar a inferencia de localizacao aproximada do carrinho.
    return {
        "cart_id": cart.cart_id,
        "algorithm_status": "not_implemented",
        "inferred_location": None,
    }
