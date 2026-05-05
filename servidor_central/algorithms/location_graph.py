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
THRESHOLD_EPSILON = 1e-9


def _canonical_edge_key(source: str, target: str) -> tuple[str, str]:
    """Gera uma chave estável para unir ida e volta do mesmo par."""
    return tuple(sorted((str(source), str(target))))


@dataclass(frozen=True)
class TransitionSample:
    cart_id: str
    source: str
    target: str
    elapsed_seconds: float
    transition_at: datetime
    weight: float


def get_graph_path(path: Path | str | None = None) -> Path:
    """Resolve o caminho do arquivo de cache do grafo de localizacao."""
    if path is not None:
        return Path(path)

    configured_path = os.getenv("SMART_CART_LOCATION_GRAPH_PATH")
    if configured_path:
        return Path(configured_path)

    return get_db_path().resolve().parent / DEFAULT_GRAPH_FILENAME


def load_location_graph(path: Path | str | None = None) -> dict[str, Any] | None:
    """Carrega o grafo salvo em disco, se ele existir."""
    graph_path = get_graph_path(path)
    if not graph_path.exists():
        return None

    with graph_path.open("r", encoding="utf-8") as graph_file:
        return json.load(graph_file)


def save_location_graph(graph: dict[str, Any], path: Path | str | None = None) -> Path:
    """Salva o grafo em disco e retorna o caminho final."""
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
    """Reconstroi o grafo de transicoes a partir do banco de dados."""
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
    cleaned_edges, edge_analyses, outlier_meta = _clean_transition_samples(samples)
    graph = _build_graph_payload(
        rows=rows,
        product_map=product_map,
        samples=samples,
        cleaned_edges=cleaned_edges,
        edge_analyses=edge_analyses,
        outlier_meta=outlier_meta,
        trained_at=trained_at,
        start_at=start_at,
        temporal_decay=temporal_decay,
        half_life_days=half_life_days,
        decay_min_weight=decay_min_weight,
    )
    graph["meta"]["cache_path"] = str(save_location_graph(graph, output_path))
    return graph


def get_location_graph_link_details(
    source: str,
    target: str,
    *,
    graph: dict[str, Any] | None = None,
    db_path: Path | str | None = None,
) -> dict[str, Any] | None:
    """Retorna as amostras e cortes usados para uma aresta do grafo."""
    if graph is None:
        graph = load_location_graph()
    if graph is None:
        return None

    canonical_source, canonical_target = _canonical_edge_key(source, target)
    link = None
    for item in graph.get("links", []):
        if _canonical_edge_key(item.get("source"), item.get("target")) == (
            canonical_source,
            canonical_target,
        ):
            link = item
            break
    if link is None:
        return None

    meta = graph.get("meta", {})
    with _open_connection(db_path) as connection:
        rows = _fetch_scan_events(connection, start_at=meta.get("start_at"))
        product_map = _fetch_product_snapshots(connection)

    samples = _build_transition_samples(
        rows,
        trained_at=_parse_trained_at(meta),
        temporal_decay=bool(meta.get("temporal_decay")),
        half_life_days=float(meta.get("half_life_days") or DEFAULT_HALF_LIFE_DAYS),
        decay_min_weight=float(meta.get("decay_min_weight") or DEFAULT_DECAY_MIN_WEIGHT),
    )
    edge_samples = [
        sample
        for sample in samples
        if _canonical_edge_key(sample.source, sample.target) == (canonical_source, canonical_target)
    ]
    if not edge_samples:
        return None

    node_map = {str(node.get("id")): node for node in graph.get("nodes", [])}
    source_node = node_map.get(source) or product_map.get(source)
    target_node = node_map.get(target) or product_map.get(target)

    analysis, _, sample_details = _analyze_link_samples(edge_samples)

    return {
        "source": source,
        "target": target,
        "source_node": source_node,
        "target_node": target_node,
        "link": link,
        "analysis": analysis,
        "samples": sample_details,
    }


def find_node(
    graph: dict[str, Any] | None, barcode: str | None
) -> dict[str, Any] | None:
    """Busca um no do grafo pelo barcode informado."""
    if not graph or not barcode:
        return None
    for node in graph.get("nodes", []):
        if node.get("id") == barcode:
            return node
    return None


def get_connected_links(
    graph: dict[str, Any] | None, barcode: str | None
) -> list[dict[str, Any]]:
    """Retorna as arestas conectadas a um barcode ordenadas por forca."""
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


