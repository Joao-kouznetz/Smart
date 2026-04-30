import sqlite3
from datetime import datetime, timedelta, timezone

from servidor_central.algorithms.location_graph import rebuild_location_graph
from servidor_central.database import init_db


def _insert_product(connection, *, cart_id, barcode, name, aisle):
    connection.execute(
        """
        INSERT INTO cart_items (
            cart_id,
            barcode,
            quantity,
            name,
            price,
            category,
            aisle,
            created_at,
            updated_at
        )
        VALUES (?, ?, 1, ?, 1.0, 'Categoria', ?, '2026-04-01T00:00:00+00:00', '2026-04-01T00:00:00+00:00')
        """,
        (cart_id, barcode, name, aisle),
    )


def _insert_scan(connection, *, cart_id, barcode, created_at):
    connection.execute(
        """
        INSERT INTO cart_interactions (cart_id, event_type, barcode, payload_json, created_at)
        VALUES (?, 'item_added', ?, NULL, ?)
        """,
        (cart_id, barcode, created_at.isoformat()),
    )


def test_rebuild_location_graph_filters_start_at_and_cleans_lower_outliers(tmp_path, monkeypatch):
    db_path = tmp_path / "smart_cart.db"
    graph_path = tmp_path / "location_graph.json"
    monkeypatch.setenv("SMART_CART_DB_PATH", str(db_path))
    monkeypatch.setenv("SMART_CART_LOCATION_GRAPH_PATH", str(graph_path))
    init_db()

    base_at = datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)
    with sqlite3.connect(db_path) as connection:
        old_cart_id = "old-cart"
        connection.execute(
            "INSERT INTO carts (id, created_at, updated_at) VALUES (?, ?, ?)",
            (old_cart_id, base_at.isoformat(), base_at.isoformat()),
        )
        _insert_product(connection, cart_id=old_cart_id, barcode="old-a", name="Antigo A", aisle="A1")
        _insert_product(connection, cart_id=old_cart_id, barcode="old-b", name="Antigo B", aisle="A2")
        _insert_scan(connection, cart_id=old_cart_id, barcode="old-a", created_at=base_at)
        _insert_scan(connection, cart_id=old_cart_id, barcode="old-b", created_at=base_at + timedelta(seconds=10))

        for index in range(16):
            cart_id = f"cart-{index}"
            start_at = base_at + timedelta(days=2, minutes=index)
            elapsed = 1 if index == 0 else 10
            connection.execute(
                "INSERT INTO carts (id, created_at, updated_at) VALUES (?, ?, ?)",
                (cart_id, start_at.isoformat(), start_at.isoformat()),
            )
            _insert_product(connection, cart_id=cart_id, barcode="a", name="Produto A", aisle="A1")
            _insert_product(connection, cart_id=cart_id, barcode="b", name="Produto B", aisle="B1")
            _insert_scan(connection, cart_id=cart_id, barcode="a", created_at=start_at)
            _insert_scan(connection, cart_id=cart_id, barcode="b", created_at=start_at + timedelta(seconds=elapsed))

    graph = rebuild_location_graph(start_at="2026-04-02T00:00:00+00:00")

    assert graph_path.exists()
    assert graph["meta"]["event_count"] == 32
    assert graph["meta"]["edge_count"] == 1
    assert graph["meta"]["valid_transition_count"] == 15
    assert graph["meta"]["kept_link_count"] == 1
    assert {node["id"] for node in graph["nodes"]} == {"a", "b"}

    link = graph["links"][0]
    assert link["source"] == "a"
    assert link["target"] == "b"
    assert link["transition_count"] == 15
    assert link["analysis"]["branch"] == "fallback_log_iqr"
    assert link["avg_elapsed_seconds"] == 10
    assert link["analysis"]["weight_seconds"] == 10
    assert link["visual_distance"] > 0


def test_rebuild_location_graph_applies_temporal_decay(tmp_path, monkeypatch):
    db_path = tmp_path / "smart_cart.db"
    monkeypatch.setenv("SMART_CART_DB_PATH", str(db_path))
    init_db()

    base_at = datetime.now(timezone.utc) - timedelta(days=2)
    with sqlite3.connect(db_path) as connection:
        for index in range(16):
            cart_id = f"cart-{index}"
            start_at = base_at + timedelta(minutes=index)
            connection.execute(
                "INSERT INTO carts (id, created_at, updated_at) VALUES (?, ?, ?)",
                (cart_id, start_at.isoformat(), start_at.isoformat()),
            )
            _insert_product(connection, cart_id=cart_id, barcode="a", name="Produto A", aisle="A1")
            _insert_product(connection, cart_id=cart_id, barcode="b", name="Produto B", aisle="B1")
            _insert_scan(connection, cart_id=cart_id, barcode="a", created_at=start_at)
            _insert_scan(connection, cart_id=cart_id, barcode="b", created_at=start_at + timedelta(seconds=10))

    graph = rebuild_location_graph(temporal_decay=True, half_life_days=1, decay_min_weight=0.01)

    assert graph["meta"]["edge_count"] == 1
    link = graph["links"][0]
    assert 0 < link["weighted_transition_count"] < link["transition_count"]
    assert link["analysis"]["branch"] == "fallback_log_iqr"


