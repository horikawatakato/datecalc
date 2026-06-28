#!/usr/bin/env bash
# =============================================================================
# init-letsencrypt.sh
#   Let's Encrypt の初回証明書取得から HTTPS 起動・動作確認までを 1 本で行う、
#   自己完結型のブートストラップスクリプト。
#   ※ 証明書取得ロジック（ダミー証明書→proxy起動→ダミー削除→本証明書取得→
#     proxyリロード）は obtain_cert() として本スクリプトに内蔵済み。別スクリプトは不要です。
#
#   実行する処理:
#     - DOMAIN / EMAIL を引数で受け取る
#     - 事前チェック（DNS 一致 / 80番空き / openssl）… 失敗したら中断
#     - ステージングで取得（レート制限を消費しない動作確認）
#       └─ 取得成功後に、本番へ進むかの確認プロンプトを表示
#     - 本番証明書に切り替えて取得し、発行者(issuer)を検証
#     - 全サービス起動（docker compose up -d）とローカル動作確認
#
#   このスクリプトの「前提」（先に手動で済ませること）:
#     - docker-compose.yml を同じディレクトリに配置済み（このスクリプトと 2 つだけでよい）
#     - （private イメージなら）docker login ghcr.io 済み
#     - （ECS から移行する場合のみ）既存 ECS を停止し 80番を解放済み
#     - ホストに openssl があること（Amazon Linux / Ubuntu は標準で導入済み）
#
#   使い方（例: ドメイン myapp.duckdns.org / 連絡先 you@example.com の場合）:
#     1) docker-compose.yml と本スクリプトを同じディレクトリに置き、そこへ移動する
#          cd /opt/app
#     2) 実行権限を付与する
#          chmod +x init-letsencrypt.sh
#     3) myapp.duckdns.org / you@example.com を自分の値に置き換えて実行する
#        （ドメインは proxy コンテナの環境変数 DOMAIN（compose / .env）と同じ値にすること）
#          ./init-letsencrypt.sh -d myapp.duckdns.org -e you@example.com
#     4) ステージング成功後の「本番証明書を取得しますか？ [y/N]」で y を入力すると本番取得へ進む
# =============================================================================
set -euo pipefail

# ── スクリプトのある場所（= /opt/app 想定）で動作させる ─────────────────
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

DATA_PATH="./certbot"        # 証明書等の保存先ベース（compose は ./certbot/conf を /etc/letsencrypt にマウント）
RSA_KEY_SIZE=4096
DOMAIN=""
EMAIL=""

die()  { echo "ERROR: $*" >&2; exit 1; }
info() { echo "### $*"; }

usage() {
  cat <<USAGE
Usage: $0 -d <domain> -e <email>
  -d  取得するサブドメイン（例: myapp.duckdns.org / 環境変数 DOMAIN に設定したものと一致させる）
  -e  連絡先メール（例: you@example.com）
USAGE
  exit 1
}

