"""Local credentials are never included in experiment records."""
import json
import os
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / 'config.local.json'
KEY_VARIABLES = {'deepseek':'DEEPSEEK_API_KEY', 'zhipu':'ZHIPU_API_KEY', 'openai':'OPENAI_API_KEY'}

def get_api_key(provider, *, prefer_local=False):
    key = os.getenv(KEY_VARIABLES[provider])
    if key and not prefer_local:
        return key.strip()
    if CONFIG_PATH.exists():
        data = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
        local_key = data.get(provider, {}).get('api_key', '')
        if not isinstance(local_key, str):
            raise ValueError('Local API key must be a string')
        if local_key.strip():
            return local_key.strip()
    return (key or '').strip()