def get_nearby_products(
    graph: dict[str, Any] | None,
    barcode: str | None,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    if not graph or not barcode or limit <= 0:
        return []

    node = find_node(graph, barcode)
    if node is None:
        return []

    nodes_by_id = {item.get("id"): item for item in graph.get("nodes", [])}
    nearby_products_by_barcode: dict[str, dict[str, Any]] = {}

    for link in graph.get("links", []):
        if link.get("source") == barcode:
            neighbor_id = link.get("target")
        elif link.get("target") == barcode:
            neighbor_id = link.get("source")
        else:
            continue

        if neighbor_id is None:
            continue

        neighbor_barcode = str(neighbor_id)
        neighbor_node = nodes_by_id.get(neighbor_id, {})
        current_item = {
            "barcode": neighbor_barcode,
            "name": neighbor_node.get("name"),
            "category": neighbor_node.get("category"),
            "aisle": neighbor_node.get("aisle"),
            "scan_count": neighbor_node.get("scan_count"),
            "avg_elapsed_seconds": link.get("avg_elapsed_seconds"),
            "transition_count": link.get("transition_count"),
            "strength": link.get("strength"),
        }

        previous_item = nearby_products_by_barcode.get(neighbor_barcode)
        if previous_item is None:
            nearby_products_by_barcode[neighbor_barcode] = current_item
            continue

        current_score = (
            float(current_item.get("avg_elapsed_seconds") or math.inf),
            str(current_item.get("name") or ""),
            neighbor_barcode,
        )
        previous_score = (
            float(previous_item.get("avg_elapsed_seconds") or math.inf),
            str(previous_item.get("name") or ""),
            neighbor_barcode,
        )
        if current_score < previous_score:
            nearby_products_by_barcode[neighbor_barcode] = current_item

    return sorted(
        nearby_products_by_barcode.values(),
        key=lambda item: (
            float(item.get("avg_elapsed_seconds") or math.inf),
            str(item.get("name") or ""),
            str(item.get("barcode") or ""),
        ),
    )[:limit]


def infer_product_position(
    graph: dict[str, Any] | None, barcode: str | None
) -> dict[str, Any]:
    """Infere a posicao de um produto no grafo e expõe seus vizinhos."""
    if graph is None:
        return {"algorithm_status": "cache_missing", "position": None, "neighbors": []}

    if not graph.get("links"):
        return {
            "algorithm_status": "insufficient_data",
            "position": None,
            "neighbors": [],
        }

    node = find_node(graph, barcode)
    if node is None:
        return {
            "algorithm_status": "product_not_in_graph",
            "position": None,
            "neighbors": [],
        }

    neighbors = []
    nodes_by_id = {item.get("id"): item for item in graph.get("nodes", [])}
    for link in get_connected_links(graph, barcode)[:10]:
        neighbor_id = (
            link["target"] if link.get("source") == barcode else link.get("source")
        )
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
    """Abre a conexao SQLite de acordo com o caminho configurado."""
    if db_path is None:
        return get_connection()

    connection = sqlite3.connect(db_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def _fetch_scan_events(
    connection: sqlite3.Connection, *, start_at: str | None
) -> list[dict[str, Any]]:
    """Carrega os eventos de leitura de itens usados para treinar o grafo."""
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


def _fetch_product_snapshots(
    connection: sqlite3.Connection,
) -> dict[str, dict[str, Any]]:
    """Resume o estado atual dos produtos a partir dos itens do carrinho."""
    rows = connection.execute("""
        SELECT barcode, name, category, aisle, MAX(updated_at) AS updated_at, SUM(quantity) AS quantity_sum
        FROM cart_items
        GROUP BY barcode, name, category, aisle
        """).fetchall()

    product_map: dict[str, dict[str, Any]] = {}
    for row in rows:
        barcode = str(row["barcode"])
        current = product_map.get(barcode)
        if current is None or str(row["updated_at"]) > str(
            current.get("updated_at", "")
        ):
            product_map[barcode] = dict(row)
    return product_map


def _parse_datetime(value: str) -> datetime | None:
    """Converte uma string ISO em datetime UTC, quando possivel."""
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
    """Transforma as leituras por carrinho em amostras de transicao."""
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
                    cart_id=str(previous["cart_id"]),
                    source=source,
                    target=target,
                    elapsed_seconds=elapsed_seconds,
                    transition_at=current_at,
                    weight=weight,
                )
            )
    return samples


def _parse_trained_at(meta: dict[str, Any]) -> datetime:
    """Recupera o instante de treino do metadado salvo em disco."""
    trained_at = meta.get("trained_at")
    if isinstance(trained_at, str):
        parsed = _parse_datetime(trained_at)
        if parsed is not None:
            return parsed
    return datetime.now(timezone.utc)