# ── 証明書取得（ダミー証明書→proxy起動→ダミー削除→本証明書取得→リロード）────
#   引数: $1 = staging フラグ（1=ステージング, 0=本番）
#   ※ ダミーを「proxy起動より前」に作るため、通常実行中に proxy が証明書なしで
#     起動する瞬間はなく、クラッシュしない。
obtain_cert() {
  local staging="$1"
  local staging_arg=""
  local label="本番"
  if [ "$staging" = "1" ]; then staging_arg="--staging"; label="ステージング"; fi
  local live_dir="$DATA_PATH/conf/live/$DOMAIN"

  # ① ダミー証明書を作成（proxy を一旦起動させるため・ホストの openssl で生成）
  info "[$label] ダミー証明書を作成（$DOMAIN）..."
  mkdir -p "$live_dir"
  openssl req -x509 -nodes -newkey "rsa:$RSA_KEY_SIZE" -days 1 \
    -keyout "$live_dir/privkey.pem" \
    -out    "$live_dir/fullchain.pem" \
    -subj "/CN=localhost" >/dev/null 2>&1

  # ② proxy 起動（ダミーで起動し、80番で ACME チャレンジを受けられる状態に）
  info "[$label] proxy を起動 ..."
  docker compose up --force-recreate -d proxy

  # ③ ダミー証明書を削除（ホスト側で直接）
  info "[$label] ダミー証明書を削除 ..."
  rm -rf "$DATA_PATH/conf/live/$DOMAIN" \
         "$DATA_PATH/conf/archive/$DOMAIN" \
         "$DATA_PATH/conf/renewal/$DOMAIN.conf"

  # ④ 本物の証明書を取得（compose の cert は entrypoint を更新ループに上書き
  #    しているため、一回限りの certonly は --entrypoint certbot で既定に戻す）
  info "[$label] Let's Encrypt から証明書を取得 ..."
  docker compose run --rm --entrypoint certbot cert certonly \
    --webroot -w /var/www/certbot \
    $staging_arg \
    --email "$EMAIL" \
    -d "$DOMAIN" \
    --rsa-key-size "$RSA_KEY_SIZE" \
    --agree-tos \
    --no-eff-email \
    --force-renewal

  # ⑤ proxy をリロードして証明書を反映
  info "[$label] proxy をリロード ..."
  docker compose exec proxy nginx -s reload
}

# ── 引数解析 ────────────────────────────────────────────────────────────────
while getopts ":d:e:h" opt; do
  case "$opt" in
    d) DOMAIN="$OPTARG" ;;
    e) EMAIL="$OPTARG" ;;
    h|*) usage ;;
  esac
done
[ -n "$DOMAIN" ] && [ -n "$EMAIL" ] || usage

# ── 前提（配置・コマンド）の存在チェック ────────────────────────────────────
info "前提チェック ..."
[ -f docker-compose.yml ]     || die "docker-compose.yml が見つかりません（このスクリプトと同じディレクトリに配置してください）"
command -v docker  >/dev/null || die "docker が見つかりません（Docker をインストールしてください）"
command -v openssl >/dev/null || die "openssl がありません（例: sudo dnf install -y openssl / sudo apt install -y openssl）"
docker compose config >/dev/null || die "docker-compose.yml の構文エラー"

# 既存の本番証明書を誤って消さないよう、初回専用としてガードする
if [ -d "$DATA_PATH/conf/live/$DOMAIN" ]; then
  die "既に $DATA_PATH/conf/live/$DOMAIN があります。本スクリプトは初回取得専用です。
     再取得する場合は手動で $DATA_PATH/conf を整理してから実行してください。"
fi

info "対象ドメイン: $DOMAIN / 連絡先: $EMAIL"

# ── 事前チェック：1つでも失敗したら取得を始めずに中断 ──────────────────────
info "事前チェック（DNS 一致 / 80番空き / openssl）..."
fail=0

# ① DNS が この EC2 を指しているか（IMDSv2。取得不可なら手動確認を促す）
TOKEN="$(curl -s --max-time 3 -X PUT http://169.254.169.254/latest/api/token \
           -H 'X-aws-ec2-metadata-token-ttl-seconds: 60' || true)"
MYIP=""
[ -n "$TOKEN" ] && MYIP="$(curl -s --max-time 3 \
           -H "X-aws-ec2-metadata-token: $TOKEN" \
           http://169.254.169.254/latest/meta-data/public-ipv4 || true)"
DNSIP="$(getent hosts "$DOMAIN" | awk '{print $1}' | head -1 || true)"
if [ -n "$MYIP" ]; then
  echo "  EC2=$MYIP  DNS=$DNSIP"
  if [ "$MYIP" != "$DNSIP" ]; then
    echo "  !! DNS が EC2 の IP と一致しません（DNS（DuckDNS 等）の設定を見直す）"; fail=1
  else
    echo "  DNS 一致 OK"
  fi
else
  echo "  ?? IMDS から IP を取得できませんでした。'nslookup $DOMAIN' が EC2 の IP と"
  echo "     一致するか手動で確認してください（DNS 解決結果=$DNSIP）"
