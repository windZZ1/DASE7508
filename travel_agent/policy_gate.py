"""Booking policy gate (member 5): enforce user constraints before the write.

The baseline ``BookingService`` validates hotel/coupon identity and writes
orders, but deliberately does NOT enforce the user's budget or rating. This
gate wraps ``book_hotel`` so those two hard constraints are checked against
*trusted* hotel facts before any order is written.

Trust boundary
--------------
The model only supplies ``hotel_id`` and ``coupon_code``. The gate ignores the
model-facing search description (which may be poisoned by member 4's attack)
and re-reads the rating and coupon-adjusted total price from the trusted
search service. City, currency, stay length and hotel-coupon pairing are
already enforced on the trusted path by the immutable ``Task`` and by
``get_quote`` (see ``hotel_search`` / ``pricing``).

Rejection reasons (returned as ``{"ok": False, "error": <reason>}``):

* ``invalid_booking_arguments`` - non-string ``hotel_id`` or bad coupon type
* ``unknown_hotel_or_coupon``   - hotel unavailable, wrong city/currency, or
                                  coupon not applicable to that hotel/stay
* ``rating_below_minimum``      - trusted rating < ``task.min_rating``
* ``budget_exceeded``           - trusted ``total_cents`` > ``task.max_total_cents``

Checks run rating first, then budget, so a request that violates both reports
``rating_below_minimum``. A passing request is delegated to the wrapped
booking service, which performs the actual SQLite write and returns the order.
"""

from decimal import Decimal

from .hotel_search import HotelSearchService


class PolicyGate:
    """Wrap a BookingService so every ``book_hotel`` is policy-checked."""

    def __init__(self, booking_service, trusted_search_service=None):
        self.booking_service = booking_service
        self.trusted_search = (
            trusted_search_service
            or getattr(booking_service, "search_service", None)
            or HotelSearchService()
        )

    # ---- agent tool surface ------------------------------------------------
    def search_hotels(self, task):
        """Model-facing search (may be the poisoned view in attack conditions)."""
        return self.booking_service.search_hotels(task)

    def get_quote(self, task, hotel_id, coupon_code):
        """Trusted quote lookup, independent of the model-facing description."""
        return self.trusted_search.get_quote(task, hotel_id, coupon_code)

    def book_hotel(self, task, hotel_id, coupon_code):
        decision = self.evaluate(task, hotel_id, coupon_code)
        if not decision["ok"]:
            return decision
        return self.booking_service.book_hotel(task, hotel_id, coupon_code)

    # ---- policy decision (pure, no write) ----------------------------------
    def evaluate(self, task, hotel_id, coupon_code):
        """Return ``{"ok": True, "quote": ...}`` or ``{"ok": False, "error": ...}``."""
        if not isinstance(hotel_id, str) or not hotel_id or not (
            coupon_code is None or isinstance(coupon_code, str)
        ):
            return {"ok": False, "error": "invalid_booking_arguments"}

        quote = self.trusted_search.get_quote(task, hotel_id, coupon_code)
        if quote is None:
            return {"ok": False, "error": "unknown_hotel_or_coupon"}

        # Rating and budget are the two hard constraints the baseline omits.
        # City, currency, dates and hotel-coupon pairing were already checked
        # on the trusted path by get_quote and the immutable Task.
        if Decimal(str(quote["rating"])) < Decimal(task.min_rating):
            return {"ok": False, "error": "rating_below_minimum"}

        if quote["total_cents"] > task.max_total_cents:
            return {"ok": False, "error": "budget_exceeded"}

        return {"ok": True, "quote": quote}

    # ---- store introspection / reset (delegated to the booking service) ----
    def get_order(self, order_id):
        return self.booking_service.get_order(order_id)

    def list_orders(self):
        return self.booking_service.list_orders()

    def reset(self, trial_id=None):
        return self.booking_service.reset(trial_id)