def _clean_transition_samples(
    samples: list[TransitionSample],
) -> tuple[
    dict[tuple[str, str], list[TransitionSample]],
    dict[tuple[str, str], dict[str, Any]],
    dict[str, Any],
]:
    """Analisa cada link e remove as arestas descartadas."""
    grouped: dict[tuple[str, str], list[TransitionSample]] = defaultdict(list)
    for sample in samples:
        grouped[_canonical_edge_key(sample.source, sample.target)].append(sample)

    cleaned_edges: dict[tuple[str, str], list[TransitionSample]] = {}
    edge_analyses: dict[tuple[str, str], dict[str, Any]] = {}
    kept_link_count = 0
    discarded_low_volume = 0
    discarded_after_lower = 0
    discarded_after_upper = 0
    median_link_count = 0
    fallback_link_count = 0
    kde_link_count = 0

    for edge_key, edge_samples in grouped.items():
        analysis, kept_samples, _ = _analyze_link_samples(edge_samples)
        edge_analyses[edge_key] = analysis
        if analysis["decision"] == "kept":
            cleaned_edges[edge_key] = kept_samples
            kept_link_count += 1
        else:
            discard_reason = analysis.get("discard_reason")
            if discard_reason == "low_volume":
                discarded_low_volume += 1
            elif discard_reason == "after_lower":
                discarded_after_lower += 1
            elif discard_reason == "after_upper":
                discarded_after_upper += 1

        method = str(analysis.get("outlier_method") or "")
        if method == "median":
            median_link_count += 1
        elif method == "fallback_log_iqr":
            fallback_link_count += 1
        elif method.startswith("kde_"):
            kde_link_count += 1

    outlier_meta = {
        "min_raw_edge_samples": MIN_RAW_EDGE_SAMPLES,
        "min_clean_edge_samples": MIN_CLEAN_EDGE_SAMPLES,
        "kept_link_count": kept_link_count,
        "discarded_link_count": len(grouped) - kept_link_count,
        "discarded_edges_low_sample": discarded_low_volume,
        "discarded_edges_after_lower_threshold": discarded_after_lower,
        "discarded_edges_after_upper_threshold": discarded_after_upper,
        "median_link_count": median_link_count,
        "fallback_link_count": fallback_link_count,
        "kde_link_count": kde_link_count,
    }
    return cleaned_edges, edge_analyses, outlier_meta


