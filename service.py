import re
from .db import session


class InputError(ValueError):
    pass


def products(path):
    with session(path) as db:
        return [dict(row) for row in db.execute(
            "SELECT id, name, category, price_grosz, icon FROM products WHERE active=1 ORDER BY id"
        )]


def _order(db, order_id):
    row = db.execute(
        "SELECT id, total_grosz, status, created_at FROM orders WHERE id=?", (order_id,)
    ).fetchone()
    return dict(row) if row is not None else None


def create_order(path, payload):
    if not isinstance(payload, dict):
        raise InputError("Nieprawidłowe zamówienie.")
    request_id = payload.get("request_id")
    items = payload.get("items")
    payment_method = payload.get("payment_method", "kiosk")
    if payment_method not in ("kiosk", "cashier"):
        raise InputError("Nieprawidłowy sposób płatności.")
    if not isinstance(request_id, str) or not re.fullmatch(r"[a-f0-9-]{36}", request_id):
        raise InputError("Brak poprawnego identyfikatora żądania.")
    if not isinstance(items, list) or not 1 <= len(items) <= 50:
        raise InputError("Koszyk musi zawierać od 1 do 50 pozycji.")
    quantities = {}
    for item in items:
        if not isinstance(item, dict):
            raise InputError("Nieprawidłowa pozycja koszyka.")
        product_id = item.get("product_id")
        quantity = item.get("quantity")
        if type(product_id) is not int or type(quantity) is not int or quantity < 1 or quantity > 99:
            raise InputError("Nieprawidłowa ilość lub produkt.")
        quantities[product_id] = quantities.get(product_id, 0) + quantity
        if quantities[product_id] > 99:
            raise InputError("Maksymalnie 99 sztuk produktu.")

    with session(path) as db:
        # Acquire the write lock before checking request_id, so retries are serialized.
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute("SELECT id FROM orders WHERE request_id=?", (request_id,)).fetchone()
        if existing:
            order = _order(db, existing["id"])
            if (order["status"] == "oczekuje_przy_kasie") != (payment_method == "cashier"):
                raise InputError("To zamówienie ma już wybrany inny sposób płatności.")
            return order
        ids = list(quantities)
        marks = ",".join("?" for _ in ids)
        rows = db.execute(
            f"SELECT id, name, price_grosz FROM products WHERE active=1 AND id IN ({marks})", ids
        ).fetchall()
        if len(rows) != len(ids):
            raise InputError("Wybrany produkt jest niedostępny.")
        total = sum(row["price_grosz"] * quantities[row["id"]] for row in rows)
        cursor = db.execute(
            "INSERT INTO orders(request_id, total_grosz, status) VALUES (?, ?, ?)",
            (request_id, total, "oczekuje_przy_kasie" if payment_method == "cashier" else "oczekuje")
        )
        db.executemany(
            "INSERT INTO order_items(order_id, product_id, name, quantity, unit_grosz) VALUES (?, ?, ?, ?, ?)",
            [(cursor.lastrowid, r["id"], r["name"], quantities[r["id"]], r["price_grosz"]) for r in rows],
        )
        return _order(db, cursor.lastrowid)


def demo_pay(path, order_id):
    if type(order_id) is not int or order_id < 1:
        raise InputError("Nieprawidłowy numer zamówienia.")
    with session(path) as db:
        db.execute("BEGIN IMMEDIATE")
        order = _order(db, order_id)
        if order is None:
            raise InputError("Nie znaleziono zamówienia.")
        if order["status"] == "oczekuje_przy_kasie":
            raise InputError("To zamówienie należy opłacić przy kasie.")
        if order["status"] == "oczekuje":
            db.execute("UPDATE orders SET status='demo_oplacone' WHERE id=?", (order_id,))
        return _order(db, order_id)
