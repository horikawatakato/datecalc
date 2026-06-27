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

# GHCR連携用ビルド引数（docker build --build-arg で上書き可能）
ARG IMAGE_VERSION=latest
ARG GITHUB_REPOSITORY=horikawatakato/datecalc
ARG GITHUB_SERVER_URL=https://github.com
ARG BUILD_DATE=unknown
ARG GIT_REVISION=unknown

# OCI標準ラベル（GHCRがリポジトリと自動紐づけするために必要）
LABEL org.opencontainers.image.title="DateCalc" \
      org.opencontainers.image.description="Date calculation web app (Flask + Gunicorn)" \
      org.opencontainers.image.version="${IMAGE_VERSION}" \
      org.opencontainers.image.source="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${GIT_REVISION}"

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

# wsgi / DateCalc_server / DateCalc は src/ にあるため import 検索パスへ追加する
ENV PYTHONPATH=/app/src

USER appuser

EXPOSE 8000

# Gunicorn 経由で起動（DateCalc_server.py の app.run() は呼ばれない）
# 設定は /app/gunicorn.conf.py、アプリは PYTHONPATH(/app/src) 上の wsgi:app
CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:app"]
