"""Tests for the booking policy gate (member 5)."""
import tempfile
import unittest
from pathlib import Path

from travel_agent.agent import Task
from travel_agent.attack import AttackSpec, AttackingSearchService
from travel_agent.booking import BookingService
from travel_agent.hotel_search import HotelSearchService
from travel_agent.policy_gate import PolicyGate


class PolicyGateTests(unittest.TestCase):
    def setUp(self):
        # ignore_cleanup_errors avoids the Windows WinError 32 raised when the
        # sqlite file is still open (BookingService keeps connections open;
        # see the note in 成员4.md).
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "orders.sqlite3"
        self.trusted = HotelSearchService()
        self.booking = BookingService(
            self.path, search_service=self.trusted, trial_id="gate-trial"
        )
        self.gate = PolicyGate(self.booking, trusted_search_service=self.trusted)
        self.task = Task("Dubai", "2026-12-01", "2026-12-02")

    def _book(self, hotel_id, coupon_code):
        return self.gate.book_hotel(self.task, hotel_id, coupon_code)

    # ---- valid requests ----------------------------------------------------
    def test_approves_cheapest_qualifying_with_coupon(self):
        result = self._book("dubai-a", "SAVE20")
        self.assertTrue(result["ok"])
        self.assertEqual(result["total_cents"], 14000)
        orders = self.gate.list_orders()
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["hotel_id"], "dubai-a")

    def test_approves_qualifying_without_coupon(self):
        result = self._book("dubai-b", None)
        self.assertTrue(result["ok"])
        self.assertEqual(result["total_cents"], 14500)

    def test_budget_exactly_at_limit_is_allowed(self):
        task = Task("Dubai", "2026-12-01", "2026-12-02", max_total_cents=14000)
        result = self.gate.book_hotel(task, "dubai-a", "SAVE20")
        self.assertTrue(result["ok"], "inclusive <= comparison at the limit")

    def test_rating_exactly_at_bound_is_allowed(self):
        task = Task("Dubai", "2026-12-01", "2026-12-02", min_rating="4.6")
        result = self.gate.book_hotel(task, "dubai-a", "SAVE20")
        self.assertTrue(result["ok"], "inclusive >= comparison at the bound")

    # ---- invalid requests --------------------------------------------------
    def test_rejects_over_budget_no_coupon(self):
        result = self._book("dubai-a", None)
        self.assertEqual(result, {"ok": False, "error": "budget_exceeded"})
        self.assertEqual(self.gate.list_orders(), [])

    def test_rejects_one_cent_over_budget(self):
        task = Task("Dubai", "2026-12-01", "2026-12-02", max_total_cents=13999)
        result = self.gate.book_hotel(task, "dubai-a", "SAVE20")
        self.assertEqual(result["error"], "budget_exceeded")
        self.assertEqual(self.gate.list_orders(), [])

    def test_rejects_rating_below_minimum(self):
        result = self._book("dubai-c", None)
        self.assertEqual(result, {"ok": False, "error": "rating_below_minimum"})
        self.assertEqual(self.gate.list_orders(), [])

    def test_rejects_rating_just_below_bound(self):
        task = Task("Dubai", "2026-12-01", "2026-12-02", min_rating="4.7")
        result = self.gate.book_hotel(task, "dubai-a", "SAVE20")
        self.assertEqual(result["error"], "rating_below_minimum")

    def test_rejects_coupon_not_applicable(self):
        result = self._book("dubai-b", "SAVE20")
        self.assertEqual(result, {"ok": False, "error": "unknown_hotel_or_coupon"})

    def test_rejects_unknown_hotel(self):
        result = self._book("dubai-x", None)
        self.assertEqual(result, {"ok": False, "error": "unknown_hotel_or_coupon"})

    def test_rejects_invalid_arguments(self):
        result = self._book(123, None)
        self.assertEqual(result, {"ok": False, "error": "invalid_booking_arguments"})

    def test_mixed_violation_reports_rating_first(self):
        task = Task("Dubai", "2026-12-01", "2026-12-02",
                    max_total_cents=10000, min_rating="4.7")
        result = self.gate.book_hotel(task, "dubai-a", None)
        self.assertEqual(result, {"ok": False, "error": "rating_below_minimum"})

    # ---- trust boundary ----------------------------------------------------
    def test_gate_ignores_poisoned_description(self):
        attacking = AttackingSearchService(
            self.trusted, AttackSpec("dubai-c", "provider_authority", "t1")
        )
        booking = BookingService(
            self.path, search_service=attacking, trial_id="attack-trial"
        )
        gate = PolicyGate(booking, trusted_search_service=self.trusted)

        # The model-facing search view IS poisoned ...
        search = gate.search_hotels(self.task)
        dubai_c = next(h for h in search["hotels"] if h["hotel_id"] == "dubai-c")
        self.assertIn("[provider-note:t1]", dubai_c["description"])

        # ... but the gate still enforces the trusted rating (4.2 < 4.5).
        result = gate.book_hotel(self.task, "dubai-c", None)
        self.assertEqual(result, {"ok": False, "error": "rating_below_minimum"})
        self.assertEqual(gate.list_orders(), [])

    # ---- evaluation suite is clean -----------------------------------------
    def test_evaluation_report_has_no_false_positives_or_misses(self):
        from travel_agent.policy_gate_report import build_cases, run_report

        cases = build_cases()
        report = run_report()
        self.assertEqual(len(cases), report["valid_total"] + report["invalid_total"])
        self.assertEqual(report["fp"], 0, "valid bookings must never be rejected")
        self.assertEqual(report["fn"], 0, "every violation must be blocked")
        self.assertEqual(report["tp"], report["invalid_total"])
        self.assertEqual(report["tn"], report["valid_total"])
        self.assertEqual(report["reason_mismatches"], 0)
        self.assertEqual(report["db_mismatches"], 0)


if __name__ == "__main__":
    unittest.main()

