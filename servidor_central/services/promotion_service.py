from typing import Any

from servidor_central.clients import supermarket_api
from servidor_central.schemas import PromotionResponse


def _extract_collection(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in ("promotions", "items", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return value

    raise supermarket_api.SupermarketAPIError("Formato invalido recebido da API externa.")


def _normalize_promotion(payload: dict[str, Any]) -> PromotionResponse:
    discount_value = payload.get("discount_value")

    return PromotionResponse(
        id=str(payload["id"]),
        title=str(payload["title"]),
        description=payload.get("description"),
        product_barcode=payload.get("product_barcode"),
        discount_type=payload.get("discount_type"),
        discount_value=float(discount_value) if discount_value is not None else None,
        aisle=payload.get("aisle"),
    )


def get_promotions() -> list[PromotionResponse]:
    payload = supermarket_api.fetch_promotions()
    promotions = _extract_collection(payload)
    return [_normalize_promotion(promotion) for promotion in promotions]
