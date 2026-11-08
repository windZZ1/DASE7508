"""Run one simulated booking with Zhipu from the VS Code play button."""
from datetime import datetime, timezone
from pathlib import Path

from travel_agent import configure
from travel_agent.__main__ import main as run_demo
from travel_agent.credentials import get_api_key


def main():
    if not get_api_key('zhipu', prefer_local=True):
        configure.main(['--provider', 'zhipu'])
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = Path(__file__).resolve().parent / 'runs' / f'zhipu-vscode-{timestamp}.json'
    return run_demo(['--provider', 'zhipu', '--model', 'glm-4.7-flash',
                     '--base-url', 'https://open.bigmodel.cn/api/paas/v4/',
                     '--output', str(output)], prefer_local_key=True)


if __name__ == '__main__':
    raise SystemExit(main())
