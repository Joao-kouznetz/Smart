import json
from typing import Any

from servidor_central.algorithms.location_inference import infer_location
from servidor_central.algorithms.location_graph import find_node, get_nearby_products, load_location_graph
from servidor_central.algorithms.location_promotions import find_location_promotions
from servidor_central.algorithms.recommendations import generate_recommendations
from servidor_central.clients.supermarket_api import SupermarketAPIError
from servidor_central.database import get_connection, utc_now_iso
from servidor_central.schemas import (
    CartItemResponse,
    CartResponse,
    LocationCurrentProductResponse,
    LocationNearbyProductResponse,
    LocationResponse,
    LocationPromotionsResponse,
    RecommendationResponse,
    PromotionResponse,
)
from servidor_central.services import catalog_service, promotion_service


class CartItemNotFoundError(Exception):
    pass


def _row_to_cart_item(row: Any) -> CartItemResponse:
    quantity = int(row["quantity"])
    unit_price = float(row["price"])
    subtotal = round(quantity * unit_price, 2)

    return CartItemResponse(
        item_id=int(row["id"]),
        barcode=str(row["barcode"]),
        name=str(row["name"]),
        quantity=quantity,
        unit_price=unit_price,
        subtotal=subtotal,
        category=row["category"],
        aisle=row["aisle"],
    )


def _touch_cart(connection: Any, cart_id: str) -> None:
    connection.execute(
        """
        UPDATE carts
        SET updated_at = ?
        WHERE id = ?
        """,
        (utc_now_iso(), cart_id),
    )


def _record_interaction(
    connection: Any,
    cart_id: str,
    event_type: str,
    barcode: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO cart_interactions (cart_id, event_type, barcode, payload_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            cart_id,
            event_type,
            barcode,
            json.dumps(payload) if payload is not None else None,
            utc_now_iso(),
        ),
    )


def ensure_cart_exists(cart_id: str) -> None:
    with get_connection() as connection:
        existing = connection.execute(
            "SELECT id FROM carts WHERE id = ?",
            (cart_id,),
        ).fetchone()

        if existing:
            return

        now = utc_now_iso()
        connection.execute(
            """
            INSERT INTO carts (id, created_at, updated_at)
            VALUES (?, ?, ?)
            """,
            (cart_id, now, now),
        )


def get_cart(cart_id: str) -> CartResponse:
    ensure_cart_exists(cart_id)

    with get_connection() as connection:
        cart_row = connection.execute(
            """
            SELECT id, updated_at
            FROM carts
            WHERE id = ?
            """,
            (cart_id,),
        ).fetchone()

        item_rows = connection.execute(
            """
            SELECT id, barcode, quantity, name, price, category, aisle
            FROM cart_items
            WHERE cart_id = ?
            ORDER BY id ASC
            """,
            (cart_id,),
        ).fetchall()

    items = [_row_to_cart_item(row) for row in item_rows]
    total_items = sum(item.quantity for item in items)
    total_amount = round(sum(item.subtotal for item in items), 2)

    return CartResponse(
        cart_id=str(cart_row["id"]),
        items=items,
        total_items=total_items,
        total_amount=total_amount,
        updated_at=str(cart_row["updated_at"]),
    )


def get_last_added_barcode(cart_id: str) -> str | None:
    ensure_cart_exists(cart_id)

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT barcode
            FROM cart_interactions
            WHERE cart_id = ?
              AND event_type = 'item_added'
              AND barcode IS NOT NULL
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (cart_id,),
        ).fetchone()

    return str(row["barcode"]) if row else None


def add_cart_item(cart_id: str, barcode: str, quantity: int) -> CartResponse:
    ensure_cart_exists(cart_id)
    product = catalog_service.get_product_by_barcode(barcode)
    now = utc_now_iso()

    with get_connection() as connection:
        existing_item = connection.execute(
            """
            SELECT id, quantity
            FROM cart_items
            WHERE cart_id = ? AND barcode = ?
            """,
            (cart_id, product.barcode),
        ).fetchone()

        if existing_item:
            updated_quantity = int(existing_item["quantity"]) + quantity
            connection.execute(
                """
                UPDATE cart_items
                SET quantity = ?, name = ?, price = ?, category = ?, aisle = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    updated_quantity,
                    product.name,
                    product.price,
                    product.category,
                    product.aisle,
                    now,
                    int(existing_item["id"]),
                ),
            )
        else:
            connection.execute(
                """
                INSERT INTO cart_items (
                    cart_id,
                    barcode,
                    quantity,
                    name,
                    price,
                    category,
                    aisle,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cart_id,
                    product.barcode,
                    quantity,
                    product.name,
                    product.price,
                    product.category,
                    product.aisle,
                    now,
                    now,
                ),
            )
        _touch_cart(connection, cart_id)
        _record_interaction(
            connection,
            cart_id,
            "item_added",
            barcode=product.barcode,
            payload={"quantity": quantity},
        )

    return get_cart(cart_id)


