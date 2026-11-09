"""Mock hotel search service."""

import json
from pathlib import Path

from .pricing import calculate_quotes


# Project root is the parent of the travel_agent directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = PROJECT_ROOT / "fixtures"


class HotelSearchService:
    def __init__(
        self,
        hotels_path=None,
        coupons_path=None,
    ):
        self.hotels_path = Path(hotels_path) if hotels_path else (
            FIXTURES_DIR / "hotels.json"
        )
        self.coupons_path = Path(coupons_path) if coupons_path else (
            FIXTURES_DIR / "coupons.json"
        )

    def search_hotels(self, task):
        """Search available hotels for the task's city and currency."""
        with self.hotels_path.open("r", encoding="utf-8") as file:
            hotels = json.load(file)

        with self.coupons_path.open("r", encoding="utf-8") as file:
            coupons = json.load(file)

        results = []

        for hotel in hotels:
            if not hotel["available"]:
                continue

            if hotel["city"].casefold() != task.city.casefold():
                continue

            if hotel["currency"] != task.currency:
                continue

            results.append(
                {
                    "hotel_id": hotel["hotel_id"],
                    "name": hotel["name"],
                    "city": hotel["city"],
                    "currency": hotel["currency"],
                    "rating": hotel["rating"],
                    "description": hotel["description"],
                    "quotes": calculate_quotes(
                        hotel,
                        coupons,
                        task.check_in,
                    ),
                }
            )
    
        return {"hotels": results}
    def get_quote(self, task, hotel_id, coupon_code):
        """
        Return a quote for a specific hotel and coupon.

        Return None if the hotel or coupon is not available for the task.
        """
        result = self.search_hotels(task)

        for hotel in result["hotels"]:
            if hotel["hotel_id"] != hotel_id:
                continue

            for quote in hotel["quotes"]:
                if quote["coupon_code"] == coupon_code:
                    return {
                        "hotel_id": hotel["hotel_id"],
                        "city": hotel["city"],
                        "currency": hotel["currency"],
                        "rating": hotel["rating"],
                        "coupon_code": quote["coupon_code"],
                        "total_cents": quote["total_cents"],
                    }

        return None