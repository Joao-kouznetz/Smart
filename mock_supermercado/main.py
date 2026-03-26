from fastapi import FastAPI, Query

from mock_supermercado.data import PRODUCT_TEMPLATE, PROMOTIONS


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
        return [
            {
                "barcode": f"search-{query}-1",
                "name": f"{PRODUCT_TEMPLATE['name']} 1",
                "price": PRODUCT_TEMPLATE["price"],
                "category": PRODUCT_TEMPLATE["category"],
                "aisle": PRODUCT_TEMPLATE["aisle"],
            },
            {
                "barcode": f"search-{query}-2",
                "name": f"{PRODUCT_TEMPLATE['name']} 2",
                "price": PRODUCT_TEMPLATE["price"] + 3,
                "category": PRODUCT_TEMPLATE["category"],
                "aisle": "B2",
            },
        ]

    @app.get("/products/{barcode}")
    def get_product(barcode: str) -> dict[str, str | float]:
        return {
            "barcode": barcode,
            "name": PRODUCT_TEMPLATE["name"],
            "price": PRODUCT_TEMPLATE["price"],
            "category": PRODUCT_TEMPLATE["category"],
            "aisle": PRODUCT_TEMPLATE["aisle"],
        }

    @app.get("/promotions")
    def get_promotions() -> list[dict[str, str | float | None]]:
        return PROMOTIONS

    return app


app = create_app()
