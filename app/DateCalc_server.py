"""
DateCalc サーバー (DateCalc_server.py)
=======================================
Flask で軽量な HTTP サーバーを立て、DateCalc.py の計算ロジックを
Web API として公開します。DateCalc.html はこのサーバーを通じて
Pythonの計算結果を受け取ります。

起動方法:
    python DateCalc_server.py

ブラウザで http://localhost:5000 を開くと DateCalc.html が表示されます。
Ctrl+C で停止します。
"""

import sys
import os
from datetime import date
from flask import Flask, request, jsonify, send_from_directory

# DateCalc.py と同じディレクトリを検索パスに追加
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from DateCalc import calculate, get_weekday

app = Flask(__name__, static_folder=None)  # 自動静的ルートを無効化（ソース露出防止）


# ── 静的ファイル ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """DateCalc.html をそのまま返す。"""
    return send_from_directory(BASE_DIR, "DateCalc.html")


# ── API エンドポイント ────────────────────────────────────────────────────────

@app.route("/api/today")
def api_today():
    """
    今日の日付情報を返す。

    Response JSON:
        {
            "year":    int,
            "month":   int,
            "day":     int,
            "weekday": str   # 例: "木"
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
    """
    日付の差分を計算して返す。

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

if __name__ == "__main__":
    print("=" * 48)
    print("  日数計算機サーバー起動")
    print("  ブラウザで http://localhost:5000 を開いてください")
    print("  停止: Ctrl+C")
    print("=" * 48)
    # debug=False, use_reloader=False で本番向けに安定動作
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
