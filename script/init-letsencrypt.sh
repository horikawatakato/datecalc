#!/bin/sh
# =============================================================================
# init-letsencrypt.sh
#   Let's Encrypt の初回証明書取得をブートストラップするスクリプト。
#
#   nginx.conf は起動時に証明書ファイルを参照するため、証明書が無いと nginx が
#   起動できず、その結果 certbot の HTTP-01 チャレンジも通せない（鶏と卵）。
#   そこで「ダミー証明書を置く → nginx 起動 → ダミー削除 → 本証明書取得 →
#   nginx リロード」の順で初期化する。初回に一度だけ実行すればよい。
#
#   前提:
#     - このディレクトリに docker-compose.yml があること
#     - イメージは未デプロイ時 :latest にフォールバックして pull される（初回は .env 不要）
#     - ホストに openssl コマンドがあること（Amazon Linux / Ubuntu は標準で導入済み）
#     - private イメージの場合、事前に docker login ghcr.io 済みであること
#
#   使い方:
#     1) 下の DOMAIN と EMAIL を自分の値に変更
#     2) chmod +x init-letsencrypt.sh
#     3) ./init-letsencrypt.sh
# =============================================================================
set -eu

# ── ① 設定（自分の値に変更）─────────────────────────────────────────────────
DOMAIN="[DOMAIN]"                    # 取得したサブドメイン（リポジトリの nginx.conf と一致させる）
EMAIL="[EMAIL]"                      # 期限切れ通知などの連絡先
STAGING=0                            # 1 でステージング環境（レート制限が緩い。まず 1 で動作確認）

DATA_PATH="./certbot"
RSA_KEY_SIZE=4096
LIVE_DIR="$DATA_PATH/conf/live/$DOMAIN"

# ── ② 既存証明書の確認 ──────────────────────────────────────────────────────
if [ -d "$LIVE_DIR" ]; then
  printf "既存の証明書が %s に見つかりました。続行すると置き換えられます。[y/N] " "$DOMAIN"
  read -r decision
  case "$decision" in
    y|Y) : ;;
    *) echo "中止しました。"; exit 0 ;;
  esac
fi

# ── ③ ダミー証明書の作成（nginx を一旦起動させるため・ホストの openssl で生成）──
#      証明書ディレクトリはホストにバインドマウントされる ./certbot 配下なので、
#      ホスト側で直接ファイル操作してよい（コンテナ越しの操作は不要）。
echo "### ダミー証明書を作成します（$DOMAIN）..."
mkdir -p "$LIVE_DIR"
openssl req -x509 -nodes -newkey "rsa:$RSA_KEY_SIZE" -days 1 \
  -keyout "$LIVE_DIR/privkey.pem" \
  -out    "$LIVE_DIR/fullchain.pem" \
  -subj "/CN=localhost"

# ── ④ nginx 起動（ダミー証明書で起動し、80番で ACME チャレンジを受けられる状態に）──
echo "### nginx を起動します ..."
docker compose up --force-recreate -d nginx

# ── ⑤ ダミー証明書を削除（ホスト側で直接）────────────────────────────────────
echo "### ダミー証明書を削除します ..."
rm -rf "$DATA_PATH/conf/live/$DOMAIN" \
       "$DATA_PATH/conf/archive/$DOMAIN" \
       "$DATA_PATH/conf/renewal/$DOMAIN.conf"

# ── ⑥ 本物の証明書を取得 ────────────────────────────────────────────────────
#      compose の certbot サービスは entrypoint を「更新ループ」に上書きしているため、
#      一回限りの certonly 実行では --entrypoint certbot で既定の certbot に戻す
#      （付けないとループが起動するだけで certonly が実行されない）。
echo "### Let's Encrypt から証明書を取得します ..."
STAGING_ARG=""
[ "$STAGING" = "1" ] && STAGING_ARG="--staging"

docker compose run --rm --entrypoint certbot certbot certonly \
  --webroot -w /var/www/certbot \
  $STAGING_ARG \
  --email "$EMAIL" \
  -d "$DOMAIN" \
  --rsa-key-size "$RSA_KEY_SIZE" \
  --agree-tos \
  --no-eff-email \
  --force-renewal

# ── ⑦ nginx をリロードして本証明書を反映 ────────────────────────────────────
echo "### nginx をリロードします ..."
docker compose exec nginx nginx -s reload

echo ""
echo "完了しました。https://$DOMAIN にアクセスして鍵マークを確認してください。"
