from fastapi.testclient import TestClient

from mock_supermercado.main import create_app


def test_get_product_returns_demo_payload():
    with TestClient(create_app()) as client:
        response = client.get("/products/123456")

    assert response.status_code == 200
    assert response.json() == {
        "barcode": "123456",
        "name": "Produto Demo Supermercado",
        "price": 19.9,
        "category": "Demo",
        "aisle": "A1",
    }


def test_search_products_returns_demo_list():
    with TestClient(create_app()) as client:
        response = client.get("/products/search", params={"query": "leite"})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert payload[0]["barcode"] == "search-leite-1"
    assert payload[1]["aisle"] == "B2"


def test_get_promotions_returns_demo_list():
    with TestClient(create_app()) as client:
        response = client.get("/promotions")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert payload[0]["id"] == "promo-demo-1"
    assert payload[1]["discount_type"] == "fixed"
