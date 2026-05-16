import csv
import json
import math
import random
import sqlite3
from collections import Counter
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from pathlib import Path
from typing import Any, Literal

from mock_supermercado.data import CATALOG_CSV_PATH
from servidor_central.database import SCHEMA_SQL, get_db_path

WALKING_SPEED_KMH = 3.0
WALKING_SPEED_MPS = WALKING_SPEED_KMH * 1000 / 3600
SHELF_PICKUP_SECONDS = 2.0
DEFAULT_START_WINDOW_HOURS = 10
AISLE_LENGTH_M = 20.0
AISLE_GAP_M = 1.0
GONDOLA_WIDTH_M = 1.0
TravelTimeDistribution = Literal["fixed", "normal", "right-tail", "bimodal"]
TRAVEL_TIME_DISTRIBUTIONS = ("fixed", "normal", "right-tail", "bimodal")
MIN_RANDOM_TRAVEL_SECONDS = 0.1
BIMODAL_FAST_GROUP_PROBABILITY = 0.5
BIMODAL_FAST_MEAN_SECONDS = 0.3
BIMODAL_FAST_STANDARD_DEVIATION_SECONDS = 0.04


class SimulationConfigError(ValueError):
    pass


@dataclass(frozen=True)
class SimulationResult:
    people_count: int
    cart_ids: list[str]
    interaction_count: int
    first_event_at: str | None
    last_event_at: str | None


@dataclass(frozen=True)
class ProductLocation:
    barcode: str
    name: str
    aisle: str
    dist_to_aisle_m: float


def distance_between_products(
    barcode_a: str,
    barcode_b: str,
    supermarket_layout: dict[str, list[dict[str, Any]]],
    *,
    aisle_gap_m: float = AISLE_GAP_M,
    aisle_length_m: float = AISLE_LENGTH_M,
    gondola_width_m: float = GONDOLA_WIDTH_M,
) -> float:
    """Calcula a distancia estimada entre dois produtos no layout do supermercado."""
    locations = _build_location_index(supermarket_layout)
    product_a = _get_location(locations, barcode_a)
    product_b = _get_location(locations, barcode_b)

    if product_a.aisle == product_b.aisle:
        return abs(product_a.dist_to_aisle_m - product_b.dist_to_aisle_m)

    row_a, col_a = _parse_aisle_position(product_a.aisle)
    row_b, col_b = _parse_aisle_position(product_b.aisle)
    column_step = 1.0 if col_a != col_b else 0.0

    if row_a == row_b:
        return column_step * aisle_gap_m

    route_same_side = product_a.dist_to_aisle_m + product_b.dist_to_aisle_m
    route_other_side = abs(aisle_length_m - product_a.dist_to_aisle_m) + abs(
        aisle_length_m - product_b.dist_to_aisle_m
    )
    base_distance = min(route_same_side, route_other_side)
    row_distance = abs(row_a - row_b) * (aisle_gap_m + gondola_width_m)
    column_distance = column_step * aisle_gap_m
    return base_distance + row_distance + column_distance


def example_distance_between_products_calls(
    supermarket_layout: dict[str, list[dict[str, Any]]],
) -> dict[str, float]:
    """Executa as chamadas solicitadas de distance_between_products."""
    return {
        "7891000100003_7891000100026": distance_between_products(
            "7891000100003",
            "7891000100026",
            supermarket_layout,
        ),
        "7891000100003_7891000100048": distance_between_products(
            "7891000100003",
            "7891000100048",
            supermarket_layout,
        ),
        "7891000100003_7891000100002": distance_between_products(
            "7891000100003",
            "7891000100002",
            supermarket_layout,
        ),
    }


