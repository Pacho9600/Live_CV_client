from __future__ import annotations

from PyQt5 import QtWidgets
from services.api_client import ApiClient


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self.setWindowTitle("Architecture Showcase — Main")
        self.setMinimumSize(800, 520)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QtWidgets.QLabel("Welcome")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        layout.addWidget(title)

        info = QtWidgets.QLabel(
            "Logged in via browser flow.\n\n"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.me_out = QtWidgets.QTextEdit()
        self.me_out.setReadOnly(True)
        layout.addWidget(self.me_out, 1)

        btn = QtWidgets.QPushButton("Fetch /me")
        btn.clicked.connect(self._fetch_me)
        layout.addWidget(btn)

        self._fetch_me()

    def _fetch_me(self):
        res = self.api.me()
        if res.ok and res.data:
            self.me_out.setText(str(res.data))
        else:
            self.me_out.setText(f"Error: {res.error}")
