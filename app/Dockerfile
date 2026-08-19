# ────────────────────────────────────────────
# ステージ1: 依存パッケージのインストール
# ────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app
COPY requirements.txt .
# 実行イメージへそのまま移せるよう /install に隔離インストール
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ────────────────────────────────────────────
# ステージ2: 実行イメージ
# ────────────────────────────────────────────
# builder と同一 base に固定（/install を /usr/local へ移すため、Python バージョンとパス構成を揃える）
FROM python:3.12-slim

# LABEL / ARG は置かない。理由は2つ:
#   - OCI ラベルは CI が --label で渡す（docker/metadata-action）ため、同名 LABEL は上書きされ届かない
#   - revision 等を ARG で受けると、LABEL 以降の層のビルドキャッシュを毎回壊す

# 非 root 実行用のユーザーを作成（最小権限で実行し侵害時の影響を抑える）
RUN useradd --create-home appuser
WORKDIR /app

# /install の隔離分を標準パス /usr/local へ配置（実行時に --prefix 不要で import できる）
COPY --from=builder /install /usr/local

# ビルドコンテキスト app/（.dockerignore で tests/ 等を除外）をコピー
#   所有者を実行ユーザー appuser に揃える（root 所有ファイルを非 root 実行下に残さない）
COPY --chown=appuser:appuser . .

# Python 実行時設定: 標準出力/エラーを即時フラッシュ（ログ欠落防止）し、
#   .pyc を書き出さない（使い捨てコンテナでは再利用されず、/app 配下への無駄な生成を防ぐ）
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# wsgi / DateCalc_server / DateCalc は src/ にあるため import 検索パスへ追加する
ENV PYTHONPATH=/app/src

USER appuser

EXPOSE 8000

# Gunicorn 経由で起動（DateCalc_server.py の app.run() は呼ばれない）
# 設定は /app/gunicorn.conf.py、アプリは wsgi:app（src/ 上）
CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:app"]