def populate_simulated_purchases(
    people_count: int,
    supermarket_layout: dict[str, list[dict[str, Any]]],
    personas: list[dict[str, Any]],
    persona_proportions: list[float],
    *,
    db_path: Path | None = None,
    catalog_csv_path: Path | None = None,
    cart_id_prefix: str = "sim-cart",
    seed: int | None = None,
    start_at: datetime | None = None,
    start_window_hours: int = DEFAULT_START_WINDOW_HOURS,
    aisle_gap_m: float = AISLE_GAP_M,
    clear_existing_data: bool = False,
    travel_time_distribution: TravelTimeDistribution = "fixed",
) -> SimulationResult:
    """Gera compras simuladas, grava os dados no banco e devolve um resumo da simulacao."""
    if people_count < 0:
        raise SimulationConfigError("people_count deve ser maior ou igual a zero.")
    _validate_travel_time_distribution(travel_time_distribution)

    rng = random.Random(seed)
    catalog = _read_catalog_by_barcode(catalog_csv_path or CATALOG_CSV_PATH)
    locations = _build_location_index(supermarket_layout)
    _validate_personas(personas, persona_proportions, catalog, locations)

    database_path = db_path or get_db_path()
    with closing(_connect(database_path)) as connection:
        if clear_existing_data:
            with connection:
                _clear_simulation_data(connection)

    if people_count == 0:
        return SimulationResult(
            people_count=0,
            cart_ids=[],
            interaction_count=0,
            first_event_at=None,
            last_event_at=None,
        )

    base_start_at = start_at or datetime.now(timezone.utc)
    if base_start_at.tzinfo is None:
        base_start_at = base_start_at.replace(tzinfo=timezone.utc)

    cart_ids: list[str] = []
    first_event_at: datetime | None = None
    last_event_at: datetime | None = None
    interaction_count = 0

    with closing(_connect(database_path)) as connection:
        with connection:
            run_token = base_start_at.strftime("%Y%m%d%H%M%S")
            for person_index in range(people_count):
                persona = _choose_persona(personas, persona_proportions, rng)
                route = [dict(product) for product in persona["products"]]
                rng.shuffle(route)

                cart_id = _build_cart_id(
                    connection, cart_id_prefix, run_token, person_index + 1
                )
                event_times = _build_event_times(
                    route,
                    supermarket_layout,
                    rng,
                    base_start_at,
                    start_window_hours,
                    aisle_gap_m,
                    travel_time_distribution,
                )
                if not event_times:
                    continue

                cart_ids.append(cart_id)
                first_event_at = min(first_event_at or event_times[0], event_times[0])
                last_event_at = max(last_event_at or event_times[-1], event_times[-1])
                interaction_count += len(route)

                _insert_cart(connection, cart_id, event_times[0], event_times[-1])
                _insert_cart_items(
                    connection, cart_id, route, catalog, event_times, event_times[-1]
                )
                _insert_interactions(
                    connection, cart_id, route, event_times, persona["name"]
                )

    return SimulationResult(
        people_count=len(cart_ids),
        cart_ids=cart_ids,
        interaction_count=interaction_count,
        first_event_at=first_event_at.isoformat() if first_event_at else None,
        last_event_at=last_event_at.isoformat() if last_event_at else None,
    )