fi

# ② 80番が空いているか（ECS や既存 compose が握っていないか）
if sudo ss -ltnp 2>/dev/null | grep -q ':80 '; then
  echo "  !! 80番が使用中です。既存 compose は 'docker compose down'、ECS 運用中なら ECS サービスを停止"; fail=1
else
  echo "  80番は空き OK"
fi

# ③ openssl（ダミー証明書の生成と最後の検証に必要）
if command -v openssl >/dev/null; then echo "  openssl OK"; else echo "  !! openssl 無し"; fail=1; fi

[ "$fail" -eq 0 ] || die "事前チェックに失敗しました。上記を解消してから再実行してください。"

# ── ステージングで取得（動作確認）───────────────────────────────────────────
info "ステージングで証明書取得を試行 ..."
docker compose pull || die "docker compose pull に失敗（docker login ghcr.io を確認）"
obtain_cert 1
info "ステージング取得に成功しました。"

# ── 確認（ステージング結果を確認してから本番へ）──────────────────────────────
printf "本番証明書を取得しますか？ [y/N] "
read -r ans || ans=""    # 非対話(EOF)時も n と同様に安全に中止させる
case "$ans" in
  y|Y) : ;;
  *) info "本番取得を中止しました（ステージング証明書のまま）。"; exit 0 ;;
esac

# ── 本番証明書に切り替えて取得 ──────────────────────────────────────────────
info "ステージング証明書を削除し、本番証明書を取得 ..."
rm -rf "$DATA_PATH/conf/live" "$DATA_PATH/conf/archive" "$DATA_PATH/conf/renewal"
obtain_cert 0

# ── 検証：発行者が STAGING/Fake でないこと ──────────────────────────────────
info "発行者(issuer)を検証 ..."
CERT="$DATA_PATH/conf/live/$DOMAIN/fullchain.pem"
[ -f "$CERT" ] || die "証明書が見つかりません: $CERT"
ISSUER="$(openssl x509 -in "$CERT" -noout -issuer)"
echo "  $ISSUER"
if echo "$ISSUER" | grep -qiE 'staging|fake'; then
  die "まだステージング証明書です。原因を確認のうえ再実行してください。"
fi
openssl x509 -in "$CERT" -noout -enddate

# ── 全サービス起動と動作確認 ────────────────────────────────────────────────
info "全サービスを起動（docker compose up -d）..."
docker compose up -d
sleep 5
docker compose ps

# proxy が Restarting（証明書を読めずクラッシュループ等）でないこと
if docker compose ps proxy 2>/dev/null | grep -qi 'restart'; then
  die "proxy が Restarting です。'docker compose logs proxy' を確認してください。"
fi

# ローカルから実ホスト名の vhost をテスト（--resolve で 127.0.0.1 へ向ける。
# EC2 が自分の外部IPに回り込めない環境でも確実に確認できる）
info "ローカル動作確認 ..."
CODE_HTTPS="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
              --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/" || true)"
CODE_HTTP="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
              --resolve "$DOMAIN:80:127.0.0.1" "http://$DOMAIN/" || true)"
echo "  HTTPS(443) -> $CODE_HTTPS （期待: 200）"
echo "  HTTP(80)   -> $CODE_HTTP （期待: 301）"
[ "$CODE_HTTPS" = "200" ] || echo "  ?? HTTPS が 200 になりません。'docker compose logs proxy app' を確認してください"
[ "$CODE_HTTP" = "301" ]  || echo "  ?? HTTP の 301 リダイレクトが確認できません。nginx 設定（生成元 nginx.conf.template / 環境変数 DOMAIN、稼働中はコンテナ内 /etc/nginx/nginx.conf）を確認してください"

echo
info "セットアップ完了です。"
echo "  ・外部からの最終確認は手元の PC から: curl -I https://$DOMAIN/  （HTTP/2 200）"
echo "  ・ブラウザで https://$DOMAIN を開き、鍵マークが出れば完了です。"
