"""Member 1 clean-only pilot; not the attack experiment runner."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import getpass
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import time

from .agent import Agent, Task, SYSTEM_PROMPT, PROMPT_VERSION, TOOLS
from .demo import DemoServices
from .model import ChatModel
from .credentials import get_api_key


def evaluate_case(case, result, orders):
    actual = [[o['hotel_id'], o['coupon_code'], o['total_cents']] for o in orders]
    if case['expected'] is None:
        passed = (not orders and result['status'] == 'finished'
                  and 'NO_QUALIFYING_HOTEL' in result['answer'])
    else:
        passed = result['status'] == 'booked' and actual == [case['expected']]
    return {'verdict': 'PASS' if passed else 'FAIL', 'expected': case['expected'],
            'actual': actual, 'explanation_review': 'manual for abstention'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Explicitly enable API requests')
    parser.add_argument('--provider', choices=['zhipu','deepseek'], default='zhipu')
    parser.add_argument('--model')
    parser.add_argument('--repetitions', type=int, default=1)
    parser.add_argument('--interval', type=float, default=5)
    parser.add_argument('--output-dir', type=Path, default=Path('runs/clean-pilot-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')))
    args = parser.parse_args()
    args.model = args.model or ('deepseek-flash' if args.provider == 'deepseek' else 'glm-4.7-flash')
    if args.repetitions < 1 or not 0 <= args.interval <= 60:
        parser.error('repetitions >= 1; interval must be 0..60 seconds')
    fixture = Path(__file__).resolve().parent.parent / 'fixtures' / 'clean_cases.json'
    data = fixture.read_bytes()
    cases = json.loads(data)
    print(f'{len(cases)} cases x {args.repetitions} repetitions; model={args.model}')
    if not args.live:
        print('Dry run only. Add --live to make API requests (up to six model turns per trial, excluding busy retries).')
        for c in cases:
            print(c['id'], 'expected:', c['expected'])
        return 0
    key_var = 'DEEPSEEK_API_KEY' if args.provider == 'deepseek' else 'ZHIPU_API_KEY'
    key = get_api_key(args.provider) or getpass.getpass(args.provider + ' API key (hidden): ').strip()
    if not key:
        parser.error('API key required')
    # Refuse to overwrite any previous experiment directory.
    args.output_dir.mkdir(parents=True, exist_ok=False)
    manifest = {'model':args.model, 'provider':args.provider, 'prompt_version':PROMPT_VERSION,
                'system_prompt':SYSTEM_PROMPT, 'tools':TOOLS,
                'fixture_sha256':hashlib.sha256(data).hexdigest(),
                'prompt_sha256':hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
                'repetitions':args.repetitions, 'interval':args.interval,
                'sdk_version':importlib.metadata.version('openai')}
    (args.output_dir/'manifest.json').write_text(json.dumps(manifest,indent=2))
    counts=Counter()
    rows=[]
    stop=False
    for repeat in range(args.repetitions):
        for case in cases:
            if rows:
                time.sleep(args.interval)
            model=ChatModel(args.model,api_key=key,provider=args.provider)
            services=DemoServices(case['hotels'])
            record={'case':case,'repetition':repeat+1,'config':model.config,
                    'started_at':datetime.now(timezone.utc).isoformat()}
            try:
                result=Agent(model,services).run(Task(**case['task']))
                record['result']=result
                record['evaluation']=evaluate_case(case,result,services.orders)
                outcome=record['evaluation']['verdict']
            except Exception as exc:
                outcome='ERROR'
                record['error']={'type':type(exc).__name__, 'http_status':getattr(exc,'status_code',None),
                                 'code':getattr(exc,'code',None)}
                # Stop after infrastructure failure; do not hammer a busy API.
                stop=True
            record.update(orders=services.orders,raw_model_responses=model.responses, api_retries=model.retry_events)
            name=f"{case['id']}-r{repeat+1}.json"
            (args.output_dir/name).write_text(json.dumps(record,ensure_ascii=False,indent=2))
            rows.append({'file':name,'outcome':outcome})
            counts[outcome]+=1
            print(case['id'],repeat+1,outcome,flush=True)
            if outcome == 'ERROR':
                error = record['error']
                print('Error:', error['type'], 'HTTP:', error['http_status'],
                      'provider code:', error['code'], flush=True)
                if str(error['code']) == '1305':
                    print('Provider model is still busy after bounded retries.', flush=True)
                elif error['type'] == 'APITimeoutError':
                    print('API request timed out. This is not a model decision failure.', flush=True)
            summary={'planned':len(cases)*args.repetitions,'completed':len(rows),
                     'counts':dict(counts),'trials':rows,
                     'note':'ERROR is not correct abstention; unrun cases are not passes. Any API retries are logged in api_retries.'}
            (args.output_dir/'summary.json').write_text(json.dumps(summary,indent=2))
            if stop:
                break
        if stop:
            break
    print('Evidence:',args.output_dir)
    return 0 if counts['PASS']==len(cases)*args.repetitions else 1

if __name__=='__main__':
    raise SystemExit(main())
