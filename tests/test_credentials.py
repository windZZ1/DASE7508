import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from travel_agent.credentials import get_api_key

class CredentialTests(unittest.TestCase):
    def test_local_provider_and_environment_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'config.local.json'
            p.write_text(json.dumps({'deepseek':{'api_key':'test-local-key'}}))
            with patch('travel_agent.credentials.CONFIG_PATH',p), patch.dict('os.environ',{},clear=True):
                self.assertEqual(get_api_key('deepseek'),'test-local-key')
                self.assertEqual(get_api_key('zhipu'),'')
                with patch.dict('os.environ',{'DEEPSEEK_API_KEY':'test-env-key'}):
                    self.assertEqual(get_api_key('deepseek'),'test-env-key')
