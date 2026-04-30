import json
import math
import os
import random
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from servidor_central.database import get_connection, get_db_path


DEFAULT_GRAPH_FILENAME = "location_graph.json"
DEFAULT_HALF_LIFE_DAYS = 30.0
DEFAULT_DECAY_MIN_WEIGHT = 0.01
MIN_RAW_EDGE_SAMPLES = 15
MIN_CLEAN_EDGE_SAMPLES = 10


@dataclass(frozen=True)
class TransitionSample:
    source: str
    target: str
    elapsed_seconds: float
    transition_at: datetime
    weight: float


def get_graph_path(path: Path | str | None = None) -> Path:
    if path is not None:
        return Path(path)

    configured_path = os.getenv("SMART_CART_LOCATION_GRAPH_PATH")
    if configured_path:
        return Path(configured_path)

    return get_db_path().resolve().parent / DEFAULT_GRAPH_FILENAME


def load_location_graph(path: Path | str | None = None) -> dict[str, Any] | None:
    graph_path = get_graph_path(path)
    if not graph_path.exists():
        return None

    with graph_path.open("r", encoding="utf-8") as graph_file:
        return json.load(graph_file)


def save_location_graph(graph: dict[str, Any], path: Path | str | None = None) -> Path:
    graph_path = get_graph_path(path)
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    with graph_path.open("w", encoding="utf-8") as graph_file:
        json.dump(graph, graph_file, ensure_ascii=False, indent=2)
        graph_file.write("\n")
    return graph_path


def rebuild_location_graph(
    *,
    db_path: Path | str | None = None,
    output_path: Path | str | None = None,
    start_at: str | None = None,
    temporal_decay: bool = False,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
    decay_min_weight: float = DEFAULT_DECAY_MIN_WEIGHT,
) -> dict[str, Any]:
    if half_life_days <= 0:
        raise ValueError("half_life_days deve ser maior que zero.")
    if decay_min_weight < 0:
        raise ValueError("decay_min_weight deve ser maior ou igual a zero.")

    with _open_connection(db_path) as connection:
        rows = _fetch_scan_events(connection, start_at=start_at)
        product_map = _fetch_product_snapshots(connection)

    trained_at = datetime.now(timezone.utc)
    samples = _build_transition_samples(
        rows,
        trained_at=trained_at,
        temporal_decay=temporal_decay,
        half_life_days=half_life_days,
        decay_min_weight=decay_min_weight,
    )
    cleaned_edges, outlier_meta = _clean_transition_samples(samples)
    graph = _build_graph_payload(
        rows=rows,
        product_map=product_map,
        samples=samples,
        cleaned_edges=cleaned_edges,
        outlier_meta=outlier_meta,
        trained_at=trained_at,
        start_at=start_at,
        temporal_decay=temporal_decay,
        half_life_days=half_life_days,
        decay_min_weight=decay_min_weight,
    )
    graph["meta"]["cache_path"] = str(save_location_graph(graph, output_path))
    return graph


def find_node(graph: dict[str, Any] | None, barcode: str | None) -> dict[str, Any] | None:
    if not graph or not barcode:
        return None
    for node in graph.get("nodes", []):
        if node.get("id") == barcode:
            return node
    return None


def get_connected_links(graph: dict[str, Any] | None, barcode: str | None) -> list[dict[str, Any]]:
    if not graph or not barcode:
        return []

    links = [
        link
        for link in graph.get("links", [])
        if link.get("source") == barcode or link.get("target") == barcode
    ]
    return sorted(
        links,
        key=lambda link: (
            -float(link.get("strength") or 0),
            float(link.get("avg_elapsed_seconds") or math.inf),
        ),
    )


def infer_product_position(graph: dict[str, Any] | None, barcode: str | None) -> dict[str, Any]:
    if graph is None:
        return {"algorithm_status": "cache_missing", "position": None, "neighbors": []}

    if not graph.get("links"):
        return {"algorithm_status": "insufficient_data", "position": None, "neighbors": []}

    node = find_node(graph, barcode)
    if node is None:
        return {"algorithm_status": "product_not_in_graph", "position": None, "neighbors": []}

    neighbors = []
    nodes_by_id = {item.get("id"): item for item in graph.get("nodes", [])}
    for link in get_connected_links(graph, barcode)[:10]:
        neighbor_id = link["target"] if link.get("source") == barcode else link.get("source")
        neighbor_node = nodes_by_id.get(neighbor_id, {})
        neighbors.append(
            {
                "barcode": neighbor_id,
                "name": neighbor_node.get("name"),
                "aisle": neighbor_node.get("aisle"),
                "x": neighbor_node.get("x"),
                "y": neighbor_node.get("y"),
                "avg_elapsed_seconds": link.get("avg_elapsed_seconds"),
                "transition_count": link.get("transition_count"),
                "strength": link.get("strength"),
            }
        )

    return {
        "algorithm_status": "ready",
        "position": {
            "barcode": node.get("id"),
            "name": node.get("name"),
            "category": node.get("category"),
            "aisle": node.get("aisle"),
            "x": node.get("x"),
            "y": node.get("y"),
            "scan_count": node.get("scan_count"),
        },
        "neighbors": neighbors,
    }


