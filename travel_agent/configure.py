"""Save a provider key once on this computer."""
import argparse
import getpass
import json
import os
from .credentials import CONFIG_PATH

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider',choices=['deepseek','zhipu','openai'],default='deepseek')
    args=parser.parse_args(argv)
    key=getpass.getpass(args.provider + ' API key (hidden): ').strip()
    if not key:
        parser.error('No key entered; configuration unchanged')
    data=json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
    data[args.provider]={'api_key':key}
    fd=os.open(str(CONFIG_PATH),os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as f:
        if os.name == 'posix':
            os.fchmod(f.fileno(), 0o600)
        json.dump(data,f,indent=2)
        f.write('\n')
    print('Saved local configuration. Future runs read the key automatically.')

if __name__=='__main__':
    main()
