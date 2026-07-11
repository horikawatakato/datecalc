FROM nginx:1.30-alpine

# ドメイン名はビルド時に焼き込まず、起動時に環境変数 DOMAIN から展開する。
#   公式 nginx イメージの entrypoint が /etc/nginx/templates/*.template を envsubst で
#   処理し、NGINX_ENVSUBST_OUTPUT_DIR へ書き出す（→ /etc/nginx/nginx.conf を生成）。
#   NGINX_ENVSUBST_FILTER で置換対象を ${DOMAIN} のみに限定し、$host 等の nginx 変数は温存する。
COPY nginx.conf.template /etc/nginx/templates/nginx.conf.template
ENV NGINX_ENVSUBST_OUTPUT_DIR=/etc/nginx \
    NGINX_ENVSUBST_FILTER=DOMAIN

# 80(HTTP リダイレクト/ACME) と 443(HTTPS) の両方を公開
EXPOSE 80 443

# 単体 docker run 用の既定起動。compose 経由では command で上書きされ、
# envsubst→証明書リロードループ→exec nginx を明示実行する（docker-compose.yml 参照）。
CMD ["nginx", "-g", "daemon off;"]
