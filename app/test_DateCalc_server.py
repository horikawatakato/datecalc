"""DateCalc_server.py（Flask 層）のリクエストテスト。

計算ロジック本体の検証は test_DateCalc.py が担当する。ここでは HTTP の入出力
（ステータスコード・JSON の形状・400 ハンドリング）だけを確認し、サーバーが
DateCalc.calculate へ正しく橋渡ししていることを保証する。
"""

import pytest

from DateCalc_server import app


@pytest.fixture
def client():
    app.config.update(TESTING=True)
    return app.test_client()


def test_index_returns_html(client):
    """GET / は DateCalc.html を返す。"""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.content_type


def test_api_today(client):
    """GET /api/today は今日の年月日と曜日を JSON で返す。"""
    resp = client.get("/api/today")
    assert resp.status_code == 200
    data = resp.get_json()
    assert set(data) == {"year", "month", "day", "weekday"}
    assert isinstance(data["year"], int)
    assert data["weekday"] in "月火水木金土日"


def test_api_calculate_ok(client):
    """正常な year/month/day で差分計算結果（ok=True）が返る。"""
    resp = client.get("/api/calculate", query_string={"year": 2030, "month": 3, "day": 15})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["date_label"].startswith("2030年3月15日")
    assert data["cls"] in {"today", "future", "past"}


def test_api_calculate_invalid_date_returns_ok_false(client):
    """暦上存在しない日付は 200 のまま ok=False で返る（400 ではない）。"""
    resp = client.get("/api/calculate", query_string={"year": 2021, "month": 2, "day": 29})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is False
    assert "error" in data


def test_api_calculate_missing_param_returns_400(client):
    """必須パラメータ欠落（KeyError）は 400。"""
    resp = client.get("/api/calculate", query_string={"year": 2030, "month": 3})
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


def test_api_calculate_non_integer_returns_400(client):
    """整数に変換できない値（ValueError）は 400。"""
    resp = client.get("/api/calculate", query_string={"year": "abc", "month": 3, "day": 15})
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False
