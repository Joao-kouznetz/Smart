import sqlite3
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from servidor_central.algorithms.location_graph import (
    _apply_corridor_allocation,
    get_nearby_products,
    get_location_graph_link_details,
    rebuild_location_graph,
)
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


def test_corridor_allocation_groups_products_by_graph_distance(monkeypatch):
    monkeypatch.setenv("SMART_CART_CORRIDOR_COUNT", "2")
    nodes = [
        {"id": "a", "name": "Produto A", "aisle": "A1"},
        {"id": "b", "name": "Produto B", "aisle": "A1"},
        {"id": "c", "name": "Produto C", "aisle": "B1"},
        {"id": "d", "name": "Produto D", "aisle": "B1"},
    ]
    links = [
        {"source": "a", "target": "b", "avg_elapsed_seconds": 8.0},
        {"source": "c", "target": "d", "avg_elapsed_seconds": 8.0},
        {"source": "a", "target": "c", "avg_elapsed_seconds": 2.0},
        {"source": "a", "target": "d", "avg_elapsed_seconds": 2.0},
        {"source": "b", "target": "c", "avg_elapsed_seconds": 2.0},
        {"source": "b", "target": "d", "avg_elapsed_seconds": 2.0},
    ]

    meta = _apply_corridor_allocation(nodes, links)

    assert meta["allocated_corridor_count"] == 2
    assert meta["allocated_corridor_method"] == "short_edge_bipartite_graph"
    assert next(node for node in nodes if node["id"] == "a")["allocated_corridor"] == next(
        node for node in nodes if node["id"] == "b"
    )["allocated_corridor"]
    assert next(node for node in nodes if node["id"] == "c")["allocated_corridor"] == next(
        node for node in nodes if node["id"] == "d"
    )["allocated_corridor"]


def test_nearby_products_prioritize_same_estimated_corridor_neighbors():
    graph = {
        "nodes": [
            {"id": "a", "name": "Produto A", "aisle": "A1", "allocated_corridor": "C01"},
            {"id": "b", "name": "Produto B", "aisle": "A1", "allocated_corridor": "C01"},
            {"id": "c", "name": "Produto C", "aisle": "B1", "allocated_corridor": "C02"},
        ],
        "links": [
            {"source": "a", "target": "b", "avg_elapsed_seconds": 2.0},
            {"source": "b", "target": "c", "avg_elapsed_seconds": 1.0},
        ],
    }

    assert [item["barcode"] for item in get_nearby_products(graph, "b", limit=2)] == ["a", "c"]


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


def test_rebuild_location_graph_falls_back_when_kde_samples_have_no_variance(tmp_path, monkeypatch):
    db_path = tmp_path / "smart_cart.db"
    monkeypatch.setenv("SMART_CART_DB_PATH", str(db_path))
    init_db()

    base_at = datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)
    with sqlite3.connect(db_path) as connection:
        for index in range(50):
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

    assert graph["meta"]["edge_count"] == 1
    link = graph["links"][0]
    assert link["transition_count"] == 50
    assert link["avg_elapsed_seconds"] == 10
    assert link["analysis"]["branch"] == "kde_percentile_iqr_fallback"
    assert link["analysis"]["sample_count_final"] == 50


def test_rebuild_location_graph_uses_kde_valley_between_bimodal_peaks(tmp_path, monkeypatch):
    db_path = tmp_path / "smart_cart.db"
    monkeypatch.setenv("SMART_CART_DB_PATH", str(db_path))
    init_db()

    base_at = datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)
    fast_durations = [0.24, 0.27, 0.30, 0.33, 0.36] * 12
    slow_durations = [7.2, 7.6, 8.0, 8.4, 8.8] * 12
    with sqlite3.connect(db_path) as connection:
        for index, elapsed in enumerate(fast_durations + slow_durations):
            cart_id = f"cart-{index}"
            start_at = base_at + timedelta(minutes=index)
            connection.execute(
                "INSERT INTO carts (id, created_at, updated_at) VALUES (?, ?, ?)",
                (cart_id, start_at.isoformat(), start_at.isoformat()),
            )
            _insert_product(connection, cart_id=cart_id, barcode="a", name="Produto A", aisle="A1")
            _insert_product(connection, cart_id=cart_id, barcode="b", name="Produto B", aisle="B1")
            _insert_scan(connection, cart_id=cart_id, barcode="a", created_at=start_at)
            _insert_scan(connection, cart_id=cart_id, barcode="b", created_at=start_at + timedelta(seconds=elapsed))

    graph = rebuild_location_graph()

    link = graph["links"][0]
    lower_threshold = link["analysis"]["lower_threshold_seconds"]
    assert link["analysis"]["branch"] == "kde_bimodal"
    assert lower_threshold is not None
    assert 0.5 < lower_threshold < 7.0
    assert link["analysis"]["discarded_after_lower_threshold"] == len(fast_durations)


