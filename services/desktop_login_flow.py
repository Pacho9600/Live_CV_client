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

    def _handle(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        code = (qs.get("code") or [None])[0]
        state = (qs.get("state") or [None])[0]
        cancel = (qs.get("cancel") or [None])[0]

        expected_state = getattr(self.server, "expected_state", None)  # type: ignore[attr-defined]

        if cancel and state and expected_state and state == expected_state:
            self.server.canceled = True  # type: ignore[attr-defined]
            body = b"Login canceled. You can close this tab and return to the desktop app."
        else:
            body = b"You can close this tab and return to the desktop app."

        # Store on server object (ignore unrelated requests like /favicon.ico).
        if code and state and expected_state and state == expected_state:
            self.server.received = (code, state)  # type: ignore[attr-defined]

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._handle()

    def do_POST(self):
        # Consume request body (sendBeacon may POST with a small body).
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except Exception:
            length = 0
        if length:
            try:
                self.rfile.read(length)
            except Exception:
                pass
        self._handle()

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
        self._thread: Optional[threading.Thread] = None
        self.was_canceled = False

    def start_callback_server(self) -> str:
        # Bind to an ephemeral port on localhost.
        self._httpd = HTTPServer(("127.0.0.1", 0), _OneShotHandler)
        self._httpd.received = (None, None)  # type: ignore[attr-defined]
        self._httpd.expected_state = self.state  # type: ignore[attr-defined]
        self._httpd.canceled = False  # type: ignore[attr-defined]

        host, port = self._httpd.server_address
        redirect_uri = f"http://{host}:{port}/callback"

        t = threading.Thread(target=self._httpd.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)
        t.start()
        self._thread = t
        return redirect_uri

    def stop_callback_server(self) -> None:
        httpd = self._httpd
        if not httpd:
            return
        try:
            httpd.shutdown()
        except Exception:
            pass
        try:
            httpd.server_close()
        except Exception:
            pass
        self._httpd = None
        self._thread = None

    def cancel(self) -> None:
        self.was_canceled = True
        # Do not block the UI thread; the background wait loop will shut down the server.

    def open_browser(self, redirect_uri: str, prefill: bool = False) -> bool:
        params = {
            "state": self.state,
            "redirect_uri": redirect_uri,
            "code_challenge": self.code_challenge,
            "prefill": "1" if prefill else "0",
        }
        url = f"{self.api_base_url}/desktop/login?{urllib.parse.urlencode(params)}"
        return webbrowser.open(url)

    def wait_for_code(self, timeout_s: int = 120) -> Tuple[Optional[str], Optional[str]]:
        httpd = self._httpd
        if not httpd:
            return None, None

        # Poll for received data (the handler sets it).
        import time
        end = time.time() + timeout_s
        while time.time() < end:
            if self.was_canceled:
                self.stop_callback_server()
                return None, None

            if getattr(httpd, "canceled", False):  # type: ignore[attr-defined]
                self.was_canceled = True
                self.stop_callback_server()
                return None, None

            code, state = getattr(httpd, "received", (None, None))  # type: ignore[attr-defined]
            if code and state:
                self.stop_callback_server()
                return code, state
            time.sleep(0.1)

        self.stop_callback_server()
        return None, None
