from __future__ import annotations

import sys
from PyQt5 import QtWidgets

from config import API_BASE_URL
from services.api_client import ApiClient
from ui.login_window import LoginWindow
from ui.main_window import MainWindow


def main():
    app = QtWidgets.QApplication(sys.argv)

    api = ApiClient(API_BASE_URL)

    login = LoginWindow(api=api)
    main_win = MainWindow(api=api)

    def on_logged_in(_token: str):
        main_win.show()
        login.hide()

    login.logged_in.connect(on_logged_in)

    login.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
