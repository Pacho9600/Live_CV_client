from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any
import requests


@dataclass
class ApiResult:
    ok: bool
    status_code: int
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._access_token: Optional[str] = None

    def set_access_token(self, token: str) -> None:
        self._access_token = token

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self._access_token:
            h["Authorization"] = f"Bearer {self._access_token}"
        return h

    def desktop_exchange(self, code: str, code_verifier: str) -> ApiResult:
        url = f"{self.base_url}/api/auth/desktop/exchange"
        try:
            r = requests.post(url, json={"code": code, "code_verifier": code_verifier}, headers=self._headers(), timeout=10)
            if r.status_code == 200:
                return ApiResult(True, 200, data=r.json())
            try:
                detail = r.json().get("detail")
            except Exception:
                detail = r.text
            return ApiResult(False, r.status_code, error=str(detail))
        except Exception as e:
            return ApiResult(False, 0, error=str(e))

    def me(self) -> ApiResult:
        url = f"{self.base_url}/api/auth/me"
        try:
            r = requests.get(url, headers=self._headers(), timeout=10)
            if r.status_code == 200:
                return ApiResult(True, 200, data=r.json())
            try:
                detail = r.json().get("detail")
            except Exception:
                detail = r.text
            return ApiResult(False, r.status_code, error=str(detail))
        except Exception as e:
            return ApiResult(False, 0, error=str(e))
