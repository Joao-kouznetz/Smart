import json
import sqlite3
from datetime import datetime, timezone

import pytest

from mock_supermercado.simulation.purchase_simulator import (
    WALKING_SPEED_MPS,
    SimulationConfigError,
    distance_between_products,
    populate_simulated_purchases,
)

TEST_LAYOUT = {
    "A1": [
        {
            "barcode": "7891000100008",
            "name": "Presunto Bio 1kg",
            "dist_lateral_1_m": 2.0,
            "dist_lateral_2_m": 18.0,
        },
        {
            "barcode": "7891000100022",
            "name": "Manteiga Fazenda 1L",
            "dist_lateral_1_m": 5.0,
            "dist_lateral_2_m": 15.0,
        },
    ],
    "B1": [
        {
            "barcode": "7891000100017",
            "name": "Óleo Bom Preço 500ml",
            "dist_lateral_1_m": 3.0,
            "dist_lateral_2_m": 17.0,
        },
    ],
}

TEST_PERSONAS = [
    {
        "name": "Persona A",
        "products": [
            {"barcode": "7891000100008", "name": "Presunto Bio 1kg"},
            {"barcode": "7891000100022", "name": "Manteiga Fazenda 1L"},
            {"barcode": "7891000100017", "name": "Óleo Bom Preço 500ml"},
        ],
    },
    {
        "name": "Persona B",
        "products": [
            {"barcode": "7891000100008", "name": "Presunto Bio 1kg"},
            {"barcode": "7891000100008", "name": "Presunto Bio 1kg"},
        ],
    },
]


def test_distance_between_products_in_same_aisle():
    distance = distance_between_products(
        "7891000100008",
        "7891000100022",
        TEST_LAYOUT,
    )

    assert distance == 3.0


def test_distance_between_products_in_different_aisles_uses_average_side_routes():
    distance = distance_between_products(
        "7891000100008",
        "7891000100017",
        TEST_LAYOUT,
        aisle_gap_m=4.0,
    )

    assert distance == 24.0


def test_populate_simulated_purchases_clears_existing_data_and_writes_ordered_events(
    tmp_path,
):
    db_path = tmp_path / "smart_cart.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute("""
            CREATE TABLE carts (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """)
        connection.execute(
            "INSERT INTO carts (id, created_at, updated_at) VALUES ('existing', 'x', 'x')"
        )

    result = populate_simulated_purchases(
        people_count=1,
        supermarket_layout=TEST_LAYOUT,
        personas=[TEST_PERSONAS[0]],
        persona_proportions=[1.0],
        db_path=db_path,
        seed=1,
        start_at=datetime(2026, 4, 29, 9, 0, tzinfo=timezone.utc),
        start_window_hours=0,
    )

    assert result.people_count == 1
    assert result.interaction_count == 3

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        carts = connection.execute("SELECT id FROM carts ORDER BY id").fetchall()
        interactions = connection.execute(
            """
            SELECT cart_id, barcode, payload_json, created_at
            FROM cart_interactions
            WHERE cart_id = ?
            ORDER BY created_at ASC
            """,
            (result.cart_ids[0],),
        ).fetchall()

    assert [row["id"] for row in carts] == [result.cart_ids[0]]
    assert len(interactions) == 3
    assert [row["created_at"] for row in interactions] == sorted(
        row["created_at"] for row in interactions
    )
    assert json.loads(interactions[0]["payload_json"])["persona"] == "Persona A"


def test_populate_simulated_purchases_aggregates_repeated_products(tmp_path):
    result = populate_simulated_purchases(
        people_count=1,
        supermarket_layout=TEST_LAYOUT,
        personas=[TEST_PERSONAS[1]],
        persona_proportions=[1.0],
        db_path=tmp_path / "smart_cart.db",
        seed=2,
        start_at=datetime(2026, 4, 29, 9, 0, tzinfo=timezone.utc),
        start_window_hours=0,
    )

    with sqlite3.connect(tmp_path / "smart_cart.db") as connection:
        connection.row_factory = sqlite3.Row
        item = connection.execute(
            """
            SELECT barcode, quantity
            FROM cart_items
            WHERE cart_id = ?
            """,
            (result.cart_ids[0],),
        ).fetchone()

    assert item["barcode"] == "7891000100008"
    assert item["quantity"] == 2


def test_travel_time_is_distance_divided_by_fixed_walking_speed(tmp_path):
    result = populate_simulated_purchases(
        people_count=1,
        supermarket_layout=TEST_LAYOUT,
        personas=[
            {
                "name": "Persona distancia",
                "products": [
                    {"barcode": "7891000100008", "name": "Presunto Bio 1kg"},
                    {"barcode": "7891000100022", "name": "Manteiga Fazenda 1L"},
                ],
            }
        ],
        persona_proportions=[1.0],
        db_path=tmp_path / "smart_cart.db",
        seed=4,
        start_at=datetime(2026, 4, 29, 9, 0, tzinfo=timezone.utc),
        start_window_hours=0,
    )

    with sqlite3.connect(tmp_path / "smart_cart.db") as connection:
        rows = connection.execute(
            """
            SELECT created_at
            FROM cart_interactions
            WHERE cart_id = ?
            ORDER BY created_at ASC
            """,
            (result.cart_ids[0],),
        ).fetchall()

    first = datetime.fromisoformat(rows[0][0])
    second = datetime.fromisoformat(rows[1][0])
    assert (second - first).total_seconds() == pytest.approx(3.0 / WALKING_SPEED_MPS)


def test_persona_product_name_must_match_catalog(tmp_path):
    invalid_personas = [
        {
            "name": "Invalida",
            "products": [{"barcode": "7891000100008", "name": "Nome errado"}],
        }
    ]

    with pytest.raises(SimulationConfigError, match="Nome divergente"):
        populate_simulated_purchases(
            people_count=1,
            supermarket_layout=TEST_LAYOUT,
            personas=invalid_personas,
            persona_proportions=[1.0],
            db_path=tmp_path / "smart_cart.db",
        )