def _connect(db_path: Path) -> sqlite3.Connection:
    """Abre a conexao SQLite e garante que o schema esteja inicializado."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.executescript(SCHEMA_SQL)
    return connection


def _clear_simulation_data(connection: sqlite3.Connection) -> None:
    """Remove todos os dados simulados mantendo o schema intacto."""
    connection.executescript("""
        DELETE FROM cart_interactions;
        DELETE FROM cart_items;
        DELETE FROM carts;
        DELETE FROM sqlite_sequence WHERE name IN ('cart_interactions', 'cart_items', 'carts');
        """)


def _read_catalog_by_barcode(csv_path: Path) -> dict[str, dict[str, Any]]:
    """Le o catalogo CSV e organiza os produtos por barcode."""
    with csv_path.open(mode="r", encoding="utf-8", newline="") as catalog_file:
        reader = csv.DictReader(catalog_file)
        catalog = {}
        for row in reader:
            catalog[row["barcode"]] = {
                "barcode": row["barcode"],
                "name": row["name"],
                "price": float(row["price"]),
                "category": row["category"],
                "aisle": row["aisle"],
            }
    return catalog


def _build_location_index(
    supermarket_layout: dict[str, list[dict[str, Any]]],
) -> dict[str, ProductLocation]:
    """Transforma o layout do supermercado em um indice de localizacao por barcode."""
    locations: dict[str, ProductLocation] = {}
    for aisle, products in supermarket_layout.items():
        for product in products:
            barcode = str(product["barcode"])
            if barcode in locations:
                raise SimulationConfigError(f"Produto duplicado no layout: {barcode}.")
            distance_to_aisle = product.get("dist_to_aisle_m")
            if distance_to_aisle is None:
                raise SimulationConfigError(
                    f"Produto sem distancia para corredor no layout: {barcode}."
                )
            locations[barcode] = ProductLocation(
                barcode=barcode,
                name=str(product["name"]),
                aisle=aisle,
                dist_to_aisle_m=float(distance_to_aisle),
            )
    return locations


def _get_location(
    locations: dict[str, ProductLocation], barcode: str
) -> ProductLocation:
    """Busca a localizacao de um produto pelo barcode e falha se ele nao existir."""
    try:
        return locations[barcode]
    except KeyError as exc:
        raise SimulationConfigError(
            f"Produto sem posicao no layout: {barcode}."
        ) from exc


def _validate_personas(
    personas: list[dict[str, Any]],
    persona_proportions: list[float],
    catalog: dict[str, dict[str, Any]],
    locations: dict[str, ProductLocation],
) -> None:
    """Valida se as personas, proporcoes e produtos estao consistentes com catalogo e layout."""
    if not personas:
        raise SimulationConfigError("A lista de personas nao pode ser vazia.")
    if len(personas) != len(persona_proportions):
        raise SimulationConfigError(
            "Cada persona precisa ter uma proporcao correspondente."
        )
    if any(proportion < 0 for proportion in persona_proportions):
        raise SimulationConfigError("Proporcoes de personas nao podem ser negativas.")
    if sum(persona_proportions) <= 0:
        raise SimulationConfigError("A soma das proporcoes precisa ser maior que zero.")

    for persona in personas:
        if not persona.get("name"):
            raise SimulationConfigError("Toda persona precisa ter name.")
        products = persona.get("products")
        if not products:
            raise SimulationConfigError(f"Persona sem produtos: {persona['name']}.")
        for product in products:
            barcode = str(product["barcode"])
            expected_name = str(product["name"])
            catalog_product = catalog.get(barcode)
            if catalog_product is None:
                raise SimulationConfigError(
                    f"Produto da persona nao existe no catalogo: {barcode}."
                )
            if catalog_product["name"] != expected_name:
                raise SimulationConfigError(
                    f"Nome divergente para {barcode}: persona='{expected_name}', "
                    f"catalogo='{catalog_product['name']}'."
                )
            location = _get_location(locations, barcode)
            if location.name != expected_name:
                raise SimulationConfigError(
                    f"Nome divergente para {barcode}: layout='{location.name}', "
                    f"persona='{expected_name}'."
                )


def _validate_travel_time_distribution(
    travel_time_distribution: TravelTimeDistribution,
) -> None:
    """Valida o modo de distribuicao usado para gerar tempos entre produtos."""
    if travel_time_distribution not in TRAVEL_TIME_DISTRIBUTIONS:
        options = ", ".join(TRAVEL_TIME_DISTRIBUTIONS)
        raise SimulationConfigError(
            f"travel_time_distribution deve ser um de: {options}."
        )


def _choose_persona(
    personas: list[dict[str, Any]],
    persona_proportions: list[float],
    rng: random.Random,
) -> dict[str, Any]:
    """Escolhe uma persona aleatoriamente com base nas proporcoes informadas."""
    return rng.choices(personas, weights=persona_proportions, k=1)[0]


def _build_cart_id(
    connection: sqlite3.Connection,
    cart_id_prefix: str,
    run_token: str,
    sequence: int,
) -> str:
    """Monta um identificador unico para o carrinho dentro da simulacao."""
    candidate = f"{cart_id_prefix}-{run_token}-{sequence:04d}"
    suffix = 1
    while _cart_exists(connection, candidate):
        candidate = f"{cart_id_prefix}-{run_token}-{sequence:04d}-{suffix}"
        suffix += 1
    return candidate


def _cart_exists(connection: sqlite3.Connection, cart_id: str) -> bool:
    """Verifica se um carrinho ja existe na tabela carts."""
    row = connection.execute("SELECT id FROM carts WHERE id = ?", (cart_id,)).fetchone()
    return row is not None


def _build_event_times(
    route: list[dict[str, str]],
    supermarket_layout: dict[str, list[dict[str, Any]]],
    rng: random.Random,
    base_start_at: datetime,
    start_window_hours: int,
    aisle_gap_m: float,
    travel_time_distribution: TravelTimeDistribution,
) -> list[datetime]:
    """Calcula os instantes dos eventos de compra a partir da rota e da velocidade de caminhada."""
    if not route:
        return []

    start_offset_seconds = rng.randint(0, max(start_window_hours, 0) * 3600)
    event_times = [base_start_at + timedelta(seconds=start_offset_seconds)]

    for previous_product, next_product in zip(route, route[1:]):
        distance_m = distance_between_products(
            previous_product["barcode"],
            next_product["barcode"],
            supermarket_layout,
            aisle_gap_m=aisle_gap_m,
        )
        base_travel_seconds = distance_m / WALKING_SPEED_MPS + SHELF_PICKUP_SECONDS
        travel_seconds = _sample_travel_seconds(
            base_travel_seconds,
            rng,
            travel_time_distribution,
        )
        event_times.append(event_times[-1] + timedelta(seconds=travel_seconds))

    return event_times


def _sample_travel_seconds(
    base_travel_seconds: float,
    rng: random.Random,
    travel_time_distribution: TravelTimeDistribution,
) -> float:
    """Gera um intervalo entre scans mantendo o tempo deterministico como padrao."""
    if travel_time_distribution == "fixed":
        return base_travel_seconds

    if base_travel_seconds <= 0:
        return MIN_RANDOM_TRAVEL_SECONDS

    if travel_time_distribution == "normal":
        standard_deviation = max(base_travel_seconds * 0.25, 1.0)
        return max(
            MIN_RANDOM_TRAVEL_SECONDS,
            rng.gauss(base_travel_seconds, standard_deviation),
        )

    if travel_time_distribution == "right-tail":
        return _sample_right_tail_seconds(base_travel_seconds, rng)

    if travel_time_distribution == "bimodal":
        if rng.random() < BIMODAL_FAST_GROUP_PROBABILITY:
            return _sample_bimodal_fast_seconds(rng)
        return _sample_right_tail_seconds(base_travel_seconds, rng)

    _validate_travel_time_distribution(travel_time_distribution)
    return base_travel_seconds


def _sample_right_tail_seconds(
    base_travel_seconds: float,
    rng: random.Random,
) -> float:
    """Gera amostras com pico perto do tempo esperado e cauda longa a direita."""
    sigma = 0.7
    log_mode = math.log(max(base_travel_seconds, MIN_RANDOM_TRAVEL_SECONDS))
    return max(
        MIN_RANDOM_TRAVEL_SECONDS,
        rng.lognormvariate(log_mode + sigma**2, sigma),
    )


def _sample_bimodal_fast_seconds(rng: random.Random) -> float:
    """Gera o grupo rapido do bimodal: normal estreita com pico em 0.3s."""
    return max(
        MIN_RANDOM_TRAVEL_SECONDS,
        rng.gauss(
            BIMODAL_FAST_MEAN_SECONDS,
            BIMODAL_FAST_STANDARD_DEVIATION_SECONDS,
        ),
    )


def _parse_aisle_position(aisle: str) -> tuple[int, int]:
    """Converte um identificador de corredor como A1 em coordenadas ordenaveis."""
    match = re.fullmatch(r"([A-Za-z]+)(\d+)", aisle.strip())
    if match is None:
        raise SimulationConfigError(f"Corredor invalido no layout: {aisle}.")

    letters, number = match.groups()
    row_index = 0
    for char in letters.upper():
        row_index = row_index * 26 + (ord(char) - ord("A") + 1)

    return row_index, int(number)


def _insert_cart(
    connection: sqlite3.Connection,
    cart_id: str,
    created_at: datetime,
    updated_at: datetime,
) -> None:
    """Insere um carrinho simulado na tabela carts."""
    connection.execute(
        """
        INSERT INTO carts (id, created_at, updated_at)
        VALUES (?, ?, ?)
        """,
        (cart_id, created_at.isoformat(), updated_at.isoformat()),
    )


def _insert_cart_items(
    connection: sqlite3.Connection,
    cart_id: str,
    route: list[dict[str, str]],
    catalog: dict[str, dict[str, Any]],
    event_times: list[datetime],
    updated_at: datetime,
) -> None:
    """Agrupa os produtos da rota por barcode e grava os itens do carrinho."""
    quantities = Counter(product["barcode"] for product in route)
    first_seen_at = {}
    for product, event_time in zip(route, event_times):
        first_seen_at.setdefault(product["barcode"], event_time)

    for barcode, quantity in quantities.items():
        catalog_product = catalog[barcode]
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cart_id,
                barcode,
                quantity,
                catalog_product["name"],
                catalog_product["price"],
                catalog_product["category"],
                catalog_product["aisle"],
                first_seen_at[barcode].isoformat(),
                updated_at.isoformat(),
            ),
        )


def _insert_interactions(
    connection: sqlite3.Connection,
    cart_id: str,
    route: list[dict[str, str]],
    event_times: list[datetime],
    persona_name: str,
) -> None:
    """Registra os eventos de interacao do carrinho para cada produto adicionado."""
    for product, event_time in zip(route, event_times):
        connection.execute(
            """
            INSERT INTO cart_interactions (cart_id, event_type, barcode, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                cart_id,
                "item_added",
                product["barcode"],
                json.dumps({"quantity": 1, "persona": persona_name}),
                event_time.isoformat(),
            ),
        )
