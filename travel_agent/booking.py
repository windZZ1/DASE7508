"""Transactional, local-only booking store for controlled experiments."""

import sqlite3
from pathlib import Path

from .hotel_search import HotelSearchService


class BookingService:
    """Baseline booking service; policy constraints belong to the optional gate."""

    def __init__(self, db_path, search_service=None, trial_id=None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.search_service = search_service or HotelSearchService()
        self.trial_id = trial_id
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trial_id TEXT, hotel_id TEXT NOT NULL,
                check_in TEXT NOT NULL, check_out TEXT NOT NULL,
                currency TEXT NOT NULL, total_cents INTEGER NOT NULL,
                coupon_code TEXT, status TEXT NOT NULL DEFAULT 'confirmed'
            )""")

    def _connect(self):
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        return db

    def search_hotels(self, task):
        return self.search_service.search_hotels(task)

    def book_hotel(self, task, hotel_id, coupon_code):
        if not isinstance(hotel_id, str) or not hotel_id or not (
            coupon_code is None or isinstance(coupon_code, str)
        ):
            return {"ok": False, "error": "invalid_booking_arguments"}
        # Recompute from local fixtures, never from the model-facing description.
        quote = self.search_service.get_quote(task, hotel_id, coupon_code)
        if quote is None:
            return {"ok": False, "error": "unknown_hotel_or_coupon"}
        with self._connect() as db:
            cursor = db.execute(
                """INSERT INTO orders
                (trial_id, hotel_id, check_in, check_out, currency,
                 total_cents, coupon_code, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'confirmed')""",
                (self.trial_id, hotel_id, task.check_in, task.check_out,
                 quote["currency"], quote["total_cents"], coupon_code),
            )
            order_id = f"ord-{cursor.lastrowid:06d}"
        return {"ok": True, "order_id": order_id, "hotel_id": hotel_id,
                "coupon_code": coupon_code, "total_cents": quote["total_cents"]}

    def get_order(self, order_id):
        try:
            number = int(order_id.removeprefix("ord-"))
        except (AttributeError, ValueError):
            return None
        with self._connect() as db:
            row = db.execute("SELECT * FROM orders WHERE id = ?", (number,)).fetchone()
        return self._order_dict(row) if row else None

    def list_orders(self):
        with self._connect() as db:
            rows = db.execute("SELECT * FROM orders ORDER BY id").fetchall()
        return [self._order_dict(row) for row in rows]

    @staticmethod
    def _order_dict(row):
        result = dict(row)
        result["order_id"] = f"ord-{result.pop('id'):06d}"
        return result

    def reset(self, trial_id=None):
        """Clear all orders before a trial and optionally label new orders."""
        with self._connect() as db:
            db.execute("DELETE FROM orders")
            db.execute("DELETE FROM sqlite_sequence WHERE name = 'orders'")
        self.trial_id = trial_id
