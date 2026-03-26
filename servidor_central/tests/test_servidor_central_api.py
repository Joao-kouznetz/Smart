import os
import sqlite3
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from servidor_central.clients import supermarket_api
from servidor_central.clients.supermarket_api import SupermarketAPIError, SupermarketAPINotFound
from servidor_central.database import init_db
from servidor_central.main import create_app
from servidor_central.schemas import ProductResponse
from servidor_central.services import catalog_service, promotion_service


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test_smart_cart.db"
    monkeypatch.setenv("SMART_CART_DB_PATH", str(db_path))
    monkeypatch.setenv("BASE_SUPERMARKET_API_URL", "http://mock-supermercado.local")

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def _build_json_response(status_code, payload):
    request = httpx.Request("GET", "http://mock-supermercado.local")
    return httpx.Response(status_code=status_code, json=payload, request=request)


@pytest.fixture()
def mock_supermarket_request(monkeypatch):
    catalog = {
        "7891000100103": {
            "barcode": "7891000100103",
            "name": "Leite Integral 1L",
            "price": 5.99,
            "category": "Laticinios",
            "aisle": "A1",
        },
        "7891000100104": {
            "barcode": "7891000100104",
            "name": "Cafe Torrado 500g",
            "price": 18.75,
            "category": "Bebidas",
            "aisle": "B2",
        },
    }

    promotions = [
        {
            "id": "promo-demo-1",
            "title": "Leve 2 pague menos",
            "description": "Promocao ilustrativa para demonstrar a integracao.",
            "product_barcode": "7891000100103",
            "discount_type": "percentage",
            "discount_value": 10.0,
            "aisle": "A1",
        }
    ]

    def fake_request(method, url, params=None, timeout=None):
        parsed_url = httpx.URL(url)

        if method == "GET" and parsed_url.path == "/promotions":
            return _build_json_response(200, promotions)

        if method == "GET" and parsed_url.path == "/products/search":
            query = (params or {}).get("query", "").lower()
            results = [
                product for product in catalog.values() if query in product["name"].lower()
            ]
            return _build_json_response(200, results)

        if method == "GET" and parsed_url.path.startswith("/products/"):
            barcode = parsed_url.path.rsplit("/", 1)[-1]
            product = catalog.get(barcode)
            if product is None:
                return _build_json_response(404, {"detail": "Produto nao encontrado"})
            return _build_json_response(200, product)

        return _build_json_response(500, {"detail": "Requisicao inesperada no mock do teste"})

    monkeypatch.setattr(supermarket_api.httpx, "request", fake_request)
    return fake_request


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


def test_post_cart_item_creates_cart_and_persists_snapshot(client, mock_supermarket_request):
    response = client.post("/cart/cart-1/items", json={"barcode": "7891000100103", "quantity": 2})

    assert response.status_code == 201
    payload = response.json()
    assert payload["cart_id"] == "cart-1"
    assert payload["total_items"] == 2
    assert payload["total_amount"] == 11.98
    assert payload["items"][0]["barcode"] == "7891000100103"
    assert payload["items"][0]["name"] == "Leite Integral 1L"
    assert payload["items"][0]["aisle"] == "A1"


def test_post_cart_item_same_barcode_sums_quantity(client, mock_supermarket_request):
    client.post("/cart/cart-2/items", json={"barcode": "7891000100104", "quantity": 1})
    response = client.post("/cart/cart-2/items", json={"barcode": "7891000100104", "quantity": 3})

    payload = response.json()
    assert payload["total_items"] == 4
    assert payload["total_amount"] == 75.0
    assert len(payload["items"]) == 1
    assert payload["items"][0]["barcode"] == "7891000100104"
    assert payload["items"][0]["quantity"] == 4
    assert payload["items"][0]["subtotal"] == 75.0


def test_get_cart_returns_existing_items_and_totals(client, mock_supermarket_request):
    client.post("/cart/cart-2-view/items", json={"barcode": "7891000100104", "quantity": 1})
    client.post("/cart/cart-2-view/items", json={"barcode": "7891000100104", "quantity": 3})

    response = client.get("/cart/cart-2-view")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] == 4
    assert payload["total_amount"] == 75.0
    assert len(payload["items"]) == 1
    assert payload["items"][0]["barcode"] == "7891000100104"
    assert payload["items"][0]["quantity"] == 4


