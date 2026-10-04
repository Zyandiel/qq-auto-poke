from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from instance import single_instance


class InstanceTests(unittest.TestCase):
    def run_child(self, path):
        script = "from instance import single_instance; import sys\nwith single_instance(sys.argv[1]): print('locked')"
        return subprocess.run([sys.executable, "-c", script, str(path)], cwd=Path(__file__).parents[1],
                              capture_output=True, text=True, timeout=5)

    def test_other_process_is_denied_and_lock_is_released(self):
        with TemporaryDirectory() as directory:
            config = Path(directory) / "config.yaml"
            with single_instance(config):
                denied = self.run_child(config)
                self.assertNotEqual(denied.returncode, 0)
                self.assertIn("AlreadyRunningError", denied.stderr)
            accepted = self.run_child(config)
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            self.assertEqual(accepted.stdout.strip(), "locked")

    def test_different_configs_are_independent(self):
        with TemporaryDirectory() as directory:
            with single_instance(Path(directory) / "first.yaml"):
                accepted = self.run_child(Path(directory) / "second.yaml")
                self.assertEqual(accepted.returncode, 0, accepted.stderr)
