import os
from typing import Any

import httpx


class SupermarketAPIError(Exception):
    pass


class SupermarketAPIConfigError(SupermarketAPIError):
    pass


class SupermarketAPINotFound(SupermarketAPIError):
    pass


def _get_base_url() -> str:
    base_url = os.getenv("BASE_SUPERMARKET_API_URL")
    if not base_url:
        raise SupermarketAPIConfigError(
            "BASE_SUPERMARKET_API_URL nao configurada para acessar a API externa do supermercado."
        )
    return base_url.rstrip("/")


def _request_json(method: str, path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{_get_base_url()}{path}"

    try:
        response = httpx.request(method=method, url=url, params=params, timeout=5.0)
    except httpx.RequestError as exc:
        raise SupermarketAPIError("Falha ao consultar a API externa do supermercado.") from exc

    if response.status_code == 404:
        raise SupermarketAPINotFound("Recurso nao encontrado na API externa do supermercado.")

    if response.status_code >= 400:
        raise SupermarketAPIError(
            f"API externa do supermercado retornou status {response.status_code}."
        )

    try:
        return response.json()
    except ValueError as exc:
        raise SupermarketAPIError("Resposta invalida da API externa do supermercado.") from exc


def fetch_product_by_barcode(barcode: str) -> Any:
    return _request_json("GET", f"/products/{barcode}")


def search_products(query: str) -> Any:
    return _request_json("GET", "/products/search", params={"query": query})


def fetch_promotions() -> Any:
    return _request_json("GET", "/promotions")
