import json
import sqlite3
from datetime import datetime, timezone

import pytest

from mock_supermercado.simulation.purchase_simulator import (
    BIMODAL_FAST_MEAN_SECONDS,
    SHELF_PICKUP_SECONDS,
    WALKING_SPEED_MPS,
    SimulationConfigError,
    distance_between_products,
    populate_simulated_purchases,
)

TEST_LAYOUT = {
    "A1": [
        {
            "barcode": "7891000100008",
            "name": "Presunto",
            "dist_to_aisle_m": 2.0,
        },
        {
            "barcode": "7891000100022",
            "name": "Manteiga sem sal",
            "dist_to_aisle_m": 5.0,
        },
    ],
    "B1": [
        {
            "barcode": "7891000100017",
            "name": "Óleo de girasol",
            "dist_to_aisle_m": 3.0,
        },
    ],
    "C1": [
        {
            "barcode": "7891000100020",
            "name": "ultima coisa",
            "dist_to_aisle_m": 3.0,
        },
    ],
}

TEST_PERSONAS = [
    {
        "name": "Persona A",
        "products": [
            {"barcode": "7891000100008", "name": "Presunto"},
            {"barcode": "7891000100022", "name": "Manteiga sem sal"},
            {"barcode": "7891000100017", "name": "Óleo de girasol"},
        ],
    },
    {
        "name": "Persona B",
        "products": [
            {"barcode": "7891000100008", "name": "Presunto"},
            {"barcode": "7891000100008", "name": "Presunto"},
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
    )

    assert distance == 7.0


def test_distance_between_products_in_different_number_aisles_adds_cross_aisle_gap():
    layout = {
        "A1": [
            {"barcode": "a", "name": "Produto A", "dist_to_aisle_m": 2.0},
        ],
        "A2": [
            {"barcode": "b", "name": "Produto B", "dist_to_aisle_m": 2.0},
        ],
    }

    distance = distance_between_products("a", "b", layout)

    assert distance == 1.0


def test_distance_between_products_uses_minimum_route_between_rows():
    layout = {
        "A1": [
            {"barcode": "a", "name": "Produto A", "dist_to_aisle_m": 2.0},
        ],
        "B1": [
            {"barcode": "b", "name": "Produto B", "dist_to_aisle_m": 2.0},
        ],
        "B2": [
            {"barcode": "c", "name": "Produto C", "dist_to_aisle_m": 2.0},
        ],
    }

    same_number_distance = distance_between_products("a", "b", layout)
    different_number_distance = distance_between_products("a", "c", layout)

    assert same_number_distance == 6.0
    assert different_number_distance == 7.0


def test_distance_between_products_same_row_same_number_adds_no_gap():
    layout = {
        "A1": [
            {"barcode": "a", "name": "Produto A", "dist_to_aisle_m": 2.0},
        ],
        "B1": [
            {"barcode": "b", "name": "Produto B", "dist_to_aisle_m": 2.0},
        ],
    }

    assert distance_between_products("a", "b", layout) == 6.0


def test_populate_simulated_purchases_preserves_existing_data_by_default_and_writes_ordered_events(
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

    assert [row["id"] for row in carts] == ["existing", result.cart_ids[0]]
    assert len(interactions) == 3
    assert [row["created_at"] for row in interactions] == sorted(
        row["created_at"] for row in interactions
    )
    assert json.loads(interactions[0]["payload_json"])["persona"] == "Persona A"
    assert "existing" in [row["id"] for row in carts]


def test_populate_simulated_purchases_can_clear_existing_data_when_requested(
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
        clear_existing_data=True,
    )

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        carts = connection.execute("SELECT id FROM carts ORDER BY id").fetchall()

    assert result.people_count == 1
    assert [row["id"] for row in carts] == [result.cart_ids[0]]


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


def test_fixed_travel_time_is_distance_speed_plus_shelf_pickup_time(tmp_path):
    result = populate_simulated_purchases(
        people_count=1,
        supermarket_layout=TEST_LAYOUT,
        personas=[
            {
                "name": "Persona distancia",
                "products": [
                    {"barcode": "7891000100008", "name": "Presunto"},
                    {"barcode": "7891000100022", "name": "Manteiga sem sal"},
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
    assert (second - first).total_seconds() == pytest.approx(
        3.0 / WALKING_SPEED_MPS + SHELF_PICKUP_SECONDS
    )


def test_normal_travel_time_distribution_varies_from_fixed_time(tmp_path):
    result = populate_simulated_purchases(
        people_count=1,
        supermarket_layout=TEST_LAYOUT,
        personas=[
            {
                "name": "Persona distancia",
                "products": [
                    {"barcode": "7891000100008", "name": "Presunto"},
                    {"barcode": "7891000100022", "name": "Manteiga sem sal"},
                ],
            }
        ],
        persona_proportions=[1.0],
        db_path=tmp_path / "smart_cart.db",
        seed=4,
        start_at=datetime(2026, 4, 29, 9, 0, tzinfo=timezone.utc),
        start_window_hours=0,
        travel_time_distribution="normal",
    )

    elapsed_seconds = _fetch_elapsed_seconds(
        tmp_path / "smart_cart.db",
        result.cart_ids[0],
    )

    assert elapsed_seconds[0] > 0
    assert elapsed_seconds[0] != pytest.approx(3.0 / WALKING_SPEED_MPS + SHELF_PICKUP_SECONDS)


def test_right_tail_travel_time_distribution_creates_variable_longer_times(tmp_path):
    result = populate_simulated_purchases(
        people_count=20,
        supermarket_layout=TEST_LAYOUT,
        personas=[
            {
                "name": "Persona distancia",
                "products": [
                    {"barcode": "7891000100008", "name": "Presunto"},
                    {"barcode": "7891000100022", "name": "Manteiga sem sal"},
                ],
            }
        ],
        persona_proportions=[1.0],
        db_path=tmp_path / "smart_cart.db",
        seed=7,
        start_at=datetime(2026, 4, 29, 9, 0, tzinfo=timezone.utc),
        start_window_hours=0,
        travel_time_distribution="right-tail",
    )

    elapsed_seconds = [
        elapsed
        for cart_id in result.cart_ids
        for elapsed in _fetch_elapsed_seconds(tmp_path / "smart_cart.db", cart_id)
    ]
    fixed_seconds = 3.0 / WALKING_SPEED_MPS + SHELF_PICKUP_SECONDS

    assert max(elapsed_seconds) > fixed_seconds
    assert len(set(round(elapsed, 3) for elapsed in elapsed_seconds)) > 1


def test_bimodal_travel_time_distribution_mixes_fast_normal_and_right_tail(tmp_path):
    result = populate_simulated_purchases(
        people_count=120,
        supermarket_layout=TEST_LAYOUT,
        personas=[
            {
                "name": "Persona distancia",
                "products": [
                    {"barcode": "7891000100008", "name": "Presunto"},
                    {"barcode": "7891000100022", "name": "Manteiga sem sal"},
                ],
            }
        ],
        persona_proportions=[1.0],
        db_path=tmp_path / "smart_cart.db",
        seed=7,
        start_at=datetime(2026, 4, 29, 9, 0, tzinfo=timezone.utc),
        start_window_hours=0,
        travel_time_distribution="bimodal",
    )

    elapsed_seconds = [
        elapsed
        for cart_id in result.cart_ids
        for elapsed in _fetch_elapsed_seconds(tmp_path / "smart_cart.db", cart_id)
    ]
    fast_group = [elapsed for elapsed in elapsed_seconds if 0.1 <= elapsed <= 0.75]

    assert len(fast_group) >= 20
    assert sum(fast_group) / len(fast_group) == pytest.approx(
        BIMODAL_FAST_MEAN_SECONDS,
        abs=0.06,
    )
    assert any(elapsed > 3.0 for elapsed in elapsed_seconds)


def test_invalid_travel_time_distribution_raises_config_error(tmp_path):
    with pytest.raises(SimulationConfigError, match="travel_time_distribution"):
        populate_simulated_purchases(
            people_count=1,
            supermarket_layout=TEST_LAYOUT,
            personas=[TEST_PERSONAS[0]],
            persona_proportions=[1.0],
            db_path=tmp_path / "smart_cart.db",
            travel_time_distribution="desconhecida",
        )


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


def _fetch_elapsed_seconds(db_path, cart_id):
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT created_at
            FROM cart_interactions
            WHERE cart_id = ?
            ORDER BY created_at ASC
            """,
            (cart_id,),
        ).fetchall()

    timestamps = [datetime.fromisoformat(row[0]) for row in rows]
    return [
        (current - previous).total_seconds()
        for previous, current in zip(timestamps, timestamps[1:])
    ]
