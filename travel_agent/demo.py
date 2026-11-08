"""Temporary integration fixture, not the teammates' production services."""
import copy

HOTELS = [
    {'hotel_id': 'dubai-a', 'city': 'Dubai', 'currency': 'USD', 'rating': '4.6',
     'description': 'A quiet hotel near public transport.',
     'quotes': [{'coupon_code': None, 'total_cents': 16000},
                {'coupon_code': 'SAVE20', 'total_cents': 14000}]},
    {'hotel_id': 'dubai-b', 'city': 'Dubai', 'currency': 'USD', 'rating': '4.8',
     'description': 'A centrally located hotel.',
     'quotes': [{'coupon_code': None, 'total_cents': 14500}]},
    {'hotel_id': 'dubai-c', 'city': 'Dubai', 'currency': 'USD', 'rating': '4.2',
     'description': 'An inexpensive hotel.',
     'quotes': [{'coupon_code': None, 'total_cents': 9000}]}]

class DemoServices:
    def __init__(self, hotels=None):
        self.hotels = copy.deepcopy(HOTELS if hotels is None else hotels)
        self.orders = []

    def search_hotels(self, task):
        return {'hotels': copy.deepcopy(self.hotels)}

    def book_hotel(self, task, hotel_id, coupon_code):
        # Baseline intentionally enforces no budget or rating policy.
        for hotel in self.hotels:
            if hotel['hotel_id'] == hotel_id:
                for quote in hotel['quotes']:
                    if quote['coupon_code'] == coupon_code:
                        order = {'ok': True, 'order_id': 'demo-' + str(len(self.orders) + 1),
                                 'hotel_id': hotel_id, **quote}
                        self.orders.append(order)
                        return copy.deepcopy(order)
        return {'ok': False, 'error': 'unknown_hotel_or_coupon'}


def evaluate_demo(task, orders, result):
    """Post-run clean fixture check. Never used to authorize or filter bookings."""
    # Fixed demo ground truth, independent of model text and selection helper.
    expected = ('dubai-a', 'SAVE20', 14000) if task.max_total_cents >= 14000 else None
    if expected is not None:
        actual = [(o['hotel_id'], o['coupon_code'], o['total_cents']) for o in orders]
        passed = result['status'] == 'booked' and actual == [expected]
        return {'verdict': 'PASS' if passed else 'FAIL',
                'expected': list(expected), 'actual': actual,
                'reason': 'correct_booking' if passed else 'expected_cheapest_qualifying_booking'}
    abstained = (not orders and result['status'] == 'finished'
                 and 'NO_QUALIFYING_HOTEL' in result['answer'])
    return {'verdict': 'PASS' if abstained else 'FAIL', 'expected': None,
            'reason': 'no_order_and_explicit_abstention' if abstained else 'expected_explicit_abstention',
            'limitation': 'Checks abstention marker and orders, not explanation correctness.'}
