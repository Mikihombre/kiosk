import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


SEED_PRODUCTS = [
    (1, "Burger klasyczny", "Restauracja", 2490, "🍔"),
    (2, "Frytki", "Restauracja", 990, "🍟"),
    (3, "Lemoniada", "Restauracja", 890, "🥤"),
    (4, "Sałatka", "Restauracja", 2190, "🥗"),
    (5, "Woda", "Sklep", 490, "💧"),
    (6, "Kanapka", "Sklep", 1390, "🥪"),
    (7, "Jabłko", "Sklep", 350, "🍎"),
    (8, "Kawa", "Sklep", 1190, "☕"),
]


def default_db_path():
    directory = Path(os.environ.get("KIOSK_DATA_DIR", "data"))
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "kiosk.sqlite3"


def connect(path):
    connection = sqlite3.connect(path, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


@contextmanager
def session(path):
    db = connect(path)
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize(path):
    with session(path) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price_grosz INTEGER NOT NULL CHECK(price_grosz >= 0),
                icon TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL UNIQUE,
                total_grosz INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'oczekuje',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL REFERENCES orders(id),
                product_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit_grosz INTEGER NOT NULL
            );
        """)
        db.executemany(
            "INSERT OR IGNORE INTO products(id, name, category, price_grosz, icon) VALUES (?, ?, ?, ?, ?)",
            SEED_PRODUCTS,
        )