def _analyze_link_samples(
    edge_samples: list[TransitionSample],
) -> tuple[dict[str, Any], list[TransitionSample], list[dict[str, Any]]]:
    """Executa a politica de limpeza e resumo para um link."""
    ordered_samples = sorted(edge_samples, key=lambda item: item.transition_at)
    durations = [sample.elapsed_seconds for sample in ordered_samples]
    sample_count = len(ordered_samples)

    def build_sample_details(
        *,
        lower_threshold: float | None,
        upper_threshold: float | None,
        used_for_weight: set[int],
        force_discard_all: bool = False,
    ) -> list[dict[str, Any]]:
        details: list[dict[str, Any]] = []
        for index, sample in enumerate(ordered_samples):
            if force_discard_all:
                kept_after_lower = False
                kept_after_upper = False
            elif lower_threshold is None:
                kept_after_lower = True
                kept_after_upper = True
            else:
                kept_after_lower = sample.elapsed_seconds >= (lower_threshold - THRESHOLD_EPSILON)
                if upper_threshold is None:
                    kept_after_upper = kept_after_lower
                else:
                    kept_after_upper = kept_after_lower and sample.elapsed_seconds <= (upper_threshold + THRESHOLD_EPSILON)

            details.append(
                {
                    "cart_id": sample.cart_id,
                    "elapsed_seconds": round(sample.elapsed_seconds, 6),
                    "transition_at": sample.transition_at.isoformat(),
                    "weight": round(sample.weight, 6),
                    "kept_after_lower": kept_after_lower,
                    "kept_after_upper": kept_after_upper,
                    "used_for_weight": index in used_for_weight,
                }
            )
        return details

    if sample_count < 5:
        analysis = {
            "branch": "low_volume",
            "outlier_method": "low_volume",
            "decision": "discarded",
            "discard_reason": "low_volume",
            "sample_count_initial": sample_count,
            "raw_sample_count": sample_count,
            "lower_threshold_seconds": None,
            "upper_threshold_seconds": None,
            "dip_p_value": None,
            "dependency_warning": None,
            "min_raw_edge_samples": MIN_RAW_EDGE_SAMPLES,
            "min_clean_edge_samples": MIN_CLEAN_EDGE_SAMPLES,
            "lower_cleaned_sample_count": 0,
            "upper_cleaned_sample_count": 0,
            "sample_count_after_lower": 0,
            "sample_count_after_upper": 0,
            "sample_count_final": 0,
            "discarded_after_lower_threshold": sample_count,
            "discarded_after_upper_threshold": 0,
            "weight_seconds": None,
            "formula_lower": None,
            "formula_upper": None,
            "formula_weight": None,
            "formula_summary": "Descartado por volume inicial menor que 5 amostras.",
        }
        return analysis, [], build_sample_details(lower_threshold=None, upper_threshold=None, used_for_weight=set(), force_discard_all=True)

    if sample_count <= 15:
        median = _percentile(durations, 50)
        analysis = {
            "branch": "median",
            "outlier_method": "median",
            "decision": "kept",
            "discard_reason": None,
            "sample_count_initial": sample_count,
            "raw_sample_count": sample_count,
            "lower_threshold_seconds": None,
            "upper_threshold_seconds": None,
            "dip_p_value": None,
            "dependency_warning": None,
            "min_raw_edge_samples": MIN_RAW_EDGE_SAMPLES,
            "min_clean_edge_samples": MIN_CLEAN_EDGE_SAMPLES,
            "lower_cleaned_sample_count": sample_count,
            "upper_cleaned_sample_count": sample_count,
            "sample_count_after_lower": sample_count,
            "sample_count_after_upper": sample_count,
            "sample_count_final": sample_count,
            "discarded_after_lower_threshold": 0,
            "discarded_after_upper_threshold": 0,
            "weight_seconds": float(median),
            "formula_lower": None,
            "formula_upper": None,
            "formula_weight": "mediana(tempos do link)",
            "formula_summary": "Entre 5 e 15 amostras, o tempo do link e a mediana dos tempos brutos.",
        }
        return analysis, list(ordered_samples), build_sample_details(lower_threshold=None, upper_threshold=None, used_for_weight=set(range(sample_count)))

    if sample_count <= 49:
        log_values = [math.log(sample.elapsed_seconds) for sample in ordered_samples]
        q1_log = _percentile(log_values, 25)
        q3_log = _percentile(log_values, 75)
        iqr_log = q3_log - q1_log
        lower_threshold = math.nextafter(math.exp(q1_log - 1.5 * iqr_log), -math.inf)
        upper_threshold = math.nextafter(math.exp(q3_log + 1.5 * iqr_log), math.inf)
        lower_cleaned = [sample for sample in ordered_samples if lower_threshold - THRESHOLD_EPSILON <= sample.elapsed_seconds <= upper_threshold + THRESHOLD_EPSILON]
        if len(lower_cleaned) < MIN_CLEAN_EDGE_SAMPLES:
            analysis = {
                "branch": "fallback_log_iqr",
                "outlier_method": "fallback_log_iqr",
                "decision": "discarded",
                "discard_reason": "after_upper",
                "sample_count_initial": sample_count,
                "raw_sample_count": sample_count,
                "lower_threshold_seconds": float(lower_threshold),
                "upper_threshold_seconds": float(upper_threshold),
                "dip_p_value": None,
                "dependency_warning": None,
                "min_raw_edge_samples": MIN_RAW_EDGE_SAMPLES,
                "min_clean_edge_samples": MIN_CLEAN_EDGE_SAMPLES,
                "lower_cleaned_sample_count": len(lower_cleaned),
                "upper_cleaned_sample_count": 0,
                "sample_count_after_lower": len(lower_cleaned),
                "sample_count_after_upper": 0,
                "sample_count_final": 0,
                "discarded_after_lower_threshold": sample_count - len(lower_cleaned),
                "discarded_after_upper_threshold": len(lower_cleaned),
                "weight_seconds": None,
                "formula_lower": "exp(Q1(log(x)) - 1.5 * IQR(log(x)))",
                "formula_upper": "exp(Q3(log(x)) + 1.5 * IQR(log(x)))",
                "formula_weight": "P25(dados filtrados)",
                "formula_summary": "Fallback log/IQR para links com 16 a 49 amostras.",
            }
            return analysis, [], build_sample_details(lower_threshold=lower_threshold, upper_threshold=upper_threshold, used_for_weight=set(), force_discard_all=True)

        kept_durations = sorted(sample.elapsed_seconds for sample in lower_cleaned)
        weight_seconds = _percentile(kept_durations, 25)
        kept_indexes = {
            index
            for index, sample in enumerate(ordered_samples)
            if sample.elapsed_seconds >= lower_threshold - THRESHOLD_EPSILON and sample.elapsed_seconds <= upper_threshold + THRESHOLD_EPSILON
        }
        analysis = {
            "branch": "fallback_log_iqr",
            "outlier_method": "fallback_log_iqr",
            "decision": "kept",
            "discard_reason": None,
            "sample_count_initial": sample_count,
            "raw_sample_count": sample_count,
            "lower_threshold_seconds": float(lower_threshold),
            "upper_threshold_seconds": float(upper_threshold),
            "dip_p_value": None,
            "dependency_warning": None,
            "min_raw_edge_samples": MIN_RAW_EDGE_SAMPLES,
            "min_clean_edge_samples": MIN_CLEAN_EDGE_SAMPLES,
            "lower_cleaned_sample_count": len(lower_cleaned),
            "upper_cleaned_sample_count": len(lower_cleaned),
            "sample_count_after_lower": len(lower_cleaned),
            "sample_count_after_upper": len(lower_cleaned),
            "sample_count_final": len(lower_cleaned),
            "discarded_after_lower_threshold": sample_count - len(lower_cleaned),
            "discarded_after_upper_threshold": 0,
            "weight_seconds": float(weight_seconds),
            "formula_lower": "exp(Q1(log(x)) - 1.5 * IQR(log(x)))",
            "formula_upper": "exp(Q3(log(x)) + 1.5 * IQR(log(x)))",
            "formula_weight": "P25(dados filtrados)",
            "formula_summary": "Fallback log/IQR para links com 16 a 49 amostras.",
        }
        return analysis, lower_cleaned, build_sample_details(lower_threshold=lower_threshold, upper_threshold=upper_threshold, used_for_weight=kept_indexes)

    try:
        import numpy as np
        from diptest import diptest
        from scipy.signal import find_peaks
        from scipy.stats import gaussian_kde
    except ImportError as exc:
        dependency_warning = f"Dependencia estatistica ausente: {exc.name}."
        lower_threshold = math.nextafter(_percentile(durations, 5), -math.inf)
        lower_cleaned = [sample for sample in ordered_samples if sample.elapsed_seconds >= lower_threshold - THRESHOLD_EPSILON]
        if len(lower_cleaned) < MIN_CLEAN_EDGE_SAMPLES:
            analysis = {
                "branch": "kde_dependency_fallback",
                "outlier_method": "kde_dependency_fallback",
                "decision": "discarded",
                "discard_reason": "after_lower",
                "sample_count_initial": sample_count,
                "raw_sample_count": sample_count,
                "lower_threshold_seconds": float(lower_threshold),
                "upper_threshold_seconds": None,
                "dip_p_value": None,
                "dependency_warning": dependency_warning,
                "min_raw_edge_samples": MIN_RAW_EDGE_SAMPLES,
                "min_clean_edge_samples": MIN_CLEAN_EDGE_SAMPLES,
                "lower_cleaned_sample_count": len(lower_cleaned),
                "upper_cleaned_sample_count": 0,
                "sample_count_after_lower": len(lower_cleaned),
                "sample_count_after_upper": 0,
                "sample_count_final": 0,
                "discarded_after_lower_threshold": sample_count - len(lower_cleaned),
                "discarded_after_upper_threshold": 0,
                "weight_seconds": None,
                "formula_lower": "P5(tempos do link)",
                "formula_upper": "Q3 + 1.5 * IQR",
                "formula_weight": "P25(dados filtrados)",
                "formula_summary": "Fallback para quando as dependencias estatisticas nao estiverem disponiveis.",
            }
            return analysis, [], build_sample_details(lower_threshold=lower_threshold, upper_threshold=None, used_for_weight=set(), force_discard_all=True)

        kept_durations = sorted(sample.elapsed_seconds for sample in lower_cleaned)
        q1 = _percentile(kept_durations, 25)
        q3 = _percentile(kept_durations, 75)
        iqr = q3 - q1
        upper_threshold = math.nextafter(q3 + 1.5 * iqr, math.inf)
        upper_cleaned = [sample for sample in lower_cleaned if sample.elapsed_seconds <= upper_threshold + THRESHOLD_EPSILON]
        if len(upper_cleaned) < MIN_CLEAN_EDGE_SAMPLES:
            analysis = {
                "branch": "kde_dependency_fallback",
                "outlier_method": "kde_dependency_fallback",
                "decision": "discarded",
                "discard_reason": "after_upper",
                "sample_count_initial": sample_count,
                "raw_sample_count": sample_count,
                "lower_threshold_seconds": float(lower_threshold),
                "upper_threshold_seconds": float(upper_threshold),
                "dip_p_value": None,
                "dependency_warning": dependency_warning,
                "min_raw_edge_samples": MIN_RAW_EDGE_SAMPLES,
                "min_clean_edge_samples": MIN_CLEAN_EDGE_SAMPLES,
                "lower_cleaned_sample_count": len(lower_cleaned),
                "upper_cleaned_sample_count": len(upper_cleaned),
                "sample_count_after_lower": len(lower_cleaned),
                "sample_count_after_upper": len(upper_cleaned),
                "sample_count_final": 0,
                "discarded_after_lower_threshold": sample_count - len(lower_cleaned),
                "discarded_after_upper_threshold": len(lower_cleaned) - len(upper_cleaned),
                "weight_seconds": None,
                "formula_lower": "P5(tempos do link)",
                "formula_upper": "Q3 + 1.5 * IQR",
                "formula_weight": "P25(dados filtrados)",
                "formula_summary": "Fallback para quando as dependencias estatisticas nao estiverem disponiveis.",
            }
            return analysis, [], build_sample_details(lower_threshold=lower_threshold, upper_threshold=upper_threshold, used_for_weight=set(), force_discard_all=True)

        weight_seconds = _percentile(sorted(sample.elapsed_seconds for sample in upper_cleaned), 25)
        used_indexes = {
            index
            for index, sample in enumerate(ordered_samples)
            if sample.elapsed_seconds >= lower_threshold - THRESHOLD_EPSILON and sample.elapsed_seconds <= upper_threshold + THRESHOLD_EPSILON
        }
        analysis = {
            "branch": "kde_dependency_fallback",
            "outlier_method": "kde_dependency_fallback",
            "decision": "kept",
            "discard_reason": None,
            "sample_count_initial": sample_count,
            "raw_sample_count": sample_count,
            "lower_threshold_seconds": float(lower_threshold),
            "upper_threshold_seconds": float(upper_threshold),
            "dip_p_value": None,
            "dependency_warning": dependency_warning,
            "min_raw_edge_samples": MIN_RAW_EDGE_SAMPLES,
            "min_clean_edge_samples": MIN_CLEAN_EDGE_SAMPLES,
            "lower_cleaned_sample_count": len(lower_cleaned),
            "upper_cleaned_sample_count": len(upper_cleaned),
            "sample_count_after_lower": len(lower_cleaned),
            "sample_count_after_upper": len(upper_cleaned),
            "sample_count_final": len(upper_cleaned),
            "discarded_after_lower_threshold": sample_count - len(lower_cleaned),
            "discarded_after_upper_threshold": len(lower_cleaned) - len(upper_cleaned),
            "weight_seconds": float(weight_seconds),
            "formula_lower": "P5(tempos do link)",
            "formula_upper": "Q3 + 1.5 * IQR",
            "formula_weight": "P25(dados filtrados)",
            "formula_summary": "Fallback para quando as dependencias estatisticas nao estiverem disponiveis.",
        }
        return analysis, upper_cleaned, build_sample_details(lower_threshold=lower_threshold, upper_threshold=upper_threshold, used_for_weight=used_indexes)

    data = np.array(durations, dtype=float)
    dip_statistic, p_value = diptest(data)
    _ = dip_statistic
    grid = np.linspace(float(data.min()), float(data.max()), max(512, min(2048, sample_count * 16)))
    density = gaussian_kde(data, bw_method="silverman")(grid)

    if float(p_value) < 0.05:
        peaks, _ = find_peaks(density)
        if len(peaks) >= 2:
            strongest_peaks = sorted(peaks, key=lambda index: density[index], reverse=True)[:2]
            first_peak, second_peak = sorted(strongest_peaks)
            valley_segment = density[first_peak : second_peak + 1]
            valley_index = first_peak + int(np.argmin(valley_segment))
            lower_threshold = math.nextafter(float(grid[valley_index]), -math.inf)
            formula_lower = "vale do KDE(Silverman) entre os dois primeiros picos"
        else:
            lower_threshold = math.nextafter(_percentile(durations, 5), -math.inf)
            formula_lower = "P5(tempos do link) porque o KDE nao encontrou dois picos"
        branch = "kde_bimodal"
        outlier_method = "kde_bimodal"
    else:
        lower_threshold = math.nextafter(_percentile(durations, 5), -math.inf)
        formula_lower = "P5(tempos do link)"
        branch = "kde_unimodal"
        outlier_method = "kde_unimodal"

    lower_cleaned = [sample for sample in ordered_samples if sample.elapsed_seconds >= lower_threshold - THRESHOLD_EPSILON]
    if len(lower_cleaned) < MIN_CLEAN_EDGE_SAMPLES:
        analysis = {
            "branch": branch,
            "outlier_method": outlier_method,
            "decision": "discarded",
            "discard_reason": "after_lower",
            "sample_count_initial": sample_count,
            "raw_sample_count": sample_count,
            "lower_threshold_seconds": float(lower_threshold),
            "upper_threshold_seconds": None,
            "dip_p_value": float(p_value),
            "dependency_warning": None,
            "min_raw_edge_samples": MIN_RAW_EDGE_SAMPLES,
            "min_clean_edge_samples": MIN_CLEAN_EDGE_SAMPLES,
            "lower_cleaned_sample_count": len(lower_cleaned),
            "upper_cleaned_sample_count": 0,
            "sample_count_after_lower": len(lower_cleaned),
            "sample_count_after_upper": 0,
            "sample_count_final": 0,
            "discarded_after_lower_threshold": sample_count - len(lower_cleaned),
            "discarded_after_upper_threshold": 0,
            "weight_seconds": None,
            "formula_lower": formula_lower,
            "formula_upper": "Q3 + 1.5 * IQR",
            "formula_weight": "P25(dados filtrados)",
            "formula_summary": "Corte superior por IQR apos o filtro inferior.",
        }
        return analysis, [], build_sample_details(lower_threshold=lower_threshold, upper_threshold=None, used_for_weight=set())

    kept_durations = sorted(sample.elapsed_seconds for sample in lower_cleaned)
    q1 = _percentile(kept_durations, 25)
    q3 = _percentile(kept_durations, 75)
    iqr = q3 - q1
    upper_threshold = math.nextafter(q3 + 1.5 * iqr, math.inf)
    upper_cleaned = [sample for sample in lower_cleaned if sample.elapsed_seconds <= upper_threshold + THRESHOLD_EPSILON]
    if len(upper_cleaned) < MIN_CLEAN_EDGE_SAMPLES:
        analysis = {
            "branch": branch,
            "outlier_method": outlier_method,
            "decision": "discarded",
            "discard_reason": "after_upper",
            "sample_count_initial": sample_count,
            "raw_sample_count": sample_count,
            "lower_threshold_seconds": float(lower_threshold),
            "upper_threshold_seconds": float(upper_threshold),
            "dip_p_value": float(p_value),
            "dependency_warning": None,
            "min_raw_edge_samples": MIN_RAW_EDGE_SAMPLES,
            "min_clean_edge_samples": MIN_CLEAN_EDGE_SAMPLES,
            "lower_cleaned_sample_count": len(lower_cleaned),
            "upper_cleaned_sample_count": len(upper_cleaned),
            "sample_count_after_lower": len(lower_cleaned),
            "sample_count_after_upper": len(upper_cleaned),
            "sample_count_final": 0,
            "discarded_after_lower_threshold": sample_count - len(lower_cleaned),
            "discarded_after_upper_threshold": len(lower_cleaned) - len(upper_cleaned),
            "weight_seconds": None,
            "formula_lower": formula_lower,
            "formula_upper": "Q3 + 1.5 * IQR",
            "formula_weight": "P25(dados filtrados)",
            "formula_summary": "Corte superior por IQR apos o filtro inferior.",
        }
        return analysis, [], build_sample_details(lower_threshold=lower_threshold, upper_threshold=upper_threshold, used_for_weight=set(), force_discard_all=True)

    weight_seconds = _percentile(sorted(sample.elapsed_seconds for sample in upper_cleaned), 25)
    used_indexes = {
        index
        for index, sample in enumerate(ordered_samples)
        if sample.elapsed_seconds >= lower_threshold - THRESHOLD_EPSILON and sample.elapsed_seconds <= upper_threshold + THRESHOLD_EPSILON
    }
    analysis = {
        "branch": branch,
        "outlier_method": outlier_method,
        "decision": "kept",
        "discard_reason": None,
        "sample_count_initial": sample_count,
        "raw_sample_count": sample_count,
        "lower_threshold_seconds": float(lower_threshold),
        "upper_threshold_seconds": float(upper_threshold),
        "dip_p_value": float(p_value),
        "dependency_warning": None,
        "min_raw_edge_samples": MIN_RAW_EDGE_SAMPLES,
        "min_clean_edge_samples": MIN_CLEAN_EDGE_SAMPLES,
        "lower_cleaned_sample_count": len(lower_cleaned),
        "upper_cleaned_sample_count": len(upper_cleaned),
        "sample_count_after_lower": len(lower_cleaned),
        "sample_count_after_upper": len(upper_cleaned),
        "sample_count_final": len(upper_cleaned),
        "discarded_after_lower_threshold": sample_count - len(lower_cleaned),
        "discarded_after_upper_threshold": len(lower_cleaned) - len(upper_cleaned),
        "weight_seconds": float(weight_seconds),
        "formula_lower": formula_lower,
        "formula_upper": "Q3 + 1.5 * IQR",
        "formula_weight": "P25(dados filtrados)",
        "formula_summary": "Amostras com 50+ passam por KDE/Silverman, Dip Test e corte superior por IQR.",
    }
    return analysis, upper_cleaned, build_sample_details(lower_threshold=lower_threshold, upper_threshold=upper_threshold, used_for_weight=used_indexes)


