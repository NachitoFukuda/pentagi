#!/usr/bin/env python3
"""Loopback-only Chat Completions adapter for the user's authenticated Codex CLI.

No OpenAI credential is read here or passed to PentAGI. Function calls are returned
as data; PentAGI executes them in its worker VM. No third-party Python dependencies.
"""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_BODY = 2 * 1024 * 1024
MAX_OUTPUT = 8 * 1024 * 1024
MODEL_ALIAS = 'codex-local'


class BridgeError(Exception):
    pass


def envelope_schema():
    return {'type': 'object', 'additionalProperties': False,
            'properties': {'content': {'type': 'string'}, 'tool_calls': {
                'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
                    'properties': {'name': {'type': 'string'}, 'arguments': {'type': 'string'}},
                    'required': ['name', 'arguments']}}}, 'required': ['content', 'tool_calls']}


def validate_request(body):
    if not isinstance(body, dict) or body.get('model') != MODEL_ALIAS:
        raise BridgeError('model must be codex-local')
    if not isinstance(body.get('messages'), list) or not body['messages']:
        raise BridgeError('messages must be a nonempty array')
    for message in body['messages']:
        if not isinstance(message, dict) or message.get('role') not in (
                'system', 'developer', 'user', 'assistant', 'tool', 'function'):
            raise BridgeError('unsupported message role')
        # Explicitly reject multimodal input instead of silently dropping evidence.
        content = message.get('content')
        if content is not None and not isinstance(content, str):
            if not isinstance(content, list) or any(
                    not isinstance(p, dict) or p.get('type') != 'text' for p in content):
                raise BridgeError('only text messages are supported')
    tools = body.get('tools') or []
    if not isinstance(tools, list) or any(not isinstance(t, dict) or
            t.get('type') != 'function' or not isinstance(t.get('function'), dict) or
            not isinstance(t['function'].get('name'), str) for t in tools):
        raise BridgeError('only named function tools are supported')
    return body


def validate_answer(answer, body):
    if not isinstance(answer, dict) or not isinstance(answer.get('content'), str) or not isinstance(answer.get('tool_calls'), list):
        raise BridgeError('invalid CLI response shape')
    offered = {t['function']['name']: t['function'] for t in body.get('tools') or []}
    choice = body.get('tool_choice', 'auto')
    calls = []
    for call in answer['tool_calls']:
        if not isinstance(call, dict) or call.get('name') not in offered:
            raise BridgeError('CLI returned an unoffered tool')
        if choice == 'none':
            raise BridgeError('tool_choice forbids tool calls')
        if isinstance(choice, dict) and call['name'] != choice.get('function', {}).get('name'):
            raise BridgeError('CLI returned the wrong forced tool')
        if not isinstance(call.get('arguments'), str):
            raise BridgeError('tool arguments must be a JSON string')
        try:
            arguments = json.loads(call['arguments'])
        except ValueError:
            raise BridgeError('tool arguments are invalid JSON') from None
        if not isinstance(arguments, dict):
            raise BridgeError('tool arguments must be an object')
        # Full tool-schema validation also takes place in PentAGI's tool dispatcher.
        calls.append({'id': 'call_' + secrets.token_hex(12), 'type': 'function',
                      'function': {'name': call['name'], 'arguments': call['arguments']}})
    if (choice == 'required' or isinstance(choice, dict)) and not calls:
        raise BridgeError('a tool call was required')
    if body.get('parallel_tool_calls') is False and len(calls) > 1:
        raise BridgeError('parallel tool calls are disabled')
    if not calls and body.get('response_format', {}).get('type') == 'json_object':
        try:
            json.loads(answer['content'])
        except ValueError:
            raise BridgeError('JSON response mode returned invalid JSON') from None
    return {'role': 'assistant', 'content': answer['content'] or None,
            **({'tool_calls': calls} if calls else {})}


