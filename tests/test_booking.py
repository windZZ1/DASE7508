import tempfile
import unittest
from pathlib import Path

from travel_agent.agent import Task
from travel_agent.booking import BookingService


class BookingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "orders.sqlite3"
        self.service = BookingService(self.path, trial_id="trial-1")
        self.task = Task("Dubai", "2026-12-01", "2026-12-02")

    def test_create_query_and_persist(self):
        result = self.service.book_hotel(self.task, "dubai-a", "SAVE20")
        self.assertTrue(result["ok"])
        self.assertEqual(result["total_cents"], 14000)
        order = BookingService(self.path).get_order(result["order_id"])
        self.assertEqual(order["status"], "confirmed")
        self.assertEqual(order["trial_id"], "trial-1")
        self.assertEqual(order["total_cents"], 14000)

    def test_invalid_coupon_has_no_write(self):
        result = self.service.book_hotel(self.task, "dubai-b", "SAVE20")
        self.assertEqual(result["error"], "unknown_hotel_or_coupon")
        self.assertEqual(self.service.list_orders(), [])

    def test_baseline_allows_low_rating_for_gate_experiment(self):
        self.assertTrue(self.service.book_hotel(self.task, "dubai-c", None)["ok"])

    def test_reset_clears_orders_and_labels_next_trial(self):
        self.service.book_hotel(self.task, "dubai-a", None)
        self.service.reset("trial-2")
        self.assertEqual(self.service.list_orders(), [])
        result = self.service.book_hotel(self.task, "dubai-b", None)
        self.assertEqual(result["order_id"], "ord-000001")
        self.assertEqual(self.service.get_order(result["order_id"])["trial_id"], "trial-2")


if __name__ == "__main__":
    unittest.main()
