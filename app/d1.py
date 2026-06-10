"""Cloudflare D1 backend exposing a sqlite3-like connection interface.

The app accesses SQLite exclusively through ``database.connect()`` with a
narrow API surface: ``conn.execute(sql, params)`` returning a cursor with
``fetchone()``/``fetchall()``, ``conn.executescript(...)``, ``commit()`` and
``close()``; rows are read by column name (``row["col"]`` / ``row.keys()``).
This module implements exactly that surface on top of the D1 HTTP API, so the
rest of the codebase runs unchanged against D1.

Notes / limitations:
- Every ``execute`` is one HTTPS round-trip to Cloudflare; latency is much
  higher than local SQLite.
- D1 auto-commits each statement; ``commit()`` is a no-op and multi-statement
  transactions are NOT atomic.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, Iterator, List, Optional, Sequence

import httpx

from .config import settings

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 3


class D1Error(RuntimeError):
    """Raised when the D1 HTTP API reports a failure."""


class D1Row:
    """Mapping-style row compatible with the sqlite3.Row usage in this app."""

    __slots__ = ("_data",)

    def __init__(self, data: Dict[str, Any]) -> None:
        self._data = data

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return list(self._data.values())[key]
        return self._data[key]

    def keys(self) -> List[str]:
        return list(self._data.keys())

    def __iter__(self) -> Iterator[Any]:
        return iter(self._data.values())

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"D1Row({self._data!r})"


class D1Cursor:
    def __init__(self, rows: List[D1Row]) -> None:
        self._rows = rows
        self._pos = 0

    def fetchone(self) -> Optional[D1Row]:
        if self._pos >= len(self._rows):
            return None
        row = self._rows[self._pos]
        self._pos += 1
        return row

    def fetchall(self) -> List[D1Row]:
        rows = self._rows[self._pos :]
        self._pos = len(self._rows)
        return rows

    def __iter__(self) -> Iterator[D1Row]:
        while True:
            row = self.fetchone()
            if row is None:
                return
            yield row


_client_lock = threading.Lock()
_client: Optional[httpx.Client] = None


def _http_client() -> httpx.Client:
    global _client
    with _client_lock:
        if _client is None:
            if not (settings.cf_account_id and settings.cf_d1_database_id and settings.cf_api_token):
                raise D1Error(
                    "WISE_DB_BACKEND=d1 requires CLOUDFLARE_ACCOUNT_ID, "
                    "CLOUDFLARE_D1_DATABASE_ID and CLOUDFLARE_API_TOKEN to be set."
                )
            base_url = (
                f"{settings.cf_api_base.rstrip('/')}/accounts/{settings.cf_account_id}"
                f"/d1/database/{settings.cf_d1_database_id}"
            )
            _client = httpx.Client(
                base_url=base_url,
                headers={"Authorization": f"Bearer {settings.cf_api_token}"},
                timeout=httpx.Timeout(30.0, connect=10.0),
            )
        return _client


def _normalize_param(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise D1Error(f"Unsupported D1 parameter type: {type(value).__name__}")


def _query(sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
    payload: Dict[str, Any] = {"sql": sql}
    if params:
        payload["params"] = [_normalize_param(value) for value in params]

    last_error: Optional[Exception] = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = _http_client().post("/query", json=payload)
        except httpx.TransportError as exc:
            last_error = exc
        else:
            if response.status_code not in _RETRYABLE_STATUS:
                return _parse_response(response, sql)
            last_error = D1Error(f"D1 HTTP {response.status_code}: {response.text[:300]}")
        if attempt < _MAX_ATTEMPTS:
            time.sleep(0.5 * attempt)
    raise D1Error(f"D1 query failed after {_MAX_ATTEMPTS} attempts: {last_error}") from last_error


def _parse_response(response: httpx.Response, sql: str) -> List[Dict[str, Any]]:
    try:
        body = response.json()
    except ValueError as exc:
        raise D1Error(f"D1 returned non-JSON response (HTTP {response.status_code})") from exc
    if not body.get("success"):
        errors = body.get("errors") or [{"message": f"HTTP {response.status_code}"}]
        detail = "; ".join(str(item.get("message", item)) for item in errors)
        raise D1Error(f"D1 query failed: {detail} (sql: {sql[:120]})")
    # /query returns one result object per SQL statement; the app issues a
    # single statement per execute(), so the first result carries its rows.
    result = body.get("result") or []
    if not result:
        return []
    return result[0].get("results") or []


class D1Connection:
    def execute(self, sql: str, params: Sequence[Any] = ()) -> D1Cursor:
        rows = _query(sql, params)
        return D1Cursor([D1Row(row) for row in rows])

    def executescript(self, script: str) -> None:
        # D1's /query endpoint accepts multiple ';'-separated statements.
        _query(script)

    def commit(self) -> None:  # D1 auto-commits each statement.
        return None

    def close(self) -> None:  # The underlying HTTP client is shared/pooled.
        return None


def d1_connect() -> D1Connection:
    return D1Connection()
