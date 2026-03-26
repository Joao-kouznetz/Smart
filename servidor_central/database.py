import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_DB_FILENAME = "smart_cart.db"


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
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS carts (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
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
        )
