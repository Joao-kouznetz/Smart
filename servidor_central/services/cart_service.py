import json
from typing import Any

from servidor_central.algorithms.location_inference import infer_location
from servidor_central.algorithms.location_promotions import find_location_promotions
from servidor_central.algorithms.recommendations import generate_recommendations
from servidor_central.database import get_connection, utc_now_iso
from servidor_central.schemas import (
    CartItemResponse,
    CartResponse,
    LocationPromotionsResponse,
    RecommendationResponse,
)
from servidor_central.services import catalog_service


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
            INSERT INTO carts (id, status, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (cart_id, "active", now, now),
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


def add_cart_item(cart_id: str, barcode: str, quantity: int) -> CartResponse:
    ensure_cart_exists(cart_id)
    product = catalog_service.get_product_by_barcode(barcode)
    now = utc_now_iso()

    with get_connection() as connection:
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
        deleted = connection.execute(
            """
            DELETE FROM cart_items
            WHERE id = ? AND cart_id = ?
            """,
            (item_id, cart_id),
        )

        if deleted.rowcount == 0:
            raise CartItemNotFoundError("Item nao encontrado no carrinho.")

        _touch_cart(connection, cart_id)
        _record_interaction(
            connection,
            cart_id,
            "item_removed",
            payload={"item_id": item_id},
        )

    return get_cart(cart_id)


def get_cart_recommendations(cart_id: str) -> RecommendationResponse:
    cart = get_cart(cart_id)
    return generate_recommendations(cart)


def get_cart_location_promotions(cart_id: str) -> LocationPromotionsResponse:
    cart = get_cart(cart_id)
    location_result = infer_location(cart)
    return find_location_promotions(cart, location_result)
