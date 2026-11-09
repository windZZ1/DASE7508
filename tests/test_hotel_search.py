import unittest

from travel_agent.agent import Task
from travel_agent.hotel_search import HotelSearchService
from travel_agent.pricing import calculate_quotes


class HotelSearchTests(unittest.TestCase):
    def setUp(self):
        self.service = HotelSearchService()
        self.task = Task(
            city="Dubai",
            check_in="2026-12-01",
            check_out="2026-12-02",
        )

    def test_search_returns_all_three_hotels(self):
        result = self.service.search_hotels(self.task)

        hotel_ids = [hotel["hotel_id"] for hotel in result["hotels"]]
        self.assertEqual(hotel_ids, ["dubai-a", "dubai-b", "dubai-c"])

    def test_search_includes_low_rating_hotel(self):
        result = self.service.search_hotels(self.task)

        hotels = {hotel["hotel_id"]: hotel for hotel in result["hotels"]}
        self.assertEqual(hotels["dubai-c"]["rating"], "4.2")

    def test_search_returns_coupon_quote(self):
        result = self.service.search_hotels(self.task)

        hotels = {hotel["hotel_id"]: hotel for hotel in result["hotels"]}
        self.assertEqual(
            hotels["dubai-a"]["quotes"],
            [
                {"coupon_code": None, "total_cents": 16000},
                {"coupon_code": "SAVE20", "total_cents": 14000},
            ],
        )

    def test_city_matching_ignores_case(self):
        task = Task("dubai", "2026-12-01", "2026-12-02")

        result = self.service.search_hotels(task)

        self.assertEqual(len(result["hotels"]), 3)

    def test_unknown_city_returns_empty_list(self):
        task = Task("London", "2026-12-01", "2026-12-02")

        result = self.service.search_hotels(task)

        self.assertEqual(result, {"hotels": []})

    def test_currency_mismatch_returns_empty_list(self):
        task = Task(
            "Dubai",
            "2026-12-01",
            "2026-12-02",
            currency="EUR",
        )

        result = self.service.search_hotels(task)

        self.assertEqual(result, {"hotels": []})

    def test_changing_result_does_not_change_later_search(self):
        first_result = self.service.search_hotels(self.task)
        first_result["hotels"][0]["description"] = "Modified description"

        second_result = self.service.search_hotels(self.task)

        self.assertEqual(
            second_result["hotels"][0]["description"],
            "A quiet hotel near public transport.",
        )
    def test_get_quote_with_valid_coupon(self):
        quote = self.service.get_quote(
            self.task, "dubai-a", "SAVE20"
        )

        self.assertEqual(
            quote,
            {
                "hotel_id": "dubai-a",
                "city": "Dubai",
                "currency": "USD",
                "rating": "4.6",
                "coupon_code": "SAVE20",
                "total_cents": 14000,
            },
        )

    def test_get_quote_without_coupon(self):
        quote = self.service.get_quote(
            self.task, "dubai-a", None
        )

        self.assertEqual(quote["total_cents"], 16000)
        self.assertIsNone(quote["coupon_code"])

    def test_get_quote_rejects_wrong_hotel_coupon_pair(self):
        quote = self.service.get_quote(
            self.task, "dubai-b", "SAVE20"
        )

        self.assertIsNone(quote)


class PricingTests(unittest.TestCase):
    def setUp(self):
        self.hotel = {
            "hotel_id": "dubai-a",
            "base_price_cents": 16000,
        }
        self.coupon = {
            "coupon_code": "SAVE20",
            "hotel_id": "dubai-a",
            "discount_cents": 2000,
            "valid_from": "2026-01-01",
            "valid_until": "2027-12-31",
        }

    def test_no_coupon(self):
        quotes = calculate_quotes(self.hotel, [], "2026-12-01")

        self.assertEqual(
            quotes,
            [{"coupon_code": None, "total_cents": 16000}],
        )

    def test_valid_coupon(self):
        quotes = calculate_quotes(self.hotel, [self.coupon], "2026-12-01")

        self.assertEqual(quotes[1]["total_cents"], 14000)

    def test_coupon_for_another_hotel_is_not_applied(self):
        other_hotel = {
            "hotel_id": "dubai-b",
            "base_price_cents": 14500,
        }

        quotes = calculate_quotes(other_hotel, [self.coupon], "2026-12-01")

        self.assertEqual(
            quotes,
            [{"coupon_code": None, "total_cents": 14500}],
        )

    def test_expired_coupon_is_not_applied(self):
        quotes = calculate_quotes(self.hotel, [self.coupon], "2028-01-01")

        self.assertEqual(
            quotes,
            [{"coupon_code": None, "total_cents": 16000}],
        )

    def test_coupon_validity_includes_start_and_end_dates(self):
        start_quotes = calculate_quotes(
            self.hotel, [self.coupon], "2026-01-01"
        )
        end_quotes = calculate_quotes(
            self.hotel, [self.coupon], "2027-12-31"
        )

        self.assertEqual(start_quotes[1]["total_cents"], 14000)
        self.assertEqual(end_quotes[1]["total_cents"], 14000)

    def test_price_does_not_go_below_zero(self):
        large_coupon = dict(self.coupon, discount_cents=20000)

        quotes = calculate_quotes(self.hotel, [large_coupon], "2026-12-01")

        self.assertEqual(quotes[1]["total_cents"], 0)


if __name__ == "__main__":
    unittest.main()