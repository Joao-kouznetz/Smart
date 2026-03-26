import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_DB_FILENAME = "smart_cart.db"
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS carts (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cart_items (
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
    FOREIGN KEY (cart_id) REFERENCES carts (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cart_interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cart_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    barcode TEXT,
    payload_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (cart_id) REFERENCES carts (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_cart_items_cart_id
ON cart_items (cart_id);

CREATE INDEX IF NOT EXISTS idx_cart_interactions_cart_id
ON cart_interactions (cart_id);
"""


def get_db_path() -> Path:
    configured_path = os.getenv("SMART_CART_DB_PATH")
    if configured_path:
        return Path(configured_path)
    return Path(__file__).resolve().parent / DEFAULT_DB_FILENAME


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> sqlite3.Connection:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(db_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def init_db() -> None:
    with get_connection() as connection:
        if _needs_schema_rebuild(connection):
            _rebuild_schema(connection)
        connection.executescript(SCHEMA_SQL)


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _get_column_names(connection: sqlite3.Connection, table_name: str) -> set[str]:
    if not _table_exists(connection, table_name):
        return set()

    columns = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {column["name"] for column in columns}


def _get_foreign_key_targets(connection: sqlite3.Connection, table_name: str) -> set[str]:
    if not _table_exists(connection, table_name):
        return set()

    foreign_keys = connection.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()
    return {foreign_key["table"] for foreign_key in foreign_keys}


def _needs_schema_rebuild(connection: sqlite3.Connection) -> bool:
    carts_columns = _get_column_names(connection, "carts")
    if "status" in carts_columns:
        return True

    cart_items_targets = _get_foreign_key_targets(connection, "cart_items")
    if cart_items_targets and cart_items_targets != {"carts"}:
        return True

    cart_interactions_targets = _get_foreign_key_targets(connection, "cart_interactions")
    if cart_interactions_targets and cart_interactions_targets != {"carts"}:
        return True

    return False


def _rebuild_schema(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = OFF;")
    connection.executescript(
        """
        CREATE TABLE carts_rebuild (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE cart_items_rebuild (
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
            FOREIGN KEY (cart_id) REFERENCES carts_rebuild (id) ON DELETE CASCADE
        );

        CREATE TABLE cart_interactions_rebuild (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cart_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            barcode TEXT,
            payload_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (cart_id) REFERENCES carts_rebuild (id) ON DELETE CASCADE
        );
        """
    )

    if _table_exists(connection, "carts"):
        connection.execute(
            """
            INSERT INTO carts_rebuild (id, created_at, updated_at)
            SELECT id, created_at, updated_at
            FROM carts
            """
        )

    if _table_exists(connection, "cart_items"):
        connection.execute(
            """
            INSERT INTO cart_items_rebuild (
                id,
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
            SELECT
                id,
                cart_id,
                barcode,
                quantity,
                name,
                price,
                category,
                aisle,
                created_at,
                updated_at
            FROM cart_items
            """
        )

    if _table_exists(connection, "cart_interactions"):
        connection.execute(
            """
            INSERT INTO cart_interactions_rebuild (id, cart_id, event_type, barcode, payload_json, created_at)
            SELECT id, cart_id, event_type, barcode, payload_json, created_at
            FROM cart_interactions
            """
        )

    connection.executescript(
        """
        DROP TABLE IF EXISTS cart_interactions;
        DROP TABLE IF EXISTS cart_items;
        DROP TABLE IF EXISTS carts;

        ALTER TABLE carts_rebuild RENAME TO carts;
        ALTER TABLE cart_items_rebuild RENAME TO cart_items;
        ALTER TABLE cart_interactions_rebuild RENAME TO cart_interactions;

        CREATE INDEX IF NOT EXISTS idx_cart_items_cart_id
        ON cart_items (cart_id);

        CREATE INDEX IF NOT EXISTS idx_cart_interactions_cart_id
        ON cart_interactions (cart_id);
        """
    )
    connection.execute("PRAGMA foreign_keys = ON;")
