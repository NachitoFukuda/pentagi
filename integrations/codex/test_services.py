import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('services', Path(__file__).with_name('services.py'))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


class ServicesTests(unittest.TestCase):
    def test_services_use_distinct_vm_port_and_keep_secrets_out_of_launchd(self):
        with patch.dict(s.os.environ, {'OPENAI_API_KEY': 'secret', 'CODEX_API_KEY': 'secret'}):
            jobs = s.job_definitions('test-model', '/Applications/Official/codex')
        self.assertEqual(jobs['bridge']['ProgramArguments'][-2:], ['--codex', '/Applications/Official/codex'])
        self.assertIn('127.0.0.1:18766:127.0.0.1:18765', jobs['tunnel']['ProgramArguments'])
        for job in jobs.values():
            self.assertNotIn('OPENAI_API_KEY', job['EnvironmentVariables'])
            self.assertNotIn('CODEX_API_KEY', job['EnvironmentVariables'])
            self.assertNotIn('secret', str(job))
            self.assertTrue(job['KeepAlive'])

    def test_bridge_must_be_ready_before_reverse_tunnel_is_started(self):
        events = []
        with tempfile.TemporaryDirectory() as root, patch.object(s, 'STATE', Path(root)), \
                patch.object(s, 'load_job', side_effect=lambda name, *_: events.append(name)), \
                patch.object(s, 'wait_bridge', side_effect=lambda: events.append('ready')):
            s.start('test-model', '/Applications/Official/codex')
        self.assertEqual(events, ['bridge', 'ready', 'tunnel'])

    def test_stale_pid_cannot_kill_an_unrelated_process(self):
        with tempfile.TemporaryDirectory() as root, patch.object(s, 'STATE', Path(root)):
            (Path(root) / 'bridge.pid').write_text('1234')
            with patch.object(s.subprocess, 'run') as run, patch.object(s.os, 'kill') as kill:
                run.return_value.returncode = 0
                run.return_value.stdout = '/usr/bin/unrelated'
                with self.assertRaisesRegex(SystemExit, 'unrelated'):
                    s.stop_legacy('bridge')
                kill.assert_not_called()


if __name__ == '__main__': unittest.main()
