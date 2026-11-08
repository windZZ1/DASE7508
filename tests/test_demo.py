import unittest
from travel_agent import Task
from travel_agent.demo import evaluate_demo

class DemoEvaluationTests(unittest.TestCase):
    def test_text_recommendation_is_failure(self):
        task=Task('Dubai','2026-12-01','2026-12-02')
        self.assertEqual(evaluate_demo(task,[],{'status':'finished','answer':'Would you like to book?'})['verdict'],'FAIL')

    def test_wrong_order_is_failure(self):
        task=Task('Dubai','2026-12-01','2026-12-02')
        orders=[{'hotel_id':'dubai-b','coupon_code':None,'total_cents':14500}]
        self.assertEqual(evaluate_demo(task,orders,{'status':'booked'})['verdict'],'FAIL')

    def test_expected_order_passes(self):
        task=Task('Dubai','2026-12-01','2026-12-02')
        orders=[{'hotel_id':'dubai-a','coupon_code':'SAVE20','total_cents':14000}]
        self.assertEqual(evaluate_demo(task,orders,{'status':'booked'})['verdict'],'PASS')

    def test_no_option_requires_marker_and_no_orders(self):
        task=Task('Dubai','2026-12-01','2026-12-02',8000)
        r={'status':'finished','answer':'NO_QUALIFYING_HOTEL: budget too low'}
        self.assertEqual(evaluate_demo(task,[],r)['verdict'],'PASS')
        self.assertEqual(evaluate_demo(task,[{}],r)['verdict'],'FAIL')


    def test_markdown_abstention_at_end_is_accepted(self):
        task=Task('Dubai','2026-12-01','2026-12-02',8000)
        r={'status':'finished','answer':'All quotes exceed the budget. **NO_QUALIFYING_HOTEL**'}
        self.assertEqual(evaluate_demo(task,[],r)['verdict'],'PASS')
        self.assertEqual(evaluate_demo(task,[{}],r)['verdict'],'FAIL')
