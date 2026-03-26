import csv
from pathlib import Path

from mock_supermercado.data import CATALOG_CSV_PATH


class ProductNotFoundError(Exception):
    pass


def _read_catalog(csv_path: Path | None = None) -> list[dict[str, str | float]]:
    catalog_path = csv_path or CATALOG_CSV_PATH

    with catalog_path.open(mode="r", encoding="utf-8", newline="") as catalog_file:
        reader = csv.DictReader(catalog_file)
        products = []
        for row in reader:
            products.append(
                {
                    "barcode": row["barcode"],
                    "name": row["name"],
                    "price": float(row["price"]),
                    "category": row["category"],
                    "aisle": row["aisle"],
                }
            )
    return products


def get_product_by_barcode(barcode: str, csv_path: Path | None = None) -> dict[str, str | float]:
    for product in _read_catalog(csv_path):
        if product["barcode"] == barcode:
            return product

    raise ProductNotFoundError("Produto nao encontrado no catalogo do mock.")


def search_products(query: str, csv_path: Path | None = None) -> list[dict[str, str | float]]:
    normalized_query = query.strip().lower()
    return [
        product
        for product in _read_catalog(csv_path)
        if normalized_query in str(product["name"]).lower()
    ]