def test_rebuild_location_graph_dependency_fallback_can_use_kde_valley(tmp_path, monkeypatch):
    db_path = tmp_path / "smart_cart.db"
    monkeypatch.setenv("SMART_CART_DB_PATH", str(db_path))
    init_db()

    base_at = datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)
    fast_durations = [0.14, 0.22, 0.30, 0.38, 0.46] * 12
    slow_durations = [7.2, 7.6, 8.0, 8.4, 8.8] * 12
    with sqlite3.connect(db_path) as connection:
        for index, elapsed in enumerate(fast_durations + slow_durations):
            cart_id = f"cart-{index}"
            start_at = base_at + timedelta(minutes=index)
            connection.execute(
                "INSERT INTO carts (id, created_at, updated_at) VALUES (?, ?, ?)",
                (cart_id, start_at.isoformat(), start_at.isoformat()),
            )
            _insert_product(connection, cart_id=cart_id, barcode="a", name="Produto A", aisle="A1")
            _insert_product(connection, cart_id=cart_id, barcode="b", name="Produto B", aisle="B1")
            _insert_scan(connection, cart_id=cart_id, barcode="a", created_at=start_at)
            _insert_scan(connection, cart_id=cart_id, barcode="b", created_at=start_at + timedelta(seconds=elapsed))

    original_import = __import__

    def raise_for_diptest(name, *args, **kwargs):
        if name == "diptest":
            raise ImportError("diptest indisponivel")
        return original_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=raise_for_diptest):
        graph = rebuild_location_graph()

    link = graph["links"][0]
    lower_threshold = link["analysis"]["lower_threshold_seconds"]
    assert link["analysis"]["branch"] == "kde_bimodal_dependency_fallback"
    assert lower_threshold is not None
    assert 0.5 < lower_threshold < 7.0
    assert link["analysis"]["discarded_after_lower_threshold"] == len(fast_durations)


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


def test_get_location_graph_link_details_is_orientation_agnostic(tmp_path, monkeypatch):
    db_path = tmp_path / "smart_cart.db"
    graph_path = tmp_path / "location_graph.json"
    monkeypatch.setenv("SMART_CART_DB_PATH", str(db_path))
    monkeypatch.setenv("SMART_CART_LOCATION_GRAPH_PATH", str(graph_path))
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
            connection.execute(
                """
                INSERT INTO cart_items (
                    cart_id, barcode, quantity, name, price, category, aisle, created_at, updated_at
                ) VALUES (?, ?, 1, ?, 1.0, 'Categoria', 'A1', ?, ?)
                """,
                (cart_id, "az", "Azeite", start_at.isoformat(), start_at.isoformat()),
            )
            connection.execute(
                """
                INSERT INTO cart_items (
                    cart_id, barcode, quantity, name, price, category, aisle, created_at, updated_at
                ) VALUES (?, ?, 1, ?, 1.0, 'Categoria', 'B1', ?, ?)
                """,
                (cart_id, "su", "Suco", start_at.isoformat(), start_at.isoformat()),
            )
            connection.execute(
                "INSERT INTO cart_interactions (cart_id, event_type, barcode, payload_json, created_at) VALUES (?, 'item_added', 'az', NULL, ?)",
                (cart_id, start_at.isoformat()),
            )
            connection.execute(
                "INSERT INTO cart_interactions (cart_id, event_type, barcode, payload_json, created_at) VALUES (?, 'item_added', 'su', NULL, ?)",
                (cart_id, (start_at + timedelta(seconds=10)).isoformat()),
            )

    graph = rebuild_location_graph()
    details_forward = get_location_graph_link_details("az", "su", graph=graph)
    details_reverse = get_location_graph_link_details("su", "az", graph=graph)

    assert details_forward is not None
    assert details_reverse is not None
    assert details_forward["link"]["avg_elapsed_seconds"] == details_reverse["link"]["avg_elapsed_seconds"]
