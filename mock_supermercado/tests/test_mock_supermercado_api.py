from fastapi.testclient import TestClient

from mock_supermercado.main import create_app


def test_get_product_returns_catalog_product():
    with TestClient(create_app()) as client:
        response = client.get("/products/7891000100103")

    assert response.status_code == 200
    assert response.json() == {
        "barcode": "7891000100103",
        "name": "Requeijão",
        "price": 42.39,
        "category": "Laticínios",
        "aisle": "F2",
    }


def test_get_product_returns_demo_payload():
    with TestClient(create_app()) as client:
        response = client.get("/products/7891000100103")

    assert response.status_code == 200
    assert response.json()["barcode"] == "7891000100103"
    assert response.json()["name"] == "Requeijão"


def test_get_product_returns_404_when_barcode_does_not_exist():
    with TestClient(create_app()) as client:
        response = client.get("/products/nao-existe")

    assert response.status_code == 404


def test_search_products_returns_filtered_catalog_items():
    with TestClient(create_app()) as client:
        response = client.get("/products/search", params={"query": "pão de forma"})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert payload[0]["barcode"] == "7891000100020"
    assert payload[1]["barcode"] == "7891000100060"


def test_search_products_returns_demo_list():
    with TestClient(create_app()) as client:
        response = client.get("/products/search", params={"query": "pão de forma"})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2


def test_get_promotions_returns_demo_list():
    with TestClient(create_app()) as client:
        response = client.get("/promotions")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 100
    assert payload[0]["id"] == "promo-gen-1"
    assert payload[0]["title"] == "Cenoura Especial 1 kg"
    assert payload[-1]["id"] == "promo-gen-100"