def _build_graph_payload(
    *,
    rows: list[dict[str, Any]],
    product_map: dict[str, dict[str, Any]],
    samples: list[TransitionSample],
    cleaned_edges: dict[tuple[str, str], list[TransitionSample]],
    edge_analyses: dict[tuple[str, str], dict[str, Any]],
    outlier_meta: dict[str, Any],
    trained_at: datetime,
    start_at: str | None,
    temporal_decay: bool,
    half_life_days: float,
    decay_min_weight: float,
) -> dict[str, Any]:
    """Monta o payload final do grafo com nodos, arestas e metadados."""
    scan_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        scan_counts[str(row["barcode"])] += 1

    grouped_samples: dict[tuple[str, str], list[TransitionSample]] = defaultdict(list)
    for sample in samples:
        grouped_samples[_canonical_edge_key(sample.source, sample.target)].append(sample)

    links = []
    for (source, target), raw_edge_samples in grouped_samples.items():
        analysis = edge_analyses.get((source, target), {})
        if analysis.get("decision") != "kept":
            continue

        edge_samples = cleaned_edges.get((source, target)) or raw_edge_samples
        elapsed_values = sorted(sample.elapsed_seconds for sample in edge_samples)
        representative_elapsed = float(
            analysis.get("weight_seconds") if analysis.get("weight_seconds") is not None else (sum(elapsed_values) / len(elapsed_values))
        )
        transition_count = len(edge_samples)
        weighted_transition_count = sum(sample.weight for sample in edge_samples)
        p25_elapsed = _percentile(elapsed_values, 25)
        strength = weighted_transition_count / max(representative_elapsed, 1.0)
        links.append(
            {
                "source": source,
                "target": target,
                "transition_count": transition_count,
                "weighted_transition_count": round(weighted_transition_count, 6),
                "avg_elapsed_seconds": round(representative_elapsed, 6),
                "p25_elapsed_seconds": round(p25_elapsed, 6),
                "min_elapsed_seconds": round(min(elapsed_values), 6),
                "max_elapsed_seconds": round(max(elapsed_values), 6),
                "strength": round(strength, 9),
                "analysis": analysis,
            }
        )

    barcodes = sorted(scan_counts.keys())
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
            "valid_transition_count": sum(
                len(edge_samples) for edge_samples in cleaned_edges.values()
            ),
            "node_count": len(nodes),
            "edge_count": len(links),
            **outlier_meta,
        },
    }