def test_post_cart_item_invalid_barcode_returns_404_and_does_not_create_item(
    client,
    mock_supermarket_request,
):
    response = client.post("/cart/cart-invalido/items", json={"barcode": "nao-existe", "quantity": 1})

    assert response.status_code == 404

    cart_response = client.get("/cart/cart-invalido")
    assert cart_response.status_code == 200
    assert cart_response.json()["items"] == []


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


def test_checkout_clears_all_cart_items(client, monkeypatch):
    def fake_get_product(_: str):
        return ProductResponse(
            barcode="222",
            name="Macarrao",
            price=8.0,
            category="Mercearia",
            aisle="D4",
        )

    monkeypatch.setattr(catalog_service, "get_product_by_barcode", fake_get_product)

    client.post("/cart/cart-checkout/items", json={"barcode": "222", "quantity": 1})
    client.post("/cart/cart-checkout/items", json={"barcode": "222", "quantity": 2})

    response = client.post("/cart/cart-checkout/checkout")

    assert response.status_code == 200
    payload = response.json()
    assert payload["cart_id"] == "cart-checkout"
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


def test_servidor_central_uses_mocked_http_request_for_catalog(client, mock_supermarket_request):
    product_response = client.get("/products/7891000100103")
    promotions_response = client.get("/promotions")
    cart_response = client.post(
        "/cart/cart-integracao/items",
        json={"barcode": "7891000100104", "quantity": 2},
    )
    search_response = client.get("/products/search", params={"query": "cafe"})

    assert product_response.status_code == 200
    assert product_response.json()["name"] == "Leite Integral 1L"
    assert product_response.json()["price"] == 5.99

    assert promotions_response.status_code == 200
    assert len(promotions_response.json()) == 1

    assert cart_response.status_code == 201
    assert cart_response.json()["items"][0]["name"] == "Cafe Torrado 500g"
    assert cart_response.json()["items"][0]["unit_price"] == 18.75
    assert cart_response.json()["items"][0]["aisle"] == "B2"
    assert search_response.status_code == 200
    assert search_response.json()[0]["barcode"] == "7891000100104"


def test_servidor_central_consumes_mock_supermercado(client, mock_supermarket_request):
    product_response = client.get("/products/7891000100103")
    cart_response = client.post(
        "/cart/cart-integracao-vscode/items",
        json={"barcode": "7891000100104", "quantity": 2},
    )

    assert product_response.status_code == 200
    assert product_response.json()["name"] == "Leite Integral 1L"
    assert cart_response.status_code == 201
    assert cart_response.json()["items"][0]["barcode"] == "7891000100104"
    assert cart_response.json()["items"][0]["quantity"] == 2


def test_post_cart_item_repairs_corrupted_foreign_key_schema(
    tmp_path: Path,
    monkeypatch,
    mock_supermarket_request,
):
    db_path = tmp_path / "corrupted_smart_cart.db"
    monkeypatch.setenv("SMART_CART_DB_PATH", str(db_path))
    monkeypatch.setenv("BASE_SUPERMARKET_API_URL", "http://mock-supermercado.local")

    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE carts (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE cart_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cart_id TEXT NOT NULL,
                barcode TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                category TEXT,
                aisle TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (cart_id) REFERENCES carts_backup (id) ON DELETE CASCADE
            );

            CREATE TABLE cart_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cart_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                barcode TEXT,
                payload_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (cart_id) REFERENCES carts_backup (id) ON DELETE CASCADE
            );

            INSERT INTO carts (id, created_at, updated_at)
            VALUES ('1', '2024-01-01T00:00:00+00:00', '2024-01-01T00:00:00+00:00');
            """
        )

    init_db()

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        cart_item_foreign_keys = connection.execute("PRAGMA foreign_key_list(cart_items)").fetchall()
        cart_interaction_foreign_keys = connection.execute(
            "PRAGMA foreign_key_list(cart_interactions)"
        ).fetchall()

    assert {row["table"] for row in cart_item_foreign_keys} == {"carts"}
    assert {row["table"] for row in cart_interaction_foreign_keys} == {"carts"}

    app = create_app()
    with TestClient(app) as test_client:
        response = test_client.post("/cart/1/items", json={"barcode": "7891000100103", "quantity": 1})

    assert response.status_code == 201
    payload = response.json()
    assert payload["cart_id"] == "1"
    assert payload["items"][0]["barcode"] == "7891000100103"
    assert payload["items"][0]["quantity"] == 1
