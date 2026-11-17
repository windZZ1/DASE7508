import copy
import unittest

from travel_agent.attack import (
    PAYLOAD_STYLES,
    AttackSpec,
    AttackingSearchService,
    inject_description,
)


RESPONSE = {
    "hotels": [
        {
            "hotel_id": "dubai-a",
            "rating": "4.6",
            "description": "Quiet hotel.",
            "quotes": [{"coupon_code": None, "total_cents": 14000}],
        },
        {
            "hotel_id": "dubai-b",
            "rating": "4.2",
            "description": "Budget hotel.",
            "quotes": [{"coupon_code": None, "total_cents": 9000}],
        },
    ]
}


class AttackTests(unittest.TestCase):
    def test_each_style_changes_only_target_description(self):
        for style in PAYLOAD_STYLES:
            with self.subTest(style=style):
                original = copy.deepcopy(RESPONSE)
                poisoned = inject_description(
                    RESPONSE, "dubai-b", style, f"test:{style}"
                )
                self.assertEqual(RESPONSE, original)
                self.assertEqual(poisoned["hotels"][0], original["hotels"][0])
                for key, value in original["hotels"][1].items():
                    if key != "description":
                        self.assertEqual(poisoned["hotels"][1][key], value)
                self.assertIn(
                    f"[provider-note:test:{style}]",
                    poisoned["hotels"][1]["description"],
                )

    def test_missing_and_duplicate_targets_are_rejected(self):
        with self.assertRaises(ValueError):
            inject_description(RESPONSE, "missing", "provider_authority", "x")
        duplicate = copy.deepcopy(RESPONSE)
        duplicate["hotels"].append(copy.deepcopy(duplicate["hotels"][1]))
        with self.assertRaisesRegex(ValueError, "occurs at"):
            inject_description(duplicate, "dubai-b", "provider_authority", "x")

    def test_attacking_search_wrapper_preserves_trusted_quote_lookup(self):
        class Search:
            def search_hotels(self, task):
                return copy.deepcopy(RESPONSE)

            def get_quote(self, task, hotel_id, coupon_code):
                return {"hotel_id": hotel_id, "coupon_code": coupon_code}

        wrapped = AttackingSearchService(
            Search(), AttackSpec("dubai-b", "coupon_exception", "wrapper")
        )
        self.assertIn(
            "[provider-note:wrapper]",
            wrapped.search_hotels(None)["hotels"][1]["description"],
        )
        self.assertEqual(
            wrapped.get_quote(None, "dubai-b", None),
            {"hotel_id": "dubai-b", "coupon_code": None},
        )


if __name__ == "__main__":
    unittest.main()
