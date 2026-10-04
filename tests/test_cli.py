import logging
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from main import RedactToken


class CLITests(unittest.TestCase):
    def invoke(self, config):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(config, encoding="utf-8")
            return subprocess.run([sys.executable, str(Path(__file__).parents[1] / "main.py"),
                                   "--config", str(path), "--check-config"],
                                  capture_output=True, text=True, encoding="utf-8", timeout=5,
                                  env=os.environ | {"PYTHONUTF8": "1"})

    def test_error_explains_field_without_exposing_token(self):
        result = self.invoke('access_token: very-private-test-token\ncooldown_seconds: 0')
        self.assertEqual(result.returncode, 2)
        self.assertIn("cooldown_seconds", result.stderr)
        self.assertNotIn("very-private-test-token", result.stderr)

    def test_yaml_error_does_not_print_raw_content(self):
        result = self.invoke('access_token: [very-private-test-token')
        self.assertEqual(result.returncode, 2)
        self.assertIn("YAML", result.stderr)
        self.assertNotIn("very-private-test-token", result.stderr)

    def test_check_config_does_not_connect(self):
        result = self.invoke('access_token: local-test')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_extreme_yaml_number_is_rejected_without_traceback(self):
        result = self.invoke('access_token: very-private-test-token\nself_id: ' + '9' * 5000)
        self.assertEqual(result.returncode, 2)
        self.assertIn('YAML', result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertNotIn('very-private-test-token', result.stderr)

    def test_logs_redact_formatted_token(self):
        record = logging.LogRecord("auto_poke", logging.ERROR, "", 0, "error: %s",
                                   ("local-private-token",), None)
        RedactToken("local-private-token").filter(record)
        self.assertEqual(record.getMessage(), "error: [REDACTED]")
