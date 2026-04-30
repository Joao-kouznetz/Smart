from typing import Any

from servidor_central.algorithms.location_graph import infer_product_position, load_location_graph
from servidor_central.schemas import CartResponse


def infer_location(
    cart: CartResponse,
    *,
    last_barcode: str | None = None,
    graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if graph is None:
        graph = load_location_graph()

    if last_barcode is None and cart.items:
        last_barcode = cart.items[-1].barcode

    position_result = infer_product_position(graph, last_barcode)
    position = position_result.get("position")
    inferred_location = position.get("aisle") if position else None

    return {
        "cart_id": cart.cart_id,
        "algorithm_status": position_result["algorithm_status"],
        "inferred_location": inferred_location,
        "current_product_barcode": position.get("barcode") if position else last_barcode,
        "current_product_name": position.get("name") if position else None,
        "graph_position": position,
        "neighbors": position_result.get("neighbors", []),
    }
