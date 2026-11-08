"""Chat Completions adapter. Requires a model supporting function tools."""
import json
import time
from .agent import Call, Reply

class ModelResponseError(ValueError):
    pass

class ChatModel:
    def __init__(self, model, *, api_key=None, base_url=None, timeout=30,
                 max_completion_tokens=1024, client=None, provider="openai"):
        if provider not in ("openai", "zhipu", "deepseek"):
            raise ValueError("Unknown provider")
        if provider == "zhipu":
            base_url = base_url or "https://open.bigmodel.cn/api/paas/v4/"
            timeout = 45
            max_completion_tokens = 8192 if model == "glm-4.7-flash" else 512
            if model == "glm-4.7-flash":
                timeout = 60
        if provider == "deepseek":
            base_url = base_url or "https://api.deepseek.com"
            timeout = 60
            max_completion_tokens = 2048
        if not model:
            raise ValueError('A model identifier is required')
        if client is None:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=base_url,
                            timeout=timeout, max_retries=0)
        self.client = client
        self.config = {'model': model, 'base_url': base_url,
                       'timeout': timeout, 'max_completion_tokens': max_completion_tokens,
                       'max_retries': 0, 'provider': provider}
        if provider == 'deepseek':
            self.config.update(temperature=0, max_tokens=2048, thinking={'type':'disabled'})
            del self.config['max_completion_tokens']
        elif provider == 'zhipu':
            self.config.update(temperature=0, max_tokens=max_completion_tokens)
            if model == "glm-4.7-flash":
                self.config["thinking"] = {"type": "enabled"}
            del self.config['max_completion_tokens']
        else:
            self.config['parallel_tool_calls'] = False
        self.responses = []
        self.retry_events = []
        self.config['busy_retry_delays'] = [5, 15] if provider == 'zhipu' else []

    def complete(self, messages, tools):
        wire = []
        for message in messages:
            item = {'role': message['role'], 'content': message['content']}
            if message['role'] == 'tool':
                item['tool_call_id'] = message['tool_call_id']
            if message.get('reasoning_content'):
                item['reasoning_content'] = message['reasoning_content']
            if message.get('tool_calls'):
                item['tool_calls'] = [
                    {'id': c['id'], 'type': 'function', 'function': {
                        'name': c['name'], 'arguments': json.dumps(c['arguments'])}}
                    for c in message['tool_calls']]
            wire.append(item)
        options = ({"temperature": 0, "max_tokens": self.config["max_tokens"], "stream": False}
                   if self.config["provider"] in ("zhipu", "deepseek") else
                   {"parallel_tool_calls": False, "max_completion_tokens": self.config["max_completion_tokens"]})
        if "thinking" in self.config:
            options["extra_body"] = {"thinking": self.config["thinking"]}
        delays = iter(self.config['busy_retry_delays'])
        while True:
            try:
                response = self.client.chat.completions.create(
                    model=self.config['model'], messages=wire,
                    tools=[{'type': 'function', 'function': t} for t in tools],
                    tool_choice='auto', **options)
                break
            except Exception as exc:
                delay = next(delays, None)
                if (delay is None or getattr(exc, 'status_code', None) != 429
                        or str(getattr(exc, 'code', None)) != '1305'):
                    raise
                self.retry_events.append({
                    'code': '1305', 'delay_seconds': delay,
                    'request_id': getattr(exc, 'request_id', None),
                })
                print(f'智谱模型繁忙（1305），{delay} 秒后重试。', flush=True)
                time.sleep(delay)
        raw = response.model_dump(mode='json')
        self.responses.append(raw)
        if not response.choices:
            raise ModelResponseError('No model choice returned')
        choice = response.choices[0]
        if choice.finish_reason not in ('stop', 'tool_calls'):
            raise ModelResponseError('Incomplete model response: ' + str(choice.finish_reason))
        message = choice.message
        calls = []
        for call in message.tool_calls or []:
            try:
                args = json.loads(call.function.arguments)
            except json.JSONDecodeError as exc:
                raise ModelResponseError('Tool arguments are not valid JSON') from exc
            if not isinstance(args, dict):
                raise ModelResponseError('Tool arguments must be an object')
            calls.append(Call(call.id, call.function.name, args))
        if len(calls) > 1:
            raise ModelResponseError('Expected serial tool calls')
        if not calls and not message.content:
            raise ModelResponseError('Empty model reply')
        return Reply(message.content or '', tuple(calls),
                     response.usage.model_dump() if response.usage else {},
                     raw.get('choices', [{}])[0].get('message', {}).get('reasoning_content'))