def _apply_force_layout(
    nodes: list[dict[str, Any]], links: list[dict[str, Any]]
) -> None:
    """Distribui os nos em um layout force-directed simples."""
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
                positions[source] = (
                    positions[source][0] - dx * force + jitter_x,
                    positions[source][1] - dy * force + jitter_y,
                )
                positions[target] = (
                    positions[target][0] + dx * force - jitter_x,
                    positions[target][1] + dy * force - jitter_y,
                )

        for node_id in node_ids:
            x, y = positions[node_id]
            positions[node_id] = (x * 0.995, y * 0.995)

    for node in nodes:
        x, y = positions[str(node["id"])]
        node["x"] = round(x, 4)
        node["y"] = round(y, 4)


def _initial_positions(node_ids: list[str]) -> dict[str, tuple[float, float]]:
    """Gera posicoes iniciais em circulo para o layout."""
    radius = max(120.0, len(node_ids) * 4.0)
    positions = {}
    for index, node_id in enumerate(node_ids):
        angle = 2 * math.pi * index / max(len(node_ids), 1)
        positions[node_id] = (math.cos(angle) * radius, math.sin(angle) * radius)
    return positions


def _target_distances(links: list[dict[str, Any]]) -> dict[tuple[str, str], float]:
    """Converte tempos medios de transicao em distancias visuais alvo."""
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
    """Calcula um percentil linear sobre uma lista ordenada de valores."""
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
