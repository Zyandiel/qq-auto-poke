from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from config import load_config


class ConfigTests(unittest.TestCase):
    def load(self, content):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(content, encoding="utf-8")
            return load_config(path)

    def test_valid(self):
        self.assertEqual(self.load('self_id: "123456"').self_id, 123456)

    def test_bad_config(self):
        for content in ['[]', 'cooldown_seconds: 0', 'cooldown_seconds: .nan',
                        'enable_logs: "false"', 'api_timeout_seconds: true',
                        'ws_url: http://localhost', 'ws_url: ws://localhost/api/',
                        'access_token: CHANGE_ME', 'self_id: false', 'typo: 1',
                        'ws_url: ws://localhost/?access_token=secret',
                        'access_token: "中文"', 'ws_url: ws://localhost:not-a-port',
                        'self_id: "' + '9'*5000 + '"', 'cooldown_seconds: ' + '9'*400]:
            with self.subTest(content=content), self.assertRaises(ValueError):
                self.load(content)
