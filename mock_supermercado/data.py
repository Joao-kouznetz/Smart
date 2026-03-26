from pathlib import Path


CATALOG_CSV_PATH = Path(__file__).resolve().parent / "catalog.csv"

PROMOTIONS = [
    {
        "id": "promo-demo-1",
        "title": "Leve 2 pague menos",
        "description": "Promocao ilustrativa para demonstrar a integracao.",
        "product_barcode": "7891000100103",
        "discount_type": "percentage",
        "discount_value": 10.0,
        "aisle": "A1",
    },
    {
        "id": "promo-demo-2",
        "title": "Oferta do corredor",
        "description": "Promocao fixa retornada pelo mock do supermercado.",
        "product_barcode": "7891000100104",
        "discount_type": "fixed",
        "discount_value": 5.0,
        "aisle": "B2",
    },
]
