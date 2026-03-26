PRODUCT_TEMPLATE = {
    "name": "Produto Demo Supermercado",
    "price": 19.9,
    "category": "Demo",
    "aisle": "A1",
}


PROMOTIONS = [
    {
        "id": "promo-demo-1",
        "title": "Leve 2 pague menos",
        "description": "Promocao ilustrativa para demonstrar a integracao.",
        "product_barcode": "demo-001",
        "discount_type": "percentage",
        "discount_value": 10.0,
        "aisle": "A1",
    },
    {
        "id": "promo-demo-2",
        "title": "Oferta do corredor",
        "description": "Promocao fixa retornada pelo mock do supermercado.",
        "product_barcode": "demo-002",
        "discount_type": "fixed",
        "discount_value": 5.0,
        "aisle": "B2",
    },
]
