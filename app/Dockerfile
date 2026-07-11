# ────────────────────────────────────────────
# ステージ1: 依存パッケージのインストール
# ────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ────────────────────────────────────────────
# ステージ2: 実行イメージ
# ────────────────────────────────────────────
FROM python:3.12-slim

# セキュリティ: 非 root ユーザーで実行
RUN useradd --create-home appuser
WORKDIR /app

# インストール済みパッケージをコピー
COPY --from=builder /install /usr/local

# アプリファイルをコピー（ビルドコンテキスト app/ の構成を保持）
#   src/DateCalc.py        … 計算ロジック
#   src/DateCalc_server.py … Flask アプリ本体
#   src/wsgi.py            … Gunicorn エントリポイント
#   static/DateCalc.html  … フロントエンド（/ で配信）
#   gunicorn.conf.py      … Gunicorn 設定（/app 直下）
COPY --chown=appuser:appuser . .

# Python 実行時設定: 標準出力/エラーを即時フラッシュ（ログ欠落防止）し、
#   .pyc を書き出さない（非 root 実行でも書き込みエラーを招かない）
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# wsgi / DateCalc_server / DateCalc は src/ にあるため import 検索パスへ追加する
ENV PYTHONPATH=/app/src

USER appuser

EXPOSE 8000

# Gunicorn 経由で起動（DateCalc_server.py の app.run() は呼ばれない）
# 設定は /app/gunicorn.conf.py、アプリは PYTHONPATH(/app/src) 上の wsgi:app
CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:app"]
