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


def test_api_calculate_year_out_of_range_returns_ok_false(client):
    """対応範囲外の年も 200 のまま ok=False で返る（date の上限超えで 500 にしない）。"""
    resp = client.get("/api/calculate", query_string={"year": 10000, "month": 1, "day": 1})
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


def test_api_calculate_content_type_is_json(client):
    """正常時も 400 時も Content-Type は application/json。

    HTML 側は「JSON でない応答＝通信エラー」で切り分けるので、この content-type が
    崩れると正常な ok:false（存在しない日付など）が通信エラー表示に化ける。行カバレッジ
    では検知できない契約なので、両ケースで明示的に固定する。
    """
    ok = client.get("/api/calculate", query_string={"year": 2030, "month": 3, "day": 15})
    assert ok.content_type.startswith("application/json")
    bad = client.get("/api/calculate", query_string={"year": "abc", "month": 3, "day": 15})
    assert bad.status_code == 400
    assert bad.content_type.startswith("application/json")


def test_api_today_content_type_is_json(client):
    """/api/today（ヘルスチェック用）も JSON を返す。"""
    resp = client.get("/api/today")
    assert resp.content_type.startswith("application/json")


def test_api_calculate_negative_year_is_bc(client):
    """負の年（歴史年代）が API 経由で受理され、BC 表記のラベルが返る。"""
    resp = client.get("/api/calculate", query_string={"year": -100, "month": 3, "day": 1})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["date_label"].startswith("BC100年3月1日")


@pytest.mark.parametrize("query", [
    {"year": 2030, "month": 3},              # day 欠落
    {"year": 2030, "day": 15},               # month 欠落
    {"month": 3, "day": 15},                 # year 欠落
    {},                                      # 全欠落
])
def test_api_calculate_any_missing_param_returns_400(client, query):
    """必須パラメータのどれが欠けても（KeyError）400。"""
    resp = client.get("/api/calculate", query_string=query)
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False
