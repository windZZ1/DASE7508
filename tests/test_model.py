import json
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock
from travel_agent import Agent, Task
from travel_agent.agent import TOOLS
from travel_agent.demo import DemoServices
from travel_agent.model import ChatModel, ModelResponseError


def response(name=None, args=None, reason=None):
    calls = None if name is None else [NS(id='call-1', function=NS(name=name, arguments=args))]
    r = Mock()
    r.choices = [NS(finish_reason=reason or ('tool_calls' if name else 'stop'),
                    message=NS(content=None if name else 'No qualifying hotel.', tool_calls=calls))]
    r.usage.model_dump.return_value = {'total_tokens': 42}
    r.model_dump.return_value = {'id': 'response-1'}
    return r

class AdapterTests(unittest.TestCase):
    def test_full_api_loop_and_wire_format(self):
        client = Mock()
        client.chat.completions.create.side_effect = [
            response('search_hotels', '{}'),
            response('book_hotel', '{"hotel_id":"dubai-a","coupon_code":"SAVE20"}')]
        model = ChatModel('test-model', client=client)
        services = DemoServices()
        result = Agent(model, services).run(Task('Dubai','2026-12-01','2026-12-02'))
        self.assertEqual(result['status'], 'booked')
        self.assertEqual(services.orders[0]['total_cents'],14000)
        request = client.chat.completions.create.call_args.kwargs
        self.assertFalse(request['parallel_tool_calls'])
        self.assertEqual(request['messages'][-1]['role'], 'tool')
        self.assertEqual(json.loads(request['messages'][-2]['tool_calls'][0]['function']['arguments']), {})
        self.assertEqual(request['tools'][0]['function']['name'],'search_hotels')
        self.assertEqual(len(model.responses),2)

    def test_invalid_json_is_failure(self):
        client=Mock(); client.chat.completions.create.return_value=response('book_hotel','oops')
        with self.assertRaises(ModelResponseError):
            ChatModel('test',client=client).complete([],TOOLS)

    def test_truncation_is_failure(self):
        client=Mock(); client.chat.completions.create.return_value=response(reason='length')
        with self.assertRaises(ModelResponseError):
            ChatModel('test',client=client).complete([],TOOLS)

    def test_api_errors_propagate(self):
        client=Mock(); client.chat.completions.create.side_effect=TimeoutError('timeout')
        with self.assertRaises(TimeoutError):
            ChatModel('test',client=client).complete([],TOOLS)

    def test_final_text_and_usage(self):
        client=Mock(); client.chat.completions.create.return_value=response()
        reply=ChatModel('test',client=client).complete([],TOOLS)
        self.assertEqual(reply.calls,())
        self.assertEqual(reply.usage['total_tokens'],42)

class ZhipuTests(unittest.TestCase):
    def test_classroom_request_parameters(self):
        client = Mock()
        client.chat.completions.create.return_value = response('search_hotels', '{}')
        model = ChatModel('glm-4-flash-250414', provider='zhipu', client=client)
        reply = model.complete([{'role':'user','content':'Find a hotel'}], TOOLS)
        request = client.chat.completions.create.call_args.kwargs
        self.assertEqual(request['max_tokens'],512)
        self.assertEqual(request['temperature'],0)
        self.assertFalse(request['stream'])
        self.assertNotIn('max_completion_tokens',request)
        self.assertNotIn('parallel_tool_calls',request)
        self.assertEqual(model.config['timeout'],45)
        self.assertEqual(model.config['base_url'],'https://open.bigmodel.cn/api/paas/v4/')
        self.assertEqual(reply.calls[0].name,'search_hotels')

class Flash47Tests(unittest.TestCase):
    def test_thinking_profile_and_history(self):
        client=Mock()
        r=response('search_hotels','{}')
        r.model_dump.return_value={'choices':[{'message':{'reasoning_content':'reasoning placeholder'}}]}
        client.chat.completions.create.return_value=r
        model=ChatModel('glm-4.7-flash',provider='zhipu',client=client)
        reply=model.complete([{'role':'assistant','content':'','reasoning_content':'previous'}],TOOLS)
        request=client.chat.completions.create.call_args.kwargs
        self.assertEqual(request['max_tokens'],8192)
        self.assertEqual(request['extra_body'],{'thinking':{'type':'enabled'}})
        self.assertEqual(request['messages'][0]['reasoning_content'],'previous')
        self.assertEqual(reply.reasoning_content,'reasoning placeholder')
        self.assertEqual(model.config['timeout'],60)

class DeepSeekTests(unittest.TestCase):
    def test_non_thinking_profile(self):
        client=Mock()
        client.chat.completions.create.return_value=response('search_hotels','{}')
        model=ChatModel('deepseek-flash',provider='deepseek',client=client)
        model.complete([],TOOLS)
        request=client.chat.completions.create.call_args.kwargs
        self.assertEqual(model.config['base_url'],'https://api.deepseek.com')
        self.assertEqual(request['model'],'deepseek-flash')
        self.assertEqual(request['max_tokens'],2048)
        self.assertEqual(request['extra_body'],{'thinking':{'type':'disabled'}})
        self.assertNotIn('max_completion_tokens',request)
        self.assertNotIn('parallel_tool_calls',request)

class ZhipuBusyRetryTests(unittest.TestCase):
    def test_busy_retries_are_bounded(self):
        class BusyError(Exception):
            status_code = 429
            code = '1305'
            request_id = 'test-request'

        from unittest.mock import patch
        client = Mock()
        client.chat.completions.create.side_effect = BusyError()
        model = ChatModel('glm-4.7-flash', provider='zhipu', client=client)
        with patch('travel_agent.model.time.sleep') as sleep:
            with self.assertRaises(BusyError):
                model.complete([], TOOLS)
        self.assertEqual(client.chat.completions.create.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [5, 15])
        self.assertEqual(len(model.retry_events), 2)
