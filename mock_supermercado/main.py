from fastapi import FastAPI, HTTPException, Query, status

from mock_supermercado.catalog_service import (
    ProductNotFoundError,
    get_product_by_barcode,
    search_products as search_products_in_catalog,
)
from mock_supermercado.data import PROMOTIONS


def create_app() -> FastAPI:
    app = FastAPI(
        title="Mock Supermercado API",
        description="API simulada do sistema externo do supermercado.",
        version="1.0.0",
    )

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/products/search")
    def search_products(query: str = Query(..., min_length=1)) -> list[dict[str, str | float]]:
        return search_products_in_catalog(query)

    @app.get("/products/{barcode}")
    def get_product(barcode: str) -> dict[str, str | float]:
        try:
            return get_product_by_barcode(barcode)
        except ProductNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    @app.get("/promotions")
    def get_promotions() -> list[dict[str, str | float | None]]:
        return PROMOTIONS

    return app


app = create_app()
