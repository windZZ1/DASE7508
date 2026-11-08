import argparse
import getpass
from dataclasses import asdict
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import sys

from .agent import Agent, Task
from .demo import DemoServices, evaluate_demo
from .model import ChatModel
from .credentials import get_api_key

def main(argv=None, *, prefer_local_key=False):
    parser = argparse.ArgumentParser(description='Run a real model against local demo hotels.')
    parser.add_argument('--provider', choices=['openai', 'zhipu', 'deepseek'], default='zhipu')
    parser.add_argument('--model', default=os.getenv('HOTEL_MODEL'))
    parser.add_argument('--base-url', default=os.getenv('HOTEL_BASE_URL'))
    parser.add_argument('--budget-cents', type=int, default=15000)
    parser.add_argument('--output', type=Path, default=Path('runs/demo.json'))
    args = parser.parse_args(argv)
    if not args.model:
        if args.provider == 'deepseek':
            args.model = 'deepseek-flash'
        elif args.provider == 'zhipu':
            args.model = 'glm-4-flash-250414'
        else:
            parser.error('Set HOTEL_MODEL or pass --model')
    key_var = {'zhipu':'ZHIPU_API_KEY','deepseek':'DEEPSEEK_API_KEY','openai':'OPENAI_API_KEY'}[args.provider]
    key = get_api_key(args.provider, prefer_local=prefer_local_key)
    if not key and sys.stdin.isatty():
        key = getpass.getpass('API key (hidden): ').strip()
    if not key:
        parser.error('Set ' + key_var + ' or HOTEL_API_KEY locally')
    task = Task('Dubai', '2026-12-01', '2026-12-02', args.budget_cents)
    services = DemoServices()
    model = ChatModel(args.model, api_key=key, base_url=args.base_url, provider=args.provider)
    record = {'started_at': datetime.now(timezone.utc).isoformat(),
              'config': model.config, 'task': asdict(task),
              'sdk_version': importlib.metadata.version('openai'), 'fixture': 'demo-v1'}
    exit_code = 0
    try:
        record['result'] = Agent(model, services).run(task)
        record['evaluation'] = evaluate_demo(task, services.orders, record['result'])
        if record['evaluation']['verdict'] != 'PASS':
            exit_code = 2
    except Exception as exc:
        # Persist failure evidence and exit nonzero; never report it as abstention.
        record['error'] = {'type': type(exc).__name__,
                           'http_status': getattr(exc, 'status_code', None),
                           'code': getattr(exc, 'code', None),
                           'request_id': getattr(exc, 'request_id', None)}
        exit_code = 1
    record['raw_model_responses'] = model.responses
    record['api_retries'] = model.retry_events
    record['orders'] = services.orders
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Saved run:', args.output)
    if exit_code == 1:
        print('Run failed:', record['error']['type'], file=sys.stderr)
        if record['error']['type'] == 'RateLimitError':
            print('API rate/quota limit: see the provider error code and retry records in the log.', file=sys.stderr)
    else:
        print('Clean demo evaluation:', record['evaluation']['verdict'])
        print(record['result']['status'], record['result']['answer'])
    return exit_code

if __name__ == '__main__':
    sys.exit(main())
