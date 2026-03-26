import os
import sqlite3

import httpx
import pytest
from fastapi.testclient import TestClient

from mock_supermercado.main import create_app as create_mock_supermercado_app
from servidor_central.clients import supermarket_api
from servidor_central.clients.supermarket_api import SupermarketAPIError, SupermarketAPINotFound
from servidor_central.main import create_app
from servidor_central.schemas import ProductResponse
from servidor_central.services import catalog_service, promotion_service


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test_smart_cart.db"
    monkeypatch.setenv("SMART_CART_DB_PATH", str(db_path))

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_init_db_creates_required_tables(client, monkeypatch):
    db_path = os.getenv("SMART_CART_DB_PATH")

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()

    table_names = {row[0] for row in rows}
    assert {"carts", "cart_items", "cart_interactions"} <= table_names


def test_post_cart_item_creates_cart_and_persists_snapshot(client, monkeypatch):
    def fake_get_product(_: str):
        return ProductResponse(
            barcode="123",
            name="Leite Integral",
            price=7.5,
            category="Laticinios",
            aisle="A3",
        )

    monkeypatch.setattr(catalog_service, "get_product_by_barcode", fake_get_product)

    response = client.post("/cart/cart-1/items", json={"barcode": "123", "quantity": 2})

    assert response.status_code == 201
    payload = response.json()
    assert payload["cart_id"] == "cart-1"
    assert payload["total_items"] == 2
    assert payload["total_amount"] == 15.0
    assert payload["items"][0]["name"] == "Leite Integral"
    assert payload["items"][0]["aisle"] == "A3"


def test_get_cart_returns_existing_items_and_totals(client, monkeypatch):
    def fake_get_product(_: str):
        return ProductResponse(
            barcode="789",
            name="Cafe",
            price=12.3,
            category="Bebidas",
            aisle="B1",
        )

    monkeypatch.setattr(catalog_service, "get_product_by_barcode", fake_get_product)

    client.post("/cart/cart-2/items", json={"barcode": "789", "quantity": 1})
    client.post("/cart/cart-2/items", json={"barcode": "789", "quantity": 3})

    response = client.get("/cart/cart-2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] == 4
    assert payload["total_amount"] == 49.2
    assert len(payload["items"]) == 2


def test_delete_cart_item_removes_target_item(client, monkeypatch):
    def fake_get_product(_: str):
        return ProductResponse(
            barcode="111",
            name="Arroz",
            price=25.0,
            category="Mercearia",
            aisle="C2",
        )

    monkeypatch.setattr(catalog_service, "get_product_by_barcode", fake_get_product)

    created = client.post("/cart/cart-3/items", json={"barcode": "111", "quantity": 1}).json()
    item_id = created["items"][0]["item_id"]

    response = client.delete(f"/cart/cart-3/items/{item_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == []
    assert payload["total_items"] == 0
    assert payload["total_amount"] == 0


def test_get_product_and_search_map_external_results(client, monkeypatch):
    monkeypatch.setattr(
        catalog_service,
        "get_product_by_barcode",
        lambda barcode: ProductResponse(
            barcode=barcode,
            name="Banana",
            price=3.2,
            category="Frutas",
            aisle="F1",
        ),
    )
    monkeypatch.setattr(
        catalog_service,
        "search_products",
        lambda _: [
            ProductResponse(
                barcode="321",
                name="Banana",
                price=3.2,
                category="Frutas",
                aisle="F1",
            )
        ],
    )

    product_response = client.get("/products/321")
    search_response = client.get("/products/search", params={"query": "banana"})

    assert product_response.status_code == 200
    assert product_response.json()["barcode"] == "321"
    assert search_response.status_code == 200
    assert search_response.json()[0]["name"] == "Banana"


def test_external_failures_return_503(client, monkeypatch):
    monkeypatch.setattr(
        catalog_service,
        "search_products",
        lambda _: (_ for _ in ()).throw(SupermarketAPIError("Servico externo indisponivel")),
    )
    monkeypatch.setattr(
        promotion_service,
        "get_promotions",
        lambda: (_ for _ in ()).throw(SupermarketAPIError("Servico externo indisponivel")),
    )

    search_response = client.get("/products/search", params={"query": "cafe"})
    promotions_response = client.get("/promotions")

    assert search_response.status_code == 503
    assert promotions_response.status_code == 503


def test_get_product_not_found_returns_404(client, monkeypatch):
    monkeypatch.setattr(
        catalog_service,
        "get_product_by_barcode",
        lambda _: (_ for _ in ()).throw(SupermarketAPINotFound("Produto nao encontrado")),
    )

    response = client.get("/products/999")

    assert response.status_code == 404


def test_algorithm_endpoints_return_placeholder_payloads(client):
    recommendations_response = client.get("/cart/cart-4/recommendations")
    location_promotions_response = client.get("/cart/cart-4/promotions/location")

    assert recommendations_response.status_code == 200
    assert recommendations_response.json() == {
        "cart_id": "cart-4",
        "algorithm_status": "not_implemented",
        "recommendations": [],
    }

    assert location_promotions_response.status_code == 200
    assert location_promotions_response.json() == {
        "cart_id": "cart-4",
        "algorithm_status": "not_implemented",
        "inferred_location": None,
        "promotions": [],
    }


def test_servidor_central_consumes_mock_supermercado(client, monkeypatch):
    monkeypatch.setenv("BASE_SUPERMARKET_API_URL", "http://mock-supermercado.local")

    mock_app = create_mock_supermercado_app()
    with TestClient(mock_app) as mock_client:
        def fake_request(method, url, params=None, timeout=None):
            parsed_url = httpx.URL(url)
            return mock_client.request(method, parsed_url.path, params=params)

        monkeypatch.setattr(supermarket_api.httpx, "request", fake_request)

        product_response = client.get("/products/qualquer-codigo")
        promotions_response = client.get("/promotions")
        cart_response = client.post(
            "/cart/cart-integracao/items",
            json={"barcode": "codigo-demo", "quantity": 2},
        )

    assert product_response.status_code == 200
    assert product_response.json()["name"] == "Produto Demo Supermercado"

    assert promotions_response.status_code == 200
    assert len(promotions_response.json()) == 2

    assert cart_response.status_code == 201
    assert cart_response.json()["items"][0]["name"] == "Produto Demo Supermercado"
