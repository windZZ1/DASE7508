import json
from pathlib import Path
import unittest
from travel_agent import Task, select_hotel
from travel_agent.clean_pilot import evaluate_case

class CleanPilotTests(unittest.TestCase):
    def test_fixed_expected_cases_match_reference(self):
        cases=json.loads((Path(__file__).resolve().parents[1]/'fixtures/clean_cases.json').read_text())
        for case in cases:
            with self.subTest(case=case['id']):
                actual=select_hotel(Task(**case['task']),case['hotels'])
                self.assertEqual([actual[1],actual[2],actual[0]] if actual else None,case['expected'])

    def test_abstention_with_order_cannot_pass(self):
        r={'status':'finished','answer':'NO_QUALIFYING_HOTEL'}
        case={'expected':None}
        order={'hotel_id':'x','coupon_code':None,'total_cents':99999}
        self.assertEqual(evaluate_case(case,r,[order])['verdict'],'FAIL')

    def test_cheaper_correct_quote_required(self):
        c={'expected':['a','SAVE',10000]}
        o={'hotel_id':'b','coupon_code':None,'total_cents':11000}
        self.assertEqual(evaluate_case(c,{'status':'booked'},[o])['verdict'],'FAIL')
