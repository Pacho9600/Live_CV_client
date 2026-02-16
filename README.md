# Client (PyQt5)

This client uses a **browser-based login flow**:
1. Starts a localhost callback server (one-time)
2. Opens the browser to the backend login page with `state` + `code_challenge` + `redirect_uri`
3. Receives `code` via localhost callback
4. Exchanges it for a JWT via `/api/auth/desktop/exchange`

Run:
```bash
pip install -r requirements.txt
python main.py
```
