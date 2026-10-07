"""Tiny HTTP endpoint for Teams card buttons: GET /decide/<token> records the decision.

Run with `python -m wfmcp callback` (same WFMCP_* env as the server, same WFMCP_SECRET).
Links are signed and expire, which is enough for an MVP on an internal network. For a
production tenant replace OpenUrl links with a Teams bot and Action.Execute so the click
carries the clicker's identity.
"""
from __future__ import annotations

import html
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .engine import Engine, EngineError

PAGE = """<!doctype html><meta name=viewport content="width=device-width"><body style="font-family:system-ui;padding:2rem;max-width:40rem">
<h2>{title}</h2><p>{body}</p><p style="color:#666">You can close this tab.</p></body>"""


def make_handler(engine: Engine):
    class H(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            u = urlparse(self.path)
            if u.path == "/health":
                return self._send(200, "ok", "")
            if not u.path.startswith("/decide/"):
                return self._send(404, "Not found", "")
            token = u.path[len("/decide/"):]
            who = parse_qs(u.query).get("by", [""])[0]
            try:
                run_id, step_id, choice = engine.verify_token(token)
                engine.decide(run_id, step_id, choice, decided_by=who or "teams-link", comment="via card")
                return self._send(200, f"Recorded: {choice}", f"Step <b>{html.escape(step_id)}</b> of run <b>{html.escape(run_id)}</b>.")
            except EngineError as e:
                return self._send(409, "Not recorded", html.escape(str(e)))

        def _send(self, code: int, title: str, body: str):
            data = PAGE.format(title=html.escape(title), body=body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, fmt, *args):  # quieter
            pass

    return H


def serve(engine: Engine, host: str = "0.0.0.0", port: int | None = None) -> None:
    port = port or int(os.environ.get("WFMCP_CALLBACK_PORT", "8787"))
    srv = ThreadingHTTPServer((host, port), make_handler(engine))
    print(f"wfmcp callback listening on http://{host}:{port}")
    srv.serve_forever()
