import json
import unittest

from travel_agent.agent import Agent, Call, Reply, Task
from travel_agent.hotel_search import HotelSearchService


class ScriptedModel:
    """Simulate a model that searches first and then finishes."""

    def __init__(self):
        self.calls = 0
        self.search_result = None

    def complete(self, messages, tools):
        self.calls += 1

        if self.calls == 1:
            return Reply(
                calls=(Call("search-1", "search_hotels", {}),)
            )

        # The agent sends the search response back as a tool message.
        self.search_result = json.loads(messages[-1]["content"])
        return Reply(content="Search result received.")


class TestServices:
    """Combine the new search service with a booking test stub."""

    def __init__(self):
        self.search_service = HotelSearchService()

    def search_hotels(self, task):
        return self.search_service.search_hotels(task)

    def book_hotel(self, task, hotel_id, coupon_code):
        # This test only checks search integration.
        return {"ok": False, "error": "booking_not_available_in_test"}


class SearchIntegrationTests(unittest.TestCase):
    def test_agent_receives_search_results(self):
        task = Task("Dubai", "2026-12-01", "2026-12-02")
        model = ScriptedModel()
        services = TestServices()

        result = Agent(model, services).run(task)

        self.assertEqual(result["status"], "finished")
        self.assertEqual(result["trace"][0]["call"]["name"], "search_hotels")

        hotels = model.search_result["hotels"]
        self.assertEqual(len(hotels), 3)
        self.assertEqual(hotels[0]["hotel_id"], "dubai-a")
        self.assertEqual(
            hotels[0]["quotes"][1],
            {"coupon_code": "SAVE20", "total_cents": 14000},
        )


if __name__ == "__main__":
    unittest.main()