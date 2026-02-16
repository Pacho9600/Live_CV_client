from __future__ import annotations

import webbrowser

from PyQt5 import QtCore, QtWidgets

from config import API_BASE_URL
from services.api_client import ApiClient
from services.desktop_login_flow import DesktopBrowserLogin


class LoginWindow(QtWidgets.QMainWindow):
    logged_in = QtCore.pyqtSignal(str)  # access token

    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._flow: DesktopBrowserLogin | None = None
        self._attempt_counter = 0
        self._current_attempt_id = 0
        self.setWindowTitle("Architecture Showcase — Desktop Login")
        self.setMinimumSize(560, 320)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QtWidgets.QLabel("Login (in Browser)")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        layout.addWidget(title)

        explain = QtWidgets.QLabel(
            "This desktop app uses a browser-based login flow (PKCE + localhost callback).\n"
            "It demonstrates a safer desktop authentication pattern than embedding password entry in the client."
        )
        explain.setWordWrap(True)
        explain.setStyleSheet("color: #444;")
        layout.addWidget(explain)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(10)

        self.login_btn = QtWidgets.QPushButton("Login in Browser")
        self.login_btn.clicked.connect(self._start_login)

        self.register_btn = QtWidgets.QPushButton("Registration")
        self.register_btn.setToolTip("Opens the registration flow in your browser.")
        self.register_btn.clicked.connect(self._open_registration)

        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.setToolTip("Cancels the current login attempt.")
        self.cancel_btn.setDisabled(True)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel_login)

        btn_row.addWidget(self.login_btn)
        btn_row.addWidget(self.register_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #B00020;")
        layout.addWidget(self.status)

        layout.addStretch(1)

    def _set_busy(self, busy: bool) -> None:
        self.login_btn.setDisabled(busy)
        self.register_btn.setDisabled(busy)
        self.cancel_btn.setVisible(busy)
        self.cancel_btn.setDisabled(not busy)
        self.setCursor(QtCore.Qt.WaitCursor if busy else QtCore.Qt.ArrowCursor)

    def _cancel_login(self) -> None:
        self._current_attempt_id = 0
        if self._flow:
            self._flow.cancel()
            self._flow = None
        self.status.setStyleSheet("color: #B00020;")
        self.status.setText("Login canceled.")
        self._set_busy(False)

    def _open_registration(self) -> None:
        health = self.api.health()
        if not health.ok:
            self.status.setStyleSheet("color: #B00020;")
            details = ""
            if health.error:
                details = f"\n{health.error}"
                err = health.error.lower()
                if "read timed out" in err or "timed out" in err:
                    details += "\nTip: restart the server (stop any old uvicorn/python processes)."
                elif "refused" in err:
                    details += "\nTip: the server is not running (connection refused)."
            self.status.setText(f"Server not reachable at {API_BASE_URL}. Start the server first.{details}")
            return

        url = f"{API_BASE_URL.rstrip('/')}/desktop/register"
        webbrowser.open(url)
        self.status.setStyleSheet("color: #333;")
        self.status.setText("Opened registration in your browser.")

    def _start_login(self, prefill: bool = False) -> None:
        health = self.api.health()
        if not health.ok:
            self.status.setStyleSheet("color: #B00020;")
            details = ""
            if health.error:
                details = f"\n{health.error}"
                err = health.error.lower()
                if "read timed out" in err or "timed out" in err:
                    details += "\nTip: restart the server (stop any old uvicorn/python processes)."
                elif "refused" in err:
                    details += "\nTip: the server is not running (connection refused)."
            self.status.setText(f"Server not reachable at {API_BASE_URL}. Start the server first.{details}")
            return

        self._attempt_counter += 1
        attempt_id = self._attempt_counter
        self._current_attempt_id = attempt_id

        self._set_busy(True)
        self.status.setStyleSheet("color: #333;")
        self.status.setText("Opening browser... complete login in the browser tab (or click Cancel).")

        flow = DesktopBrowserLogin(API_BASE_URL)
        self._flow = flow
        redirect_uri = flow.start_callback_server()
        opened = flow.open_browser(redirect_uri=redirect_uri, prefill=prefill)
        if not opened:
            self.status.setStyleSheet("color: #B00020;")
            self.status.setText("Could not open a browser window. Please open the login URL manually.")
            self._current_attempt_id = 0
            self._flow = None
            self._set_busy(False)
            return

        # Wait in a background thread so UI stays responsive
        worker = _WaitForCodeWorker(flow=flow, attempt_id=attempt_id)
        worker.finished.connect(self._on_code_received)
        worker.start()
        self._worker = worker  # keep alive

    def _on_code_received(self, code: str, state: str, code_verifier: str, expected_state: str, reason: str, attempt_id: int):
        if attempt_id != self._current_attempt_id:
            return
        try:
            if reason == "canceled":
                self.status.setStyleSheet("color: #B00020;")
                self.status.setText("Login canceled.")
                return
            if reason == "timeout" or not code or not state:
                self.status.setStyleSheet("color: #B00020;")
                self.status.setText("Login timed out (1 minute). Please complete login in the browser and try again.")
                return
            if state != expected_state:
                self.status.setStyleSheet("color: #B00020;")
                self.status.setText("Login failed: state mismatch.")
                return

            res = self.api.desktop_exchange(code=code, code_verifier=code_verifier)
            if not res.ok or not res.data:
                self.status.setStyleSheet("color: #B00020;")
                self.status.setText(f"Login failed: {res.error or 'Unknown error'}")
                return

            token = res.data.get("access_token")
            if not token:
                self.status.setStyleSheet("color: #B00020;")
                self.status.setText("Login failed: missing token in response.")
                return

            self.api.set_access_token(token)
            self.status.setStyleSheet("color: #1B5E20;")
            self.status.setText("Login OK.")
            self.logged_in.emit(token)
        finally:
            self._current_attempt_id = 0
            self._flow = None
            self._set_busy(False)


class _WaitForCodeWorker(QtCore.QThread):
    finished = QtCore.pyqtSignal(str, str, str, str, str, int)  # code, state, verifier, expected_state, reason, attempt_id

    def __init__(self, flow: DesktopBrowserLogin, attempt_id: int):
        super().__init__()
        self.flow = flow
        self.attempt_id = attempt_id

    def run(self):
        code, state = self.flow.wait_for_code(timeout_s=60)
        if not code or not state:
            reason = "canceled" if self.flow.was_canceled else "timeout"
            self.finished.emit("", "", self.flow.code_verifier, self.flow.state, reason, self.attempt_id)
            return
        self.finished.emit(code, state, self.flow.code_verifier, self.flow.state, "ok", self.attempt_id)
