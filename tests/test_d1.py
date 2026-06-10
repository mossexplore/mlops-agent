import json
import os
import sqlite3
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("CLOUDFLARE_ACCOUNT_ID", "test-account")
os.environ.setdefault("CLOUDFLARE_D1_DATABASE_ID", "test-db")
os.environ.setdefault("CLOUDFLARE_API_TOKEN", "test-token")

from app import d1  # noqa: E402


class FakeD1:
    """In-memory sqlite pretending to be the D1 /query HTTP endpoint."""

    def __init__(self) -> None:
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.requests = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(
            "/accounts/test-account/d1/database/test-db/query"
        )
        assert request.headers["authorization"] == "Bearer test-token"
        payload = json.loads(request.content)
        self.requests.append(payload)
        sql = payload["sql"]
        params = payload.get("params") or []
        try:
            if ";" in sql.strip().rstrip(";"):
                self.conn.executescript(sql)
                rows = []
            else:
                rows = [dict(row) for row in self.conn.execute(sql, params).fetchall()]
            self.conn.commit()
        except sqlite3.Error as exc:
            return httpx.Response(
                200,
                json={"success": False, "errors": [{"message": str(exc)}], "result": []},
            )
        return httpx.Response(
            200,
            json={"success": True, "errors": [], "result": [{"success": True, "results": rows}]},
        )


@pytest.fixture()
def fake_d1(monkeypatch):
    fake = FakeD1()
    client = httpx.Client(
        base_url="https://api.cloudflare.com/client/v4/accounts/test-account/d1/database/test-db",
        headers={"Authorization": "Bearer test-token"},
        transport=httpx.MockTransport(fake.handler),
    )
    monkeypatch.setattr(d1, "_client", client)
    yield fake
    client.close()


def test_execute_roundtrip(fake_d1):
    conn = d1.d1_connect()
    conn.executescript(
        "CREATE TABLE t_demo (id TEXT PRIMARY KEY, score REAL, note TEXT);"
        "CREATE INDEX idx_demo_score ON t_demo(score);"
    )
    conn.execute(
        "INSERT INTO t_demo (id, score, note) VALUES (?, ?, ?)", ("a1", 0.5, None)
    )
    conn.execute(
        "INSERT INTO t_demo (id, score, note) VALUES (?, ?, ?)", ("b2", 0.9, "hello")
    )

    row = conn.execute("SELECT * FROM t_demo WHERE id = ?", ("b2",)).fetchone()
    assert row["score"] == 0.9
    assert "note" in row.keys()

    rows = conn.execute("SELECT id FROM t_demo ORDER BY score DESC").fetchall()
    assert [r["id"] for r in rows] == ["b2", "a1"]

    missing = conn.execute("SELECT * FROM t_demo WHERE id = ?", ("nope",)).fetchone()
    assert missing is None

    conn.commit()
    conn.close()


def test_query_error_raises(fake_d1):
    conn = d1.d1_connect()
    with pytest.raises(d1.D1Error) as excinfo:
        conn.execute("SELECT * FROM missing_table")
    assert "missing_table" in str(excinfo.value)


def test_database_connect_routes_to_d1(fake_d1, monkeypatch):
    from types import SimpleNamespace

    from app import database

    # settings is a frozen dataclass; swap the module-level reference instead.
    monkeypatch.setattr(database, "settings", SimpleNamespace(db_backend="d1"))
    with database.connect() as conn:
        assert isinstance(conn, d1.D1Connection)
        conn.execute("CREATE TABLE t_route (id TEXT)")
        conn.execute("INSERT INTO t_route (id) VALUES (?)", ("x",))
        assert conn.execute("SELECT COUNT(*) AS c FROM t_route").fetchone()["c"] == 1
