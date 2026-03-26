from typing import Any

from servidor_central.clients import supermarket_api
from servidor_central.schemas import ProductResponse


def _extract_collection(payload: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value

    raise supermarket_api.SupermarketAPIError("Formato invalido recebido da API externa.")


def _normalize_product(payload: dict[str, Any]) -> ProductResponse:
    return ProductResponse(
        barcode=str(payload["barcode"]),
        name=str(payload["name"]),
        price=float(payload["price"]),
        category=payload.get("category"),
        aisle=payload.get("aisle"),
    )


def get_product_by_barcode(barcode: str) -> ProductResponse:
    payload = supermarket_api.fetch_product_by_barcode(barcode)

    if not isinstance(payload, dict):
        raise supermarket_api.SupermarketAPIError("Formato invalido recebido da API externa.")

    return _normalize_product(payload)


def search_products(query: str) -> list[ProductResponse]:
    payload = supermarket_api.search_products(query)
    products = _extract_collection(payload, "items", "products", "results")
    return [_normalize_product(product) for product in products]
