from fastapi.testclient import TestClient

from mock_supermercado.catalog_service import search_products
from mock_supermercado.main import create_app


def test_get_product_returns_catalog_product():
    with TestClient(create_app()) as client:
        response = client.get("/products/7891000100091")

    assert response.status_code == 200
    assert response.json() == {
        "barcode": "7891000100091",
        "name": "Requeijão",
        "price": 42.74,
        "category": "Laticínios",
        "aisle": "E2",
    }


def test_get_product_returns_demo_payload():
    with TestClient(create_app()) as client:
        response = client.get("/products/7891000100091")

    assert response.status_code == 200
    assert response.json()["barcode"] == "7891000100091"
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
    assert len(payload) == 1
    assert payload[0]["barcode"] == "7891000100020"


def test_search_products_returns_demo_list():
    with TestClient(create_app()) as client:
        response = client.get("/products/search", params={"query": "pão de forma"})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1


def test_search_products_dedupes_same_name_with_canonical_first_barcode(tmp_path):
    catalog_path = tmp_path / "catalog.csv"
    catalog_path.write_text(
        "\n".join(
            [
                "barcode,name,price,category,aisle",
                "1,Acém,10.0,Carnes,D1",
                "2, Acém ,12.0,Carnes,B1",
                "3,Picanha,20.0,Carnes,F2",
            ]
        ),
        encoding="utf-8",
    )

    payload = search_products("acém", catalog_path)

    assert payload == [
        {
            "barcode": "1",
            "name": "Acém",
            "price": 10.0,
            "category": "Carnes",
            "aisle": "D1",
        }
    ]


def test_search_products_matches_without_accents():
    payload = search_products("acem")

    assert len(payload) == 1
    assert payload[0]["barcode"] == "7891000100051"
    assert payload[0]["name"] == "Acém"


def test_get_promotions_returns_demo_list():
    with TestClient(create_app()) as client:
        response = client.get("/promotions")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 100
    assert payload[0]["id"] == "promo-gen-1"
    assert payload[0]["title"] == "Cenoura Especial 1 kg"
    assert payload[-1]["id"] == "promo-gen-100"