def test_rebuild_location_graph_uses_median_for_small_links(tmp_path, monkeypatch):
    db_path = tmp_path / "smart_cart.db"
    graph_path = tmp_path / "location_graph.json"
    monkeypatch.setenv("SMART_CART_DB_PATH", str(db_path))
    monkeypatch.setenv("SMART_CART_LOCATION_GRAPH_PATH", str(graph_path))
    init_db()

    base_at = datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)
    with sqlite3.connect(db_path) as connection:
        for index in range(5):
            cart_id = f"cart-{index}"
            start_at = base_at + timedelta(minutes=index)
            connection.execute(
                "INSERT INTO carts (id, created_at, updated_at) VALUES (?, ?, ?)",
                (cart_id, start_at.isoformat(), start_at.isoformat()),
            )
            _insert_product(connection, cart_id=cart_id, barcode="a", name="Produto A", aisle="A1")
            _insert_product(connection, cart_id=cart_id, barcode="b", name="Produto B", aisle="B1")
            _insert_scan(connection, cart_id=cart_id, barcode="a", created_at=start_at)
            _insert_scan(connection, cart_id=cart_id, barcode="b", created_at=start_at + timedelta(seconds=10 + index))

    graph = rebuild_location_graph()

    assert graph["meta"]["median_link_count"] == 1
    link = graph["links"][0]
    assert link["analysis"]["branch"] == "median"
    assert link["avg_elapsed_seconds"] == 12
    assert link["analysis"]["weight_seconds"] == 12


def test_rebuild_location_graph_discards_low_volume_links(tmp_path, monkeypatch):
    db_path = tmp_path / "smart_cart.db"
    monkeypatch.setenv("SMART_CART_DB_PATH", str(db_path))
    init_db()

    base_at = datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)
    with sqlite3.connect(db_path) as connection:
        for index in range(4):
            cart_id = f"cart-{index}"
            start_at = base_at + timedelta(minutes=index)
            connection.execute(
                "INSERT INTO carts (id, created_at, updated_at) VALUES (?, ?, ?)",
                (cart_id, start_at.isoformat(), start_at.isoformat()),
            )
            _insert_product(connection, cart_id=cart_id, barcode="a", name="Produto A", aisle="A1")
            _insert_product(connection, cart_id=cart_id, barcode="b", name="Produto B", aisle="B1")
            _insert_scan(connection, cart_id=cart_id, barcode="a", created_at=start_at)
            _insert_scan(connection, cart_id=cart_id, barcode="b", created_at=start_at + timedelta(seconds=10))

    graph = rebuild_location_graph()

    assert graph["meta"]["edge_count"] == 0
    assert graph["meta"]["discarded_link_count"] == 1


def test_rebuild_location_graph_reports_per_link_analysis(tmp_path, monkeypatch):
    db_path = tmp_path / "smart_cart.db"
    monkeypatch.setenv("SMART_CART_DB_PATH", str(db_path))
    init_db()

    base_at = datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)
    with sqlite3.connect(db_path) as connection:
        for index in range(16):
            cart_id = f"cart-{index}"
            start_at = base_at + timedelta(minutes=index)
            connection.execute(
                "INSERT INTO carts (id, created_at, updated_at) VALUES (?, ?, ?)",
                (cart_id, start_at.isoformat(), start_at.isoformat()),
            )
            _insert_product(connection, cart_id=cart_id, barcode="a", name="Produto A", aisle="A1")
            _insert_product(connection, cart_id=cart_id, barcode="b", name="Produto B", aisle="B1")
            _insert_scan(connection, cart_id=cart_id, barcode="a", created_at=start_at)
            _insert_scan(connection, cart_id=cart_id, barcode="b", created_at=start_at + timedelta(seconds=10 + (index % 2)))

    graph = rebuild_location_graph()

    link = graph["links"][0]
    assert link["analysis"]["branch"] in {"fallback_log_iqr", "kde_bimodal", "kde_unimodal"}
    assert "formula_weight" in link["analysis"]


def test_rebuild_location_graph_merges_bidirectional_links(tmp_path, monkeypatch):
    db_path = tmp_path / "smart_cart.db"
    monkeypatch.setenv("SMART_CART_DB_PATH", str(db_path))
    init_db()

    base_at = datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)
    with sqlite3.connect(db_path) as connection:
        for index in range(20):
            cart_id = f"cart-{index}"
            start_at = base_at + timedelta(minutes=index)
            connection.execute(
                "INSERT INTO carts (id, created_at, updated_at) VALUES (?, ?, ?)",
                (cart_id, start_at.isoformat(), start_at.isoformat()),
            )
            _insert_product(connection, cart_id=cart_id, barcode="az", name="Azeite", aisle="A1")
            _insert_product(connection, cart_id=cart_id, barcode="su", name="Suco", aisle="B1")
            if index % 2 == 0:
                _insert_scan(connection, cart_id=cart_id, barcode="az", created_at=start_at)
                _insert_scan(connection, cart_id=cart_id, barcode="su", created_at=start_at + timedelta(seconds=10))
            else:
                _insert_scan(connection, cart_id=cart_id, barcode="su", created_at=start_at)
                _insert_scan(connection, cart_id=cart_id, barcode="az", created_at=start_at + timedelta(seconds=10))

    graph = rebuild_location_graph()

    assert graph["meta"]["raw_transition_count"] == 20
    assert graph["meta"]["valid_transition_count"] == 20
    assert graph["meta"]["edge_count"] == 1
    assert graph["meta"]["kept_link_count"] == 1
    link = graph["links"][0]
    assert {link["source"], link["target"]} == {"az", "su"}
    assert link["transition_count"] == 20
    assert link["analysis"]["sample_count_initial"] == 20
    assert link["analysis"]["sample_count_final"] == 20
    assert link["analysis"]["branch"] == "fallback_log_iqr"
