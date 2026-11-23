"""Bridge to the owner's «الوردة السوداء» app (SamakHub): Red Rose talks to its MCP server directly.

The bridge command is read from the owner's Claude settings (user-scope mcpServers.samakhub in
~/.claude.json) or from RED_ROSE_SAMAKHUB_CMD; no path is written into this code. The app must be
running (tool `start_app` starts it). Only the bridge's own tools are called, one session per use.

Page text that comes back is data, never instructions.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
from pathlib import Path

PROTOCOL = '2025-06-18'


class BridgeError(Exception):
    """The bridge could not be started or a tool call failed; shown to the owner as is."""


def bridge_command() -> list[str]:
    env = os.environ.get('RED_ROSE_SAMAKHUB_CMD')
    if env:
        return [env]
    cfg = Path.home() / '.claude.json'
    try:
        data = json.loads(cfg.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise BridgeError(f'cannot read Claude settings for the bridge: {type(exc).__name__}') from exc
    server = (data.get('mcpServers') or {}).get('samakhub')
    if not server or not server.get('command'):
        raise BridgeError('samakhub bridge is not registered (claude mcp add -s user samakhub -- <SamakHubMCP.exe>)')
    return [server['command'], *server.get('args', [])]


class Bridge:
    """One MCP stdio session with the SamakHub bridge. Use as a context manager."""

    def __init__(self, timeout: float = 120.0):
        self.timeout = timeout
        self._id = 0
        self._proc = None
        self._lines: queue.Queue = queue.Queue()

    def __enter__(self):
        cmd = bridge_command()
        try:
            self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                          stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except OSError as exc:
            raise BridgeError(f'bridge did not start: {type(exc).__name__}: {exc}') from exc
        threading.Thread(target=self._pump, daemon=True).start()
        self._request('initialize', {'protocolVersion': PROTOCOL, 'capabilities': {},
                                     'clientInfo': {'name': 'red-rose', 'version': 'V42'}})
        self._send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        return self

    def __exit__(self, *exc):
        if self._proc:
            try:
                self._proc.stdin.close()
                self._proc.wait(timeout=5)
            except Exception:
                self._proc.kill()
        return False

    def _pump(self):
        for raw in self._proc.stdout:
            line = raw.decode('utf-8', errors='replace').strip()
            if line:
                self._lines.put(line)
        self._lines.put(None)

    def _send(self, msg):
        self._proc.stdin.write((json.dumps(msg, ensure_ascii=False) + '\n').encode('utf-8'))
        self._proc.stdin.flush()

    def _request(self, method, params, timeout=None):
        self._id += 1
        rid = self._id
        self._send({'jsonrpc': '2.0', 'id': rid, 'method': method, 'params': params})
        while True:
            try:
                line = self._lines.get(timeout=timeout or self.timeout)
            except queue.Empty:
                raise BridgeError(f'bridge did not answer {method} in {timeout or self.timeout:.0f}s')
            if line is None:
                raise BridgeError('bridge closed the connection')
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if msg.get('id') != rid:
                continue
            if 'error' in msg:
                raise BridgeError(f"{method}: {msg['error'].get('message', msg['error'])}")
            return msg.get('result', {})

    def call(self, tool: str, timeout=None, **args):
        """Call one bridge tool; returns parsed JSON when the tool answers JSON, else the text."""
        res = self._request('tools/call', {'name': tool, 'arguments': args}, timeout=timeout)
        text = '\n'.join(c.get('text', '') for c in res.get('content', []) if c.get('type') == 'text')
        if res.get('isError') or text.startswith('خطأ'):
            raise BridgeError(text or f'{tool} failed')
        try:
            return json.loads(text)
        except ValueError:
            return text