def _open_connection(db_path: Path | str | None) -> sqlite3.Connection:
    if db_path is None:
        return get_connection()

    connection = sqlite3.connect(db_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def _fetch_scan_events(connection: sqlite3.Connection, *, start_at: str | None) -> list[dict[str, Any]]:
    params: list[Any] = []
    start_clause = ""
    if start_at:
        start_clause = "AND created_at >= ?"
        params.append(start_at)

    rows = connection.execute(
        f"""
        SELECT id, cart_id, barcode, created_at
        FROM cart_interactions
        WHERE event_type = 'item_added'
          AND barcode IS NOT NULL
          {start_clause}
        ORDER BY cart_id ASC, created_at ASC, id ASC
        """,
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def _fetch_product_snapshots(connection: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT barcode, name, category, aisle, MAX(updated_at) AS updated_at, SUM(quantity) AS quantity_sum
        FROM cart_items
        GROUP BY barcode, name, category, aisle
        """
    ).fetchall()

    product_map: dict[str, dict[str, Any]] = {}
    for row in rows:
        barcode = str(row["barcode"])
        current = product_map.get(barcode)
        if current is None or str(row["updated_at"]) > str(current.get("updated_at", "")):
            product_map[barcode] = dict(row)
    return product_map


def _parse_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _build_transition_samples(
    rows: list[dict[str, Any]],
    *,
    trained_at: datetime,
    temporal_decay: bool,
    half_life_days: float,
    decay_min_weight: float,
) -> list[TransitionSample]:
    by_cart: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_cart[str(row["cart_id"])].append(row)

    samples: list[TransitionSample] = []
    for cart_rows in by_cart.values():
        for previous, current in zip(cart_rows, cart_rows[1:]):
            source = str(previous["barcode"])
            target = str(current["barcode"])
            if source == target:
                continue

            previous_at = _parse_datetime(str(previous["created_at"]))
            current_at = _parse_datetime(str(current["created_at"]))
            if previous_at is None or current_at is None:
                continue

            elapsed_seconds = (current_at - previous_at).total_seconds()
            if elapsed_seconds <= 0:
                continue

            weight = 1.0
            if temporal_decay:
                age_days = max((trained_at - current_at).total_seconds() / 86400.0, 0.0)
                weight = 0.5 ** (age_days / half_life_days)
                if weight < decay_min_weight:
                    continue

            samples.append(
                TransitionSample(
                    source=source,
                    target=target,
                    elapsed_seconds=elapsed_seconds,
                    transition_at=current_at,
                    weight=weight,
                )
            )
    return samples


def _clean_transition_samples(
    samples: list[TransitionSample],
) -> tuple[dict[tuple[str, str], list[TransitionSample]], dict[str, Any]]:
    durations = [sample.elapsed_seconds for sample in samples]
    lower_threshold, outlier_meta = _calibrate_lower_threshold(durations)

    grouped: dict[tuple[str, str], list[TransitionSample]] = defaultdict(list)
    for sample in samples:
        grouped[(sample.source, sample.target)].append(sample)

    cleaned_edges: dict[tuple[str, str], list[TransitionSample]] = {}
    discarded_low_sample = 0
    discarded_after_lower = 0
    discarded_after_upper = 0

    for edge_key, edge_samples in grouped.items():
        if len(edge_samples) < MIN_RAW_EDGE_SAMPLES:
            discarded_low_sample += 1
            continue

        lower_cleaned = [
            sample for sample in edge_samples if sample.elapsed_seconds >= lower_threshold
        ]
        if len(lower_cleaned) < MIN_CLEAN_EDGE_SAMPLES:
            discarded_after_lower += 1
            continue

        values = sorted(sample.elapsed_seconds for sample in lower_cleaned)
        q1 = _percentile(values, 25)
        q3 = _percentile(values, 75)
        iqr = q3 - q1
        upper_threshold = q3 + 1.5 * iqr
        upper_cleaned = [
            sample for sample in lower_cleaned if sample.elapsed_seconds <= upper_threshold
        ]
        if len(upper_cleaned) < MIN_CLEAN_EDGE_SAMPLES:
            discarded_after_upper += 1
            continue

        cleaned_edges[edge_key] = upper_cleaned

    outlier_meta.update(
        {
            "min_raw_edge_samples": MIN_RAW_EDGE_SAMPLES,
            "min_clean_edge_samples": MIN_CLEAN_EDGE_SAMPLES,
            "discarded_edges_low_sample": discarded_low_sample,
            "discarded_edges_after_lower_threshold": discarded_after_lower,
            "discarded_edges_after_upper_threshold": discarded_after_upper,
        }
    )
    return cleaned_edges, outlier_meta


def _calibrate_lower_threshold(values: list[float]) -> tuple[float, dict[str, Any]]:
    if not values:
        return 0.0, {
            "outlier_method": "global_empty",
            "lower_threshold_seconds": 0.0,
            "dip_p_value": None,
            "dependency_warning": None,
        }

    sorted_values = sorted(values)
    fallback_threshold = _percentile(sorted_values, 5)
    meta: dict[str, Any] = {
        "outlier_method": "global_p5",
        "lower_threshold_seconds": fallback_threshold,
        "dip_p_value": None,
        "dependency_warning": None,
    }

    try:
        import numpy as np
        from diptest import diptest
        from scipy.signal import find_peaks
        from scipy.stats import gaussian_kde
    except ImportError as exc:
        meta["dependency_warning"] = f"Dependencia estatistica ausente: {exc.name}."
        return fallback_threshold, meta

    if len(sorted_values) < 20 or min(sorted_values) == max(sorted_values):
        return fallback_threshold, meta

    data = np.array(sorted_values, dtype=float)
    _, p_value = diptest(data)
    meta["dip_p_value"] = float(p_value)

    if p_value >= 0.05:
        return fallback_threshold, meta

    grid = np.linspace(float(data.min()), float(data.max()), 512)
    density = gaussian_kde(data)(grid)
    peaks, _ = find_peaks(density)
    if len(peaks) < 2:
        return fallback_threshold, meta

    strongest_peaks = sorted(peaks, key=lambda index: density[index], reverse=True)[:2]
    left_peak, right_peak = sorted(strongest_peaks)
    if right_peak - left_peak <= 1:
        return fallback_threshold, meta

    valley_relative_index = int(np.argmin(density[left_peak : right_peak + 1]))
    valley_index = left_peak + valley_relative_index
    threshold = float(grid[valley_index])
    meta.update(
        {
            "outlier_method": "global_kde_diptest",
            "lower_threshold_seconds": threshold,
        }
    )
    return threshold, meta


def _build_graph_payload(
    *,
    rows: list[dict[str, Any]],
    product_map: dict[str, dict[str, Any]],
    samples: list[TransitionSample],
    cleaned_edges: dict[tuple[str, str], list[TransitionSample]],
    outlier_meta: dict[str, Any],
    trained_at: datetime,
    start_at: str | None,
    temporal_decay: bool,
    half_life_days: float,
    decay_min_weight: float,
) -> dict[str, Any]:
    scan_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        scan_counts[str(row["barcode"])] += 1

    connected_barcodes = set()
    links = []
    for (source, target), edge_samples in cleaned_edges.items():
        elapsed_values = sorted(sample.elapsed_seconds for sample in edge_samples)
        avg_elapsed = sum(elapsed_values) / len(elapsed_values)
        transition_count = len(edge_samples)
        weighted_transition_count = sum(sample.weight for sample in edge_samples)
        p25_elapsed = _percentile(elapsed_values, 25)
        strength = weighted_transition_count / max(avg_elapsed, 1.0)

        connected_barcodes.add(source)
        connected_barcodes.add(target)
        links.append(
            {
                "source": source,
                "target": target,
                "transition_count": transition_count,
                "weighted_transition_count": round(weighted_transition_count, 6),
                "avg_elapsed_seconds": round(avg_elapsed, 6),
                "p25_elapsed_seconds": round(p25_elapsed, 6),
                "min_elapsed_seconds": round(min(elapsed_values), 6),
                "max_elapsed_seconds": round(max(elapsed_values), 6),
                "strength": round(strength, 9),
            }
        )

    barcodes = sorted(connected_barcodes or scan_counts.keys())
    nodes = []
    for barcode in barcodes:
        product = product_map.get(barcode, {})
        nodes.append(
            {
                "id": barcode,
                "barcode": barcode,
                "name": product.get("name") or barcode,
                "category": product.get("category"),
                "aisle": product.get("aisle"),
                "scan_count": scan_counts.get(barcode, 0),
            }
        )

    _apply_force_layout(nodes, links)
    links.sort(
        key=lambda link: (
            str(link["source"]),
            str(link["target"]),
            float(link["avg_elapsed_seconds"]),
        )
    )

    return {
        "nodes": nodes,
        "links": links,
        "meta": {
            "trained_at": trained_at.isoformat(),
            "start_at": start_at,
            "temporal_decay": temporal_decay,
            "half_life_days": half_life_days,
            "decay_min_weight": decay_min_weight,
            "event_count": len(rows),
            "raw_transition_count": len(samples),
            "valid_transition_count": sum(len(edge_samples) for edge_samples in cleaned_edges.values()),
            "node_count": len(nodes),
            "edge_count": len(links),
            **outlier_meta,
        },
    }


def _apply_force_layout(nodes: list[dict[str, Any]], links: list[dict[str, Any]]) -> None:
    if not nodes:
        return

    node_ids = [str(node["id"]) for node in nodes]
    positions = _initial_positions(node_ids)
    target_distances = _target_distances(links)
    rng = random.Random(42)

    for _ in range(360):
        for link in links:
            source = str(link["source"])
            target = str(link["target"])
            sx, sy = positions[source]
            tx, ty = positions[target]
            dx = tx - sx
            dy = ty - sy
            distance = math.hypot(dx, dy) or 0.001
            target_distance = target_distances[(source, target)]
            adjustment = (distance - target_distance) * 0.035
            ux = dx / distance
            uy = dy / distance
            positions[source] = (sx + ux * adjustment, sy + uy * adjustment)
            positions[target] = (tx - ux * adjustment, ty - uy * adjustment)

        for index, source in enumerate(node_ids):
            sx, sy = positions[source]
            for target in node_ids[index + 1 :]:
                tx, ty = positions[target]
                dx = tx - sx
                dy = ty - sy
                distance_sq = max(dx * dx + dy * dy, 1.0)
                force = min(80.0 / distance_sq, 0.08)
                jitter_x = rng.uniform(-0.001, 0.001)
                jitter_y = rng.uniform(-0.001, 0.001)
                positions[source] = (positions[source][0] - dx * force + jitter_x, positions[source][1] - dy * force + jitter_y)
                positions[target] = (positions[target][0] + dx * force - jitter_x, positions[target][1] + dy * force - jitter_y)

        for node_id in node_ids:
            x, y = positions[node_id]
            positions[node_id] = (x * 0.995, y * 0.995)

    for node in nodes:
        x, y = positions[str(node["id"])]
        node["x"] = round(x, 4)
        node["y"] = round(y, 4)


def _initial_positions(node_ids: list[str]) -> dict[str, tuple[float, float]]:
    radius = max(120.0, len(node_ids) * 4.0)
    positions = {}
    for index, node_id in enumerate(node_ids):
        angle = 2 * math.pi * index / max(len(node_ids), 1)
        positions[node_id] = (math.cos(angle) * radius, math.sin(angle) * radius)
    return positions


def _target_distances(links: list[dict[str, Any]]) -> dict[tuple[str, str], float]:
    if not links:
        return {}

    values = sorted(float(link["avg_elapsed_seconds"]) for link in links)
    low = _percentile(values, 10)
    high = _percentile(values, 90)
    if math.isclose(low, high):
        low = min(values)
        high = max(values)

    targets = {}
    for link in links:
        source = str(link["source"])
        target = str(link["target"])
        elapsed = float(link["avg_elapsed_seconds"])
        if math.isclose(low, high):
            visual_distance = 120.0
        else:
            ratio = min(max((elapsed - low) / (high - low), 0.0), 1.0)
            visual_distance = 70.0 + ratio * 230.0
        link["visual_distance"] = round(visual_distance, 4)
        targets[(source, target)] = visual_distance
    return targets


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])

    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile / 100.0
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return float(ordered[lower_index])

    lower_value = ordered[lower_index]
    upper_value = ordered[upper_index]
    fraction = position - lower_index
    return float(lower_value + (upper_value - lower_value) * fraction)
