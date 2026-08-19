# 1.29.7 未満に下げないこと。nginx.conf.template は、1.29.7 で既定になった
#   keepalive（upstream ブロック）/ proxy_http_version 1.1 / proxy_set_header Connection ""
#   の 3 つを省いている。下げても nginx -t は通るが、upstream 接続が HTTP/1.0 + Connection: close
#   に退行し、upstream keepalive が黙って無効になる。
FROM nginx:1.30-alpine

# LABEL / ARG は置かない。理由は2つ:
#   - OCI ラベルは CI が --label で渡す（docker/metadata-action）ため、同名 LABEL は上書きされ届かない
#   - revision 等を ARG で受けると、LABEL 以降の層のビルドキャッシュを毎回壊す

# ドメイン名はビルド時に焼き込まず、起動時に環境変数 DOMAIN から envsubst で展開する。
#   テンプレートを /etc/nginx/templates/ に置き、NGINX_ENVSUBST_OUTPUT_DIR へ nginx.conf を生成。
#   NGINX_ENVSUBST_FILTER で置換対象を ${DOMAIN} のみに限定し、$host 等の nginx 変数は温存する。
#   ※ 実行トリガは compose 側の担当。entrypoint の自動実行は走らず、proxy.command が同じスクリプトを明示実行する。
COPY nginx.conf.template /etc/nginx/templates/nginx.conf.template
ENV NGINX_ENVSUBST_OUTPUT_DIR=/etc/nginx \
    NGINX_ENVSUBST_FILTER=DOMAIN

EXPOSE 80 443

# 単体 docker run 用の既定起動（compose 経由では上記のとおり command で上書きされる）。
CMD ["nginx", "-g", "daemon off;"]
