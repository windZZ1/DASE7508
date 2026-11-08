import unittest
from travel_agent import Agent, Task, Reply, Call, select_hotel

class Script:
    def __init__(self, replies): self.replies = iter(replies)
    def complete(self, messages, tools): return next(self.replies)

class FakeServices:
    def __init__(self, reject=False): self.orders=[]; self.reject=reject
    def search_hotels(self, task): return {'hotels': HOTELS}
    def book_hotel(self, task, hotel_id, coupon_code):
        if self.reject: return {'ok':False, 'error':'policy_rejected'}
        self.orders.append((hotel_id,coupon_code))
        return {'ok':True,'order_id':'order-1'}

HOTELS=[{'hotel_id':'a','city':'Dubai','currency':'USD','rating':'4.6','description':'Near the beach',
         'quotes':[{'coupon_code':None,'total_cents':16000},{'coupon_code':'SAVE','total_cents':14000}]},
        {'hotel_id':'b','city':'Dubai','currency':'USD','rating':'4.4','description':'Central',
         'quotes':[{'coupon_code':None,'total_cents':9000}]}]
TASK=Task('Dubai','2026-12-01','2026-12-02')
def search(): return Reply(calls=(Call('s','search_hotels',{}),))
def book(): return Reply(calls=(Call('b','book_hotel',{'hotel_id':'a','coupon_code':'SAVE'}),))

class Tests(unittest.TestCase):
    def test_coupon_selection(self): self.assertEqual(select_hotel(TASK,HOTELS),(14000,'a','SAVE'))
    def test_no_option(self): self.assertIsNone(select_hotel(Task('Dubai','2026-12-01','2026-12-02',8000), HOTELS))
    def test_booking(self):
        s=FakeServices(); r=Agent(Script([search(),book()]),s).run(TASK)
        self.assertEqual(r['status'],'booked'); self.assertEqual(s.orders,[('a','SAVE')])
    def test_abstention(self):
        s=FakeServices(); r=Agent(Script([search(),Reply('No qualifying hotel.')]),s).run(TASK)
        self.assertEqual(r['status'],'finished'); self.assertFalse(s.orders)
    def test_gate_rejection(self):
        r=Agent(Script([search(),book(),Reply('Booking rejected.')]),FakeServices(True)).run(TASK)
        self.assertEqual(r['trace'][-1]['result']['ok'],False); self.assertEqual(r['status'],'finished')
    def test_budget_cap(self):
        r=Agent(Script([search() for _ in range(6)]),FakeServices()).run(TASK)
        self.assertEqual(len(r['trace']),6); self.assertEqual(r['status'],'exhausted')
    def test_book_before_search(self):
        s=FakeServices(); Agent(Script([book(),Reply('Stop')]),s).run(TASK)
        self.assertFalse(s.orders)
    def test_one_night(self):
        with self.assertRaises(ValueError): Task('Dubai','2026-12-01','2026-12-03')
    def test_description_preserved(self):
        s=FakeServices(); r=Agent(Script([search(),Reply('Done')]),s).run(TASK)
        self.assertEqual(r['trace'][0]['result']['hotels'],HOTELS)

if __name__ == '__main__': unittest.main()
