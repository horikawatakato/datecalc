FROM nginx:1.31-alpine

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

# デフォルトの nginx.conf を削除して独自の設定に置き換える
RUN rm /etc/nginx/nginx.conf
COPY nginx.conf /etc/nginx/nginx.conf

# 80(HTTP リダイレクト/ACME) と 443(HTTPS) の両方を公開
EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