def delete_cart_item(cart_id: str, item_id: int) -> CartResponse:
    ensure_cart_exists(cart_id)

    with get_connection() as connection:
        existing_item = connection.execute(
            """
            SELECT id, quantity, barcode
            FROM cart_items
            WHERE id = ? AND cart_id = ?
            """,
            (item_id, cart_id),
        ).fetchone()

        if not existing_item:
            raise CartItemNotFoundError("Item nao encontrado no carrinho.")

        current_quantity = int(existing_item["quantity"])
        barcode = str(existing_item["barcode"])

        if current_quantity > 1:
            connection.execute(
                """
                UPDATE cart_items
                SET quantity = ?, updated_at = ?
                WHERE id = ?
                """,
                (current_quantity - 1, utc_now_iso(), item_id),
            )
        else:
            connection.execute(
                """
                DELETE FROM cart_items
                WHERE id = ?
                """,
                (item_id,),
            )

        _touch_cart(connection, cart_id)
        _record_interaction(
            connection,
            cart_id,
            "item_removed",
            barcode=barcode,
            payload={"item_id": item_id, "previous_quantity": current_quantity},
        )

    return get_cart(cart_id)


def get_cart_recommendations(cart_id: str) -> RecommendationResponse:
    cart = get_cart(cart_id)
    try:
        all_products = catalog_service.search_products("")
    except SupermarketAPIError:
        all_products = []
        
    product_recommendations = []
    for p in all_products:
        product_recommendations.append(PromotionResponse(
            id=f"rec-{p.barcode}",
            title=p.name,
            description=f"Recomendado para você: R$ {p.price:.2f}",
            product_barcode=p.barcode,
            discount_type=None,
            discount_value=0.0,
            aisle=p.aisle
        ))

    return generate_recommendations(
        cart,
        product_recommendations,
        last_barcode=get_last_added_barcode(cart_id),
    )


def get_cart_location_promotions(cart_id: str) -> LocationPromotionsResponse:
    cart = get_cart(cart_id)
    try:
        all_promotions = promotion_service.get_promotions()
        all_products = catalog_service.search_products("")
        pmap = {p.barcode: p for p in all_products}
        for promo in all_promotions:
            if promo.product_barcode and promo.product_barcode in pmap:
                promo.title = f"{pmap[promo.product_barcode].name} com promocao"
    except SupermarketAPIError:
        all_promotions = []
        
    location_result = infer_location(cart, last_barcode=get_last_added_barcode(cart_id))
    return find_location_promotions(cart, location_result, all_promotions)


def get_cart_location(cart_id: str, *, limit: int = 10) -> LocationResponse:
    get_cart(cart_id)
    last_barcode = get_last_added_barcode(cart_id)
    graph = load_location_graph()

    if graph is None:
        return LocationResponse(cart_id=cart_id, algorithm_status="cache_missing")

    if not graph.get("links"):
        return LocationResponse(cart_id=cart_id, algorithm_status="insufficient_data")

    if not last_barcode:
        return LocationResponse(cart_id=cart_id, algorithm_status="insufficient_data")

    current_node = find_node(graph, last_barcode)
    if current_node is None:
        return LocationResponse(cart_id=cart_id, algorithm_status="product_not_in_graph")

    current_product = LocationCurrentProductResponse(
        barcode=str(current_node.get("id")),
        name=current_node.get("name"),
        category=current_node.get("category"),
        aisle=current_node.get("aisle"),
        scan_count=current_node.get("scan_count"),
    )
    nearby_products = [
        LocationNearbyProductResponse(**product)
        for product in get_nearby_products(graph, last_barcode, limit=limit)
    ]

    return LocationResponse(
        cart_id=cart_id,
        algorithm_status="ready",
        current_product=current_product,
        nearby_products=nearby_products,
    )


def checkout_cart(cart_id: str) -> CartResponse:
    ensure_cart_exists(cart_id)

    with get_connection() as connection:
        connection.execute(
            """
            DELETE FROM cart_items
            WHERE cart_id = ?
            """,
            (cart_id,),
        )
        _touch_cart(connection, cart_id)
        _record_interaction(connection, cart_id, "checkout")

    return get_cart(cart_id)
