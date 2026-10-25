import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import subprocess
import urllib.error
import urllib.request

spec = importlib.util.spec_from_file_location('bridge', Path(__file__).with_name('bridge.py'))
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        def runner(body):
            self.calls.append(body)
            return b.validate_answer({'content': 'ok', 'tool_calls': []}, body), {}
        self.server = b.BridgeServer(('127.0.0.1', 0), 'x' * 48, runner)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, body=None, token='x' * 48, path='/v1/chat/completions'):
        return urllib.request.urlopen(urllib.request.Request(self.base + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}), timeout=5)

    def test_auth_blocks_execution(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request({'model': b.MODEL_ALIAS, 'messages': [{'role': 'user', 'content': 'hi'}]}, token='wrong')
        self.assertEqual(error.exception.code, 401)
        self.assertEqual(self.calls, [])

    def test_completion_and_buffered_sse(self):
        body = {'model': b.MODEL_ALIAS, 'messages': [{'role': 'user', 'content': 'hello'}]}
        with self.request(body) as response:
            self.assertEqual(json.load(response)['choices'][0]['message']['content'], 'ok')
        with self.request(dict(body, stream=True)) as response:
            self.assertIn(b'data: [DONE]', response.read())

    def test_busy_fails_without_spawning(self):
        self.server.slot.acquire()
        try:
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.request({'model': b.MODEL_ALIAS, 'messages': [{'role': 'user', 'content': 'hi'}]})
            self.assertEqual(error.exception.code, 429)
            self.assertEqual(self.calls, [])
        finally:
            self.server.slot.release()

    def test_function_call_round_trip_and_boundaries(self):
        body = {'tools': [{'type': 'function', 'function': {'name': 'terminal'}}], 'tool_choice': 'required'}
        answer = {'content': '', 'tool_calls': [{'name': 'terminal', 'arguments': '{"command":"printf TEST"}'}]}
        message = b.validate_answer(answer, body)
        self.assertEqual(json.loads(message['tool_calls'][0]['function']['arguments'])['command'], 'printf TEST')
        self.assertRegex(message['tool_calls'][0]['id'], r'^call_[0-9a-f]{24}$')
        for changed in [dict(answer, tool_calls=[{'name': 'unoffered', 'arguments': '{}'}]),
                        dict(answer, tool_calls=[{'name': 'terminal', 'arguments': 'invalid'}])]:
            with self.assertRaises(b.BridgeError): b.validate_answer(changed, body)
        with self.assertRaises(b.BridgeError): b.validate_answer(answer, dict(body, tool_choice='none'))
        with self.assertRaises(b.BridgeError): b.validate_answer({'content': 'x', 'tool_calls': []}, body)

    def test_multimodal_and_model_override_rejected(self):
        for body in [{'model': 'other', 'messages': [{'role': 'user', 'content': 'hi'}]},
                     {'model': b.MODEL_ALIAS, 'messages': [{'role': 'user', 'content': [{'type': 'image_url'}]}]}]:
            with self.assertRaises(b.BridgeError): b.validate_request(body)

    def test_runner_uses_cli_without_user_config_and_native_shell(self):
        runner = b.CodexRunner('/usr/local/bin/codex', 'test-model')
        command = runner.command(Path('/tmp/empty'), Path('/tmp/schema'), Path('/tmp/output'))
        self.assertIn('--ignore-user-config', command)
        self.assertIn('--ignore-rules', command)
        self.assertIn('read-only', command)
        self.assertIn('shell_tool', command)
        self.assertIn('web_search="disabled"', command)
        self.assertIn('forced_login_method="chatgpt"', command)
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox', command)

    def test_api_key_login_is_rejected_before_inference(self):
        runner = b.CodexRunner('/usr/local/bin/codex', 'test-model')
        body = {'model': b.MODEL_ALIAS, 'messages': [{'role': 'user', 'content': 'hello'}]}
        for status in ['Logged in using an API key', 'Not logged in']:
            with patch.object(b.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, status, '')), \
                    patch.object(b.subprocess, 'Popen') as spawn:
                with self.assertRaisesRegex(b.BridgeError, 'ChatGPT'):
                    runner(body)
                spawn.assert_not_called()

    def test_cli_auth_check_uses_cli_without_copying_credentials(self):
        runner = b.CodexRunner('/usr/local/bin/codex', 'test-model')
        with patch.object(b.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', 'Logged in using ChatGPT')) as call:
            runner.require_chatgpt_login()
            self.assertEqual(call.call_args.args[0], ['/usr/local/bin/codex', 'login', 'status'])

    def test_api_credentials_and_wif_are_not_inherited(self):
        with patch.dict(b.os.environ, {'OPENAI_API_KEY': 'private', 'CODEX_API_KEY': 'private',
                'ACCESS_TOKEN': 'private', 'CODEX_ACCESS_TOKEN': 'private',
                'OPENAI_IDENTITY_TOKEN_FILE': '/private/token'}):
            env = b.CodexRunner.environment()
            self.assertNotIn('OPENAI_API_KEY', env)
            self.assertNotIn('CODEX_API_KEY', env)
            self.assertNotIn('ACCESS_TOKEN', env)
            self.assertNotIn('CODEX_ACCESS_TOKEN', env)
            self.assertNotIn('OPENAI_IDENTITY_TOKEN_FILE', env)

    def test_bind_cannot_be_public(self):
        with self.assertRaises(ValueError): b.BridgeServer(('0.0.0.0', 0), 'x'*48, None)


if __name__ == '__main__': unittest.main()
