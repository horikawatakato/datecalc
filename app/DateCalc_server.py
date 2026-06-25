"""
DateCalc サーバー (DateCalc_server.py)
=======================================
Flask で軽量な HTTP サーバーを立て、DateCalc.py の計算ロジックを Web API として公開する。
このファイル自身は計算を持たず、DateCalc.calculate / get_weekday に委譲する薄い橋渡し役で、
DateCalc.html はこのサーバー経由で Python 側の計算結果を受け取る。

エンドポイント:
    GET /               … DateCalc.html を返す（画面本体）
    GET /api/today      … 今日の日付情報（年月日・曜日）を JSON で返す
    GET /api/calculate  … year/month/day を受け取り、差分計算の結果を JSON で返す

起動方法:
    python DateCalc_server.py
ブラウザで http://localhost:5000 を開くと画面が表示される。停止は Ctrl+C。
"""

import sys
import os
from datetime import date
from flask import Flask, request, jsonify, send_from_directory

# どの作業ディレクトリから起動しても下の `from DateCalc import ...` を解決できるよう、
# このファイルと同じフォルダを import 検索パスの先頭に追加する
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# 計算ロジックは DateCalc.py に集約。このサーバーは呼び出して結果を中継するだけ
from DateCalc import calculate, get_weekday

app = Flask(__name__, static_folder=None)  # 自動の静的配信を無効化（.py などソースの露出を防ぐ）


# ── 静的ファイル ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """DateCalc.html をそのまま返す。"""
    return send_from_directory(BASE_DIR, "DateCalc.html")


# ── API エンドポイント ────────────────────────────────────────────────────────

@app.route("/api/today")
def api_today():
    """今日の日付情報を返す。画面ヘッダーの「今日 — …」表示に使う。

    Response JSON:
        {
            "year":    int,
            "month":   int,
            "day":     int,
            "weekday": str   # 漢字1文字。例: "木"
        }
    """
    today = date.today()
    return jsonify({
        "year":    today.year,
        "month":   today.month,
        "day":     today.day,
        "weekday": get_weekday(today),
    })


@app.route("/api/calculate")
def api_calculate():
    """日付の差分を計算して返す（実処理は DateCalc.calculate へ委譲）。

    Query parameters:
        year  (int, required) : 年（歴史年代。紀元前は負の整数）
        month (int, required) : 月
        day   (int, required) : 日

    Response JSON (成功):
        {
            "ok":         true,
            "date_label": str,   # 例: "2030年1月1日(木)"
            "diff":       int,   # 今日との差（未来=正、過去=負）
            "diff_label": str,   # 例: "1321日後 / 3年225日後"
            "cls":        str    # "today" | "future" | "past"
        }

    Response JSON (失敗):
        {
            "ok":    false,
            "error": str    # 例: "この日付は存在しません"
        }

    HTTP 400: パラメータが不正・不足の場合
    """
    # 必須クエリ year/month/day を整数として取得。欠落(KeyError)や非整数(ValueError)は 400
    try:
        year  = int(request.args["year"])
        month = int(request.args["month"])
        day   = int(request.args["day"])
    except (KeyError, ValueError):
        return jsonify({"ok": False, "error": "year / month / day を整数で指定してください"}), 400

    today = date.today()
    result = calculate(year, month, day, today)
    return jsonify(result)


# ── 起動 ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":  # pragma: no cover  （開発用の起動経路。テスト対象外）
    print("=" * 48)
    print("  日数計算機サーバー起動")
    print("  ブラウザで http://localhost:5000 を開いてください")
    print("  停止: Ctrl+C")
    print("=" * 48)
    # ローカル専用(127.0.0.1)。debug とリローダーは無効化して安定動作させる
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
