"""Service recovery checks without stopping real processes or touching real logs."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("local_services", Path(__file__).parents[1] / "local_services.py")
services = importlib.util.module_from_spec(spec)
spec.loader.exec_module(services)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.patches = [patch.object(services, "STATE", self.directory),
                        patch.object(services, "rotate_logs"), patch.object(services, "event")]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def test_only_three_consecutive_failures_restart_the_affected_service(self):
        with patch.object(services, "loaded", return_value=True), \
             patch.object(services, "healthy", side_effect=lambda url: ":3000/" not in url), \
             patch.object(services, "ctl", return_value=SimpleNamespace(returncode=0)) as command:
            services.watchdog()
            services.watchdog()
            command.assert_not_called()
            services.watchdog()
            command.assert_called_once_with("kickstart", "-k", services.target("frontend"), check=False)

    def test_success_resets_failures_instead_of_restarting_after_intermittent_errors(self):
        with patch.object(services, "loaded", side_effect=lambda name: name == "frontend"), \
             patch.object(services, "healthy", side_effect=[False, False, True, False]), \
             patch.object(services, "ctl") as command:
            for _ in range(4):
                services.watchdog()
            command.assert_not_called()
            self.assertEqual(services.read_json(self.directory / "health.json")["frontend"]["failures"], 1)

    def test_deliberately_unloaded_jobs_are_not_resurrected(self):
        services.write_json(self.directory / "health.json", {"frontend": {"failures": 9}})
        with patch.object(services, "loaded", return_value=False), \
             patch.object(services, "healthy") as probe, patch.object(services, "ctl") as command:
            services.watchdog()
            probe.assert_not_called()
            command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
