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

You can override the server base URL (default `http://127.0.0.1:8000`) with:

```powershell
$env:LIVE_CV_API_BASE_URL = "http://127.0.0.1:8000"
python main.py
```

Troubleshooting (Windows):
```powershell
netstat -ano | findstr ":8000"
Stop-Process -Id <pid> -Force
```
