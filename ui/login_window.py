from __future__ import annotations

from PyQt5 import QtCore, QtWidgets

from config import API_BASE_URL
from services.api_client import ApiClient
from services.desktop_login_flow import DesktopBrowserLogin


class LoginWindow(QtWidgets.QMainWindow):
    logged_in = QtCore.pyqtSignal(str)  # access token

    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
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

        self.example_btn = QtWidgets.QPushButton("Example")
        self.example_btn.setToolTip("Opens the browser and pre-fills demo credentials on the login page.")
        self.example_btn.clicked.connect(lambda: self._start_login(prefill=True))

        btn_row.addWidget(self.login_btn)
        btn_row.addWidget(self.example_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #B00020;")
        layout.addWidget(self.status)

        layout.addStretch(1)

    def _set_busy(self, busy: bool) -> None:
        self.login_btn.setDisabled(busy)
        self.example_btn.setDisabled(busy)
        self.setCursor(QtCore.Qt.WaitCursor if busy else QtCore.Qt.ArrowCursor)

    def _start_login(self, prefill: bool = False) -> None:
        self._set_busy(True)
        self.status.setStyleSheet("color: #333;")
        self.status.setText("Opening browser… complete login in the browser tab.")

        flow = DesktopBrowserLogin(API_BASE_URL)
        redirect_uri = flow.start_callback_server()
        flow.open_browser(redirect_uri=redirect_uri, prefill=prefill)

        # Wait in a background thread so UI stays responsive
        worker = _WaitForCodeWorker(flow=flow)
        worker.finished.connect(self._on_code_received)
        worker.start()
        self._worker = worker  # keep alive

    def _on_code_received(self, code: str, state: str, code_verifier: str, expected_state: str):
        try:
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
            self._set_busy(False)


class _WaitForCodeWorker(QtCore.QThread):
    finished = QtCore.pyqtSignal(str, str, str, str)  # code, state, verifier, expected_state

    def __init__(self, flow: DesktopBrowserLogin):
        super().__init__()
        self.flow = flow

    def run(self):
        code, state = self.flow.wait_for_code(timeout_s=120)
        if not code or not state:
            # emit empty -> UI will show error
            self.finished.emit("", "", self.flow.code_verifier, self.flow.state)
            return
        self.finished.emit(code, state, self.flow.code_verifier, self.flow.state)
