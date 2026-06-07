FROM nginx:1.27-alpine

# デフォルトの nginx.conf を削除して独自の設定に置き換える
RUN rm /etc/nginx/nginx.conf
COPY nginx.conf /etc/nginx/nginx.conf

# 80(HTTP リダイレクト/ACME) と 443(HTTPS) の両方を公開
EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
