from __future__ import annotations

import base64
import hashlib
import secrets
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional, Tuple


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def make_pkce_pair() -> Tuple[str, str]:
    """Return (verifier, challenge)"""
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode("utf-8")).digest())
    return verifier, challenge


class _OneShotHandler(BaseHTTPRequestHandler):
    server_version = "ArchShowcaseCallback/0.1"
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        code = (qs.get("code") or [None])[0]
        state = (qs.get("state") or [None])[0]

        # Store on server object
        self.server.received = (code, state)  # type: ignore[attr-defined]

        body = b"You can close this tab and return to the desktop app."
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # Silence default logging
        return


class DesktopBrowserLogin:
    """Desktop browser login flow (PKCE + localhost callback)."""

    def __init__(self, api_base_url: str):
        self.api_base_url = api_base_url.rstrip("/")
        self.state = secrets.token_urlsafe(16)
        self.code_verifier, self.code_challenge = make_pkce_pair()
        self._httpd: Optional[HTTPServer] = None

    def start_callback_server(self) -> str:
        # Bind to an ephemeral port on localhost.
        self._httpd = HTTPServer(("127.0.0.1", 0), _OneShotHandler)
        self._httpd.received = (None, None)  # type: ignore[attr-defined]

        host, port = self._httpd.server_address
        redirect_uri = f"http://{host}:{port}/callback"

        t = threading.Thread(target=self._httpd.handle_request, daemon=True)
        t.start()
        return redirect_uri

    def open_browser(self, redirect_uri: str, prefill: bool = False) -> None:
        params = {
            "state": self.state,
            "redirect_uri": redirect_uri,
            "code_challenge": self.code_challenge,
            "prefill": "1" if prefill else "0",
        }
        url = f"{self.api_base_url}/desktop/login?{urllib.parse.urlencode(params)}"
        webbrowser.open(url)

    def wait_for_code(self, timeout_s: int = 120) -> Tuple[Optional[str], Optional[str]]:
        if not self._httpd:
            return None, None

        # Poll for received data (the handler sets it).
        import time
        end = time.time() + timeout_s
        while time.time() < end:
            code, state = getattr(self._httpd, "received", (None, None))  # type: ignore[attr-defined]
            if code and state:
                return code, state
            time.sleep(0.1)
        return None, None