class CodexRunner:
    def __init__(self, executable, model, timeout=600):
        self.executable, self.model, self.timeout = executable, model, timeout

    def command(self, directory, schema, output):
        command = [self.executable, 'exec', '--ignore-user-config', '--ignore-rules',
                   '--ephemeral', '--skip-git-repo-check', '--sandbox', 'read-only',
                   '--json', '--color', 'never', '--cd', str(directory),
                   '--output-schema', str(schema), '--output-last-message', str(output)]
        for feature in ('shell_tool', 'unified_exec', 'apps', 'hooks', 'memories',
                        'multi_agent', 'multi_agent_v2', 'computer_use', 'browser_use',
                        'in_app_browser', 'artifact', 'chronicle', 'code_mode_host'):
            command += ['--disable', feature]
        for setting in ('web_search="disabled"', 'project_doc_max_bytes=0',
                        'plugins._default.enabled=false', 'analytics.enabled=false',
                        'history.persistence="none"', 'otel.exporter="none"',
                        'otel.metrics_exporter="none"', 'model_reasoning_effort="low"'):
            command += ['-c', setting]
        if self.model:
            command += ['--model', self.model]
        return command + ['-']

    def __call__(self, body):
        validate_request(body)
        # Fresh empty working directory: no target-controlled AGENTS.md or project config.
        with tempfile.TemporaryDirectory(prefix='pentagi-codex-') as raw:
            directory = Path(raw)
            schema, output = directory / 'schema.json', directory / 'answer.json'
            schema.write_text(json.dumps(envelope_schema()))
            prompt = ('Act as a stateless language-model backend for PentAGI. Do not use any native '
                      'Codex tools, read files, browse, or execute commands. The following JSON is a '
                      'conversation and function-tool contract. Follow its system messages to produce '
                      'the next assistant response. Return requested function invocations as tool_calls '
                      'DATA in the output envelope; do not execute them. Respect tool_choice and '
                      'parallel_tool_calls. arguments must be a JSON-encoded object string. If no '
                      'function is needed, return tool_calls=[] and the assistant text in content. '
                      'For response_format=json_object, content must itself be valid JSON.\n'
                      + json.dumps(body, ensure_ascii=False))
            # No API keys, cloud keys, proxy settings, or application secrets inherited.
            allowed = ('HOME', 'PATH', 'TMPDIR', 'LANG', 'LC_ALL', 'CODEX_HOME',
                       'USER', 'LOGNAME', 'SSL_CERT_FILE', 'SSL_CERT_DIR')
            env = {k: os.environ[k] for k in allowed if k in os.environ}
            command = self.command(directory, schema, output)
            with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
                process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stdout,
                                           stderr=stderr, env=env, start_new_session=True)
                try:
                    process.communicate(prompt.encode(), timeout=self.timeout)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    raise BridgeError('Codex CLI timed out') from None
                if process.returncode:
                    # stderr can contain target data; never echo it into HTTP responses/logs.
                    raise BridgeError('Codex CLI failed; check CLI login and model access')
                if stdout.tell() > MAX_OUTPUT or not output.exists() or output.stat().st_size > MAX_OUTPUT:
                    raise BridgeError('Codex CLI output missing or too large')
                stdout.seek(0)
                usage = {}
                for line in stdout:
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if event.get('type') in ('item.started', 'item.completed'):
                        kind = event.get('item', {}).get('type')
                        if kind == 'error' and event['item'].get('message', '').startswith(
                                'Code Mode is unavailable because code-mode host is disabled.'):
                            continue  # Expected fail-closed startup notice; no tool was executed.
                        if kind not in ('agent_message', 'reasoning', None):
                            raise BridgeError('unexpected native Codex tool activity: ' + str(kind))
                    if event.get('type') == 'turn.completed':
                        usage = event.get('usage', {})
                try:
                    message = validate_answer(json.loads(output.read_text()), body)
                except ValueError:
                    raise BridgeError('Codex CLI returned invalid JSON') from None
                return message, {'prompt_tokens': usage.get('input_tokens', 0),
                                 'completion_tokens': usage.get('output_tokens', 0),
                                 'total_tokens': usage.get('input_tokens', 0) + usage.get('output_tokens', 0)}


class BridgeServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, token, runner):
        if address[0] != '127.0.0.1':
            raise ValueError('bridge may only bind to IPv4 loopback')
        self.token, self.runner = token, runner
        self.slot = threading.BoundedSemaphore(1)
        self.calls, self.failures = 0, 0
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *_):
        pass  # Never record prompts, credentials, or URL query strings.

    def send_json(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        value = self.headers.get('Authorization', '')
        if not hmac.compare_digest(value.encode(), ('Bearer ' + self.server.token).encode()):
            self.send_json(401, {'error': {'message': 'Unauthorized'}})
            self.close_connection = True
            return False
        return True

    def do_GET(self):
        if not self.authorized():
            return
        if self.path == '/health':
            self.send_json(200, {'status': 'ok', 'calls': self.server.calls,
                                 'failures': self.server.failures})
        elif self.path == '/v1/models':
            self.send_json(200, {'object': 'list', 'data': [
                {'id': MODEL_ALIAS, 'object': 'model', 'owned_by': 'local-codex'}]})
        else:
            self.send_json(404, {'error': {'message': 'Not found'}})

    def do_POST(self):
        if not self.authorized():
            return
        if self.path != '/v1/chat/completions':
            self.close_connection = True
            return self.send_json(404, {'error': {'message': 'Not found'}})
        try:
            if self.headers.get('Transfer-Encoding'):
                raise BridgeError('chunked request bodies are not supported')
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_BODY:
                raise BridgeError('request size must be between 1 byte and 2 MiB')
            self.connection.settimeout(15)
            body = validate_request(json.loads(self.rfile.read(length)))
        except (ValueError, OSError, BridgeError):
            self.close_connection = True
            return self.send_json(400, {'error': {'message': 'Invalid or unsupported request'}})
        if not self.server.slot.acquire(blocking=False):
            return self.send_json(429, {'error': {'message': 'Codex CLI is busy'}})
        try:
            self.server.calls += 1
            message, usage = self.server.runner(body)
            result = {'id': 'chatcmpl-' + secrets.token_hex(12), 'object': 'chat.completion',
                      'created': int(time.time()), 'model': MODEL_ALIAS, 'usage': usage,
                      'choices': [{'index': 0, 'message': message,
                                   'finish_reason': 'tool_calls' if message.get('tool_calls') else 'stop'}]}
            if not body.get('stream'):
                return self.send_json(200, result)
            # Buffered SSE: preserves the OpenAI streaming wire format, not token latency.
            chunk = dict(result, object='chat.completion.chunk')
            delta = dict(message)
            if delta.get('tool_calls'):
                delta['tool_calls'] = [dict(c, index=i) for i, c in enumerate(delta['tool_calls'])]
            chunk['choices'] = [{'index': 0, 'delta': delta, 'finish_reason': None}]
            end = dict(chunk, choices=[{'index': 0, 'delta': {},
                                       'finish_reason': result['choices'][0]['finish_reason']}])
            data = ('data: ' + json.dumps(chunk) + '\n\ndata: ' + json.dumps(end) + '\n\ndata: [DONE]\n\n').encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)
        except BridgeError as error:
            self.server.failures += 1
            self.send_json(502, {'error': {'message': str(error)}})
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            self.server.slot.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=18765)
    parser.add_argument('--token-file', type=Path, required=True)
    parser.add_argument('--model', required=True, help='Model available to your Codex login')
    parser.add_argument('--codex', default=shutil.which('codex'))
    args = parser.parse_args()
    if not args.codex or not Path(args.codex).is_absolute():
        parser.error('Codex CLI must resolve to an absolute executable path')
    if args.token_file.stat().st_mode & 0o077:
        parser.error('token file must be private (chmod 600)')
    token = args.token_file.read_text().strip()
    if len(token) < 32:
        parser.error('token must contain at least 32 characters')
    server = BridgeServer(('127.0.0.1', args.port), token, CodexRunner(args.codex, args.model))
    print('Codex bridge listening on loopback port ' + str(args.port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
