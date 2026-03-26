from fastapi import APIRouter, HTTPException, Query, status

from servidor_central.clients.supermarket_api import (
    SupermarketAPIConfigError,
    SupermarketAPIError,
    SupermarketAPINotFound,
)
from servidor_central.database import get_db_path
from servidor_central.schemas import (
    AddCartItemRequest,
    CartResponse,
    HealthResponse,
    LocationPromotionsResponse,
    ProductResponse,
    PromotionResponse,
    RecommendationResponse,
)
from servidor_central.services import cart_service, catalog_service, promotion_service


router = APIRouter()


def _raise_external_service_error(exc: Exception) -> None:
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=str(exc),
    ) from exc


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", database_path=str(get_db_path()))


@router.get("/products/search", response_model=list[ProductResponse])
def search_products(query: str = Query(..., min_length=1)) -> list[ProductResponse]:
    try:
        return catalog_service.search_products(query)
    except (SupermarketAPIConfigError, SupermarketAPIError) as exc:
        _raise_external_service_error(exc)


@router.get("/products/{barcode}", response_model=ProductResponse)
def get_product(barcode: str) -> ProductResponse:
    try:
        return catalog_service.get_product_by_barcode(barcode)
    except SupermarketAPINotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (SupermarketAPIConfigError, SupermarketAPIError) as exc:
        _raise_external_service_error(exc)


@router.post(
    "/cart/{cart_id}/items",
    response_model=CartResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_cart_item(cart_id: str, payload: AddCartItemRequest) -> CartResponse:
    try:
        return cart_service.add_cart_item(cart_id=cart_id, barcode=payload.barcode, quantity=payload.quantity)
    except SupermarketAPINotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (SupermarketAPIConfigError, SupermarketAPIError) as exc:
        _raise_external_service_error(exc)


@router.get("/cart/{cart_id}", response_model=CartResponse)
def get_cart(cart_id: str) -> CartResponse:
    return cart_service.get_cart(cart_id)


@router.post("/cart/{cart_id}/checkout", response_model=CartResponse)
def checkout_cart(cart_id: str) -> CartResponse:
    return cart_service.checkout_cart(cart_id)


@router.delete("/cart/{cart_id}/items/{item_id}", response_model=CartResponse)
def delete_cart_item(cart_id: str, item_id: int) -> CartResponse:
    try:
        return cart_service.delete_cart_item(cart_id=cart_id, item_id=item_id)
    except cart_service.CartItemNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/promotions", response_model=list[PromotionResponse])
def get_promotions() -> list[PromotionResponse]:
    try:
        return promotion_service.get_promotions()
    except (SupermarketAPIConfigError, SupermarketAPIError) as exc:
        _raise_external_service_error(exc)


@router.get("/cart/{cart_id}/recommendations", response_model=RecommendationResponse)
def get_cart_recommendations(cart_id: str) -> RecommendationResponse:
    return cart_service.get_cart_recommendations(cart_id)


@router.get("/cart/{cart_id}/promotions/location", response_model=LocationPromotionsResponse)
def get_cart_location_promotions(cart_id: str) -> LocationPromotionsResponse:
    return cart_service.get_cart_location_promotions(cart_id)
