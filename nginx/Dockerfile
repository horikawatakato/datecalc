FROM nginx:1.30-alpine

# GHCR連携用ビルド引数（docker build --build-arg で上書き可能。app/Dockerfile と揃える）
ARG IMAGE_VERSION=latest
ARG GITHUB_REPOSITORY=horikawatakato/datecalc
ARG GITHUB_SERVER_URL=https://github.com
ARG BUILD_DATE=unknown
ARG GIT_REVISION=unknown

# OCI標準ラベル（GHCRがリポジトリと自動紐づけするために必要）
LABEL org.opencontainers.image.title="DateCalc nginx proxy" \
      org.opencontainers.image.description="TLS-terminating nginx reverse proxy for DateCalc" \
      org.opencontainers.image.version="${IMAGE_VERSION}" \
      org.opencontainers.image.source="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${GIT_REVISION}"

# ドメイン名はビルド時に焼き込まず、起動時に環境変数 DOMAIN から展開する。
#   公式 nginx イメージの entrypoint が /etc/nginx/templates/*.template を envsubst で
#   処理し、NGINX_ENVSUBST_OUTPUT_DIR へ書き出す（→ /etc/nginx/nginx.conf を生成）。
#   NGINX_ENVSUBST_FILTER で置換対象を ${DOMAIN} のみに限定し、$host 等の nginx 変数は温存する。
COPY nginx.conf.template /etc/nginx/templates/nginx.conf.template
ENV NGINX_ENVSUBST_OUTPUT_DIR=/etc/nginx \
    NGINX_ENVSUBST_FILTER=DOMAIN \
    DOMAIN=datecalc.duckdns.org

# 80(HTTP リダイレクト/ACME) と 443(HTTPS) の両方を公開
EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
