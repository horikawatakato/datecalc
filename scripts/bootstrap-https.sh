#!/usr/bin/env bash
# ====================================================================================================
# bootstrap-https.sh
#   Let's Encrypt 証明書取得と、HTTPS 稼働・ローカル動作確認を行う初回セットアップスクリプト
#
#   事前準備:
#     - 本スクリプトと docker-compose.yml を同じディレクトリに配置（.env は本スクリプトが生成）
#     - CI により GHCR へ app / proxy イメージが push 済み（本スクリプトはビルドせず pull する）
#     - （private イメージなら）docker login ghcr.io 済み
#     - docker があり、デーモンが稼働し、docker compose が v2 プラグインであること
#     - ホストに openssl / curl / ss（iproute2）/ getent（glibc）があること（Amazon Linux / Ubuntu は標準導入）
#     ※ 80番の事前解放は不要（自プロジェクトの残骸は自動停止する。停止できない場合と他が握っている場合は中断）
#
#   実行手順:
#     1) 配置したディレクトリへ移動
#          cd /opt/app
#     2) 実行権限を付与
#          chmod +x bootstrap-https.sh
#     3) 実行し、対話プロンプトでドメイン / GitHub オーナー / （任意）メールアドレスを入力
#          ./bootstrap-https.sh
#
#   終了コード:
#     0                正常終了（本番証明書の取得を n で中止した場合も 0。後始末に失敗した場合は 1）
#     1                セットアップ失敗（前提不足 / 初回ガード / 80番占有 / 証明書取得の失敗など）、
#                      または後始末で残存物を検出（0 で終わるはずだった経路のみ格上げ。2 以上は保つ）
#     2                証明書取得と docker compose up -d は完了したが、ローカル動作確認に失敗
#     129 / 130 / 143  SIGHUP（SSH 切断）/ Ctrl-C（SIGINT）/ SIGTERM で中断
#     上記以外         set -e により外部コマンドの終了コードがそのまま出たもの
#
#   中断・失敗時の後始末（EXIT トラップ）:
#     ダミー / ステージング証明書を削除し、コンテナは停止する（ログを残すため削除はしない）。
#     本番証明書の取得に入って以降は証明書を削除せず、保持して手動確認を促す
#     （発行者チェックでステージングと判明した場合のみ削除する）。
#     n で中止した場合はステージング証明書を削除し、コンテナも削除する（実行前の状態へ戻す）。
#     発行者チェック合格後は証明書もコンテナも一切触れない。
# ====================================================================================================
# shellcheck disable=SC2153
set -euo pipefail

# ── 実行ディレクトリと定数 ───────────────────────────────────────────────────────────────────────────────
# スクリプトのある場所（= /opt/app 想定）で動作させる。pwd -P で物理パス化（compose の working_dir ラベルと厳密一致させるため）。
APP_DIR="$(cd "$(dirname "$0")" && pwd -P)"
cd "$APP_DIR"

CERTBOT_DIR="./certbot"  # 証明書等の保存先ベース（compose は ./certbot/conf を /etc/letsencrypt にマウント）
DUMMY_KEY_BITS=2048      # proxy を一旦起動させるためだけの捨て鍵。長さは問わない（本物の鍵は certbot 既定）
IMDS_TIMEOUT=3           # IMDS 応答待ち（秒）。EC2 以外では応答が無いので短く打ち切る
START_WAIT=5             # docker compose up -d 後、状態を見るまでの待ち（秒）
PROBE_RETRIES=10         # 動作確認の最大試行回数
PROBE_INTERVAL=2         # 動作確認のリトライ間隔（秒）
PROBE_TIMEOUT=5          # 動作確認 1 回あたりの curl タイムアウト（秒。宛先は --resolve で 127.0.0.1 固定）

# ── 共通ヘルパ（関数定義）────────────────────────────────────────────────────────────────────────────────
die()  { echo "ERROR: $*" >&2; exit 1; }   # 異常終了（メッセージは stderr へ）
info() { echo "$*"; }                      # スクリプト自身のメッセージはこれを通す（出力の単一窓口）

# ログ確認の案内文。終了後は .env も export した APP_IMAGE/PROXY_IMAGE も残らず、docker compose 系は
#   ${APP_IMAGE:?} 等の未解決で失敗するため素の docker logs で案内する。
#   同名サービスを持つ別プロジェクトを拾わないよう、他の docker ps と同じく working_dir で絞る。
# shellcheck disable=SC2016
hint_log() {
  printf 'ログ確認: docker logs $(docker ps -aq -f label=com.docker.compose.project.working_dir=%s -f label=com.docker.compose.service=%s | head -1)' \
    "$APP_DIR" "$1"
}

# 入力ヘルパ（ラベルを1行出力し、次行で read。前後の空白は取り除く）。
ask() {
  local _label="$1" _var="$2" _val=""
  info "$_label"
  read -r _val || die "入力が読み取れませんでした（対話端末で実行してください）"
  _val="${_val#"${_val%%[![:space:]]*}"}"  # 先頭の空白を除去
  _val="${_val%"${_val##*[![:space:]]}"}"  # 末尾の空白を除去
  printf -v "$_var" '%s' "$_val"
}

# y/n 確認（yes=0 / no=1 を返す）。
#   EOF は ask と同じく die する。n 扱いにすると、標準入力が閉じただけで「利用者が中止を選んだ」
#   ことになり、証明書が取れていないのに exit 0（正常終了）を返してしまう。
confirm() {
  local _ans
  while :; do
    info "$1 [y/n]"
    read -r _ans || die "入力が読み取れませんでした（対話端末で実行してください）"
    case "$_ans" in
      y|Y) return 0 ;;
      n|N) return 1 ;;
      *)   info "y または n を入力してください" ;;
    esac
  done
}

# ── 前提チェック（引数 / docker-compose.yml / 必須コマンド / Docker 環境）─────────────────────────────────
[ "$#" -eq 0 ] || die "引数なしで実行してください"

info "初回セットアップ（Let's Encrypt 証明書取得と、HTTPS 稼働・ローカル動作確認）"
info

[ -f docker-compose.yml ] || die "docker-compose.yml が見つかりません（このスクリプトと同じディレクトリに配置してください）"
# ss が無いと 80番チェックが「空き」に、curl が無いと DNS 事前チェックが素通りに化けるため必須とする。
REQUIRED_CMDS="docker openssl curl ss getent"
for _cmd in $REQUIRED_CMDS; do
  command -v "$_cmd" >/dev/null || die "$_cmd が見つかりません（インストールしてから再実行してください）"
done
# docker はバイナリの存在だけでは足りない。デーモンが停止していると 80番チェックの docker ps が
#   空振りして「空き OK」に化け、compose v1 しか無いと compose config の失敗が YAML の誤りに見える。
docker compose version >/dev/null 2>&1 \
  || die "docker compose（v2 プラグイン）が使えません（docker-compose v1 では動きません）"
docker info >/dev/null 2>&1 \
  || die "Docker デーモンに接続できません（デーモンの起動状態と実行ユーザーの権限を確認してください）"
info "前提 OK（docker-compose.yml / $REQUIRED_CMDS / Docker デーモン / compose v2）"

# ── 入力 → 確認（ドメイン / GitHub オーナー / （任意）メールアドレス）──────────────────────────────────────
info "以下を入力してください"
info

L_DOMAIN="証明書を取得するドメイン（リポジトリ変数 DOMAIN と同じ）:"
L_OWNER="GitHub オーナー（ユーザー名または Organization 名）:"
L_EMAIL="（任意）証明書の有効期限が近づいた際の通知先メールアドレス:"

while :; do
  # 入力値は .env / イメージ参照 / nginx の server_name / curl --resolve / certbot 引数へ、
  #   ドメインはさらにコンテナ内 root の rm -rf へもそのまま渡るため、ここで形を検査する。
  ask "$L_DOMAIN" DOMAIN
  case "$DOMAIN" in
    "")               info "ドメインが未入力です"; info; continue ;;
    *[!a-zA-Z0-9.-]*) info "ドメインに使えない文字が含まれています"; info; continue ;;
  esac
  # 上の case は空と使用文字しか見ないため、ホスト名としての形はここで見る（'..' や先頭/末尾のドット・ハイフンを弾く）。
  printf '%s' "$DOMAIN" \
    | grep -qE '^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)+$' \
    || { info "ドメイン名の形式ではありません（例: example.com）"; info; continue; }

  ask "$L_OWNER" OWNER
  # GitHub の命名規則ではなく GHCR の名前空間で使える文字（[a-z0-9._-]、大文字は後で小文字化する）で緩めに判定する
  #   （厳しくして正当なオーナー名を弾く方が損害が大きいため）。
  case "$OWNER" in
    "")                 info "GitHub オーナーが未入力です"; info; continue ;;
    *[!a-zA-Z0-9._-]*)  info "GitHub オーナーに使えない文字が含まれています"; info; continue ;;
  esac

  ask "$L_EMAIL" EMAIL
  case "$EMAIL" in
    "")            ;;
    *[[:space:]]*) info "メールアドレスに空白が含まれています"; info; continue ;;
    *@*.*)         ;;
    *)             info "メールアドレスの形式ではありません（不要なら空欄）"; info; continue ;;
  esac

  info
  confirm "入力内容は正しいですか？" && break
  info
done
info

# ── 初回ガード（既存の証明書 / .env があれば中断）─────────────────────────────────────────────────────────
# 既存の証明書（本番/ステージング）を誤って消さないよう、初回専用としてガードする。
if [ -d "$CERTBOT_DIR/conf/live/$DOMAIN" ]; then
  die "既に $CERTBOT_DIR/conf/live/$DOMAIN があります（本スクリプトは初回専用）
     再取得は手動で $CERTBOT_DIR/conf を整理してから実行してください"
fi

# .env は本スクリプトが生成・削除する一時ファイル。既存物は CI デプロイ済みか手作業の設定であり、
#   上書きすると復元できないため内容を問わず中断する。
if [ -f .env ]; then
  die ".env が既に存在します（CI デプロイ済み、または手作業の設定 / 本スクリプトは初回専用）
     .env を退避または削除してから実行してください"
fi

# ── 事前チェック（DNS の不一致を検出したら取得を始めずに中断）───────────────────────────────────────────────
info "事前チェック（DNS 一致）..."
fail=0

# DNS がこの EC2 を指しているか（IMDSv2。取得不可なら手動確認を促す）。
TOKEN="$(curl -s --max-time "$IMDS_TIMEOUT" -X PUT http://169.254.169.254/latest/api/token \
           -H 'X-aws-ec2-metadata-token-ttl-seconds: 60' || true)"
MYIP=""
[ -n "$TOKEN" ] && MYIP="$(curl -s --max-time "$IMDS_TIMEOUT" \
           -H "X-aws-ec2-metadata-token: $TOKEN" \
           http://169.254.169.254/latest/meta-data/public-ipv4 || true)"
# getent hosts は AAAA を先に返すことがあり、IPv6 を持つドメインでは IPv4 比較が外れる。ahostsv4 で IPv4 に限定し、
#   A レコードが複数ある構成もあるので先頭 1 件ではなく全件との一致を見る。
DNSIPS="$(getent ahostsv4 "$DOMAIN" | awk '{print $1}' | sort -u || true)"
DNSIPS_1LINE="$(printf '%s' "$DNSIPS" | tr '\n' ' ')"
if [ -n "$MYIP" ]; then
  info "  EC2=$MYIP  $DOMAIN=$DNSIPS_1LINE"
  if printf '%s\n' "$DNSIPS" | grep -Fqx "$MYIP"; then
    info "  DNS 一致 OK"
  else
    info "  $DOMAIN の DNS が EC2 を指していません（DNS 設定を見直してください）"; fail=1
  fi
else
  info "  IMDS（EC2 のメタデータ）から IP を取得できませんでした"
  info "     'nslookup $DOMAIN' で EC2 を指しているか手動で確認してください（DNS 解決結果=$DNSIPS_1LINE）"
fi

[ "$fail" -eq 0 ] || die "事前チェックに失敗（上記を解消してから再実行してください）"

# ── イメージ参照の導出（GHCR の app / proxy）─────────────────────────────────────────────────────────────
# GitHub オーナーからイメージ参照を導出して export（compose がプロセス環境から拾う）。
#   GHCR は小文字前提のため小文字化（CI の metadata-action と同じ）。
#   .env には書かず export で供給（.env は DOMAIN+OWNER のみ）。初回は :latest でよい。
OWNER="$(printf '%s' "$OWNER" | tr '[:upper:]' '[:lower:]')"
export APP_IMAGE="ghcr.io/${OWNER}/app:latest"
export PROXY_IMAGE="ghcr.io/${OWNER}/proxy:latest"

# ── 中断・失敗時の後始末（状態変数 → EXIT トラップ → シグナルトラップ）──────────────────────────────────────
# 後始末の「担当範囲」を表す状態。トラップから参照するため trap 設置より前に初期化する（set -u 対策）。
CERT_STATE=none   # none | dummy | staging | production | verified
STACK_UP=0        # 1 = 本スクリプトがコンテナを起動した
CLEANUP_LEFT=0    # 1 = 後始末の確認で残存物を検出した（終了コードの格上げに使う）

# 中断・失敗時の後始末。証明書 → コンテナの順に処理し、それぞれ処理後に残存を確認する。
#   remove_cert / MSG_CERT_LEFT / ours_containers を前方参照するが、CERT_STATE と STACK_UP が
#   初期値を離れるのはそれらの定義より後（obtain_cert 以降）なので、未定義のまま呼ばれることはない。
# shellcheck disable=SC2329
cleanup_on_abort() {
  local _rc="$1"
  # 発行者チェックを通った後は本番配信が成立しているので、証明書もコンテナも一切触れない。
  if [ "$CERT_STATE" = "verified" ]; then return 0; fi
  case "$CERT_STATE" in
    # 本番の証明書は消さない（発行済みか判別できず、消すと重複証明書のレート制限だけを消費するため）。
    #   コンテナは下の共通処理で停止する — 発行者チェック前で、本番配信が成立したとはまだ言えないため。
    production) info "本番証明書の可能性があるファイルは保持しました（再実行前に $CERTBOT_DIR/conf を確認してください）" || true ;;
    dummy)      info "後始末: ダミー証明書を削除します ..."      || true
                remove_cert || { CLEANUP_LEFT=1; info "$MSG_CERT_LEFT" || true; } ;;
    staging)    info "後始末: ステージング証明書を削除します ..." || true
                remove_cert || { CLEANUP_LEFT=1; info "$MSG_CERT_LEFT" || true; } ;;
  esac

  [ "$STACK_UP" = "1" ] || return 0
  # 自発的な中止（rc=0 = n 中止）は実行前の状態へ完全撤収する。失敗・中断（rc≠0）は down では
  #   コンテナごと消えて die が案内する docker logs を読めなくなるため stop に留める（80番はどちらも解放される）。
  #   compose の終了コードだけでは足りないため、remove_cert と同じく実行後に docker ps で残存を確認する。
  local _left
  if [ "$_rc" -eq 0 ]; then
    docker compose down --remove-orphans >/dev/null 2>&1 || true
    _left="$(ours_containers -a)"   # 削除なので停止済みも残っていてはいけない
    if [ -z "$_left" ]; then
      # 確認しているのは残存の有無なので、「削除しました」と実績は断定しない。
      info "後始末: 本プロジェクトのコンテナは残っていません" || true
    else
      CLEANUP_LEFT=1
      info "後始末: 削除できずに残っているコンテナ:" || true
      # shellcheck disable=SC2086
      docker inspect --format '    {{.Name}}  ({{.State.Status}})' $_left 2>/dev/null || true
      info "  手動で削除するには: docker rm -f <上記コンテナ名>" || true
    fi
  else
    docker compose stop >/dev/null 2>&1 || true
    _left="$(ours_containers)"      # 停止なので running が残っていてはいけない
    if [ -z "$_left" ]; then
      info "後始末: 本プロジェクトの稼働中コンテナはありません（停止済みのコンテナのログは docker logs で参照できます）" || true
    else
      CLEANUP_LEFT=1
      info "後始末: 停止できずに残っているコンテナ:" || true
      # shellcheck disable=SC2086
      docker inspect --format '    {{.Name}}  ({{.State.Status}})' $_left 2>/dev/null || true
      info "  手動で停止するには: docker stop <上記コンテナ名>" || true
    fi
  fi
}

# .env は一時物。残すと初回 CI デプロイのロールバック先が壊れるため全退出で消す。
#   生成より先に仕掛けて、生成直後に中断されても取り残さないようにする。
#   HUP/INT/TERM は必ず exit する（トラップが戻るだけだとスクリプトは次の行から実行を続け、
#   中断したつもりのまま本番証明書の取得へ進む）。exit すれば EXIT トラップが走るので後始末は 1 箇所で足りる。
#   HUP（SSH 切断）も捕捉する。無捕捉でも EXIT トラップは走るが $? は直前のコマンドの状態のままで、
#   実際の終了ステータス 129 と表示が食い違うため。
#   終了コードは最後に必ず表示する（メッセージだけでは 0 / 1 / 2 のどれで終わったか判別できないため）。
# shellcheck disable=SC2329
on_exit() {
  local _rc=$?   # 後続コマンドで上書きされる前に退避
  trap '' HUP INT TERM             # 後始末中の再割り込みで中途半端に終わらせない
  cleanup_on_abort "$_rc" || true  # compose は .env を必要とするので削除より前
  # rm を裸で置くと、失敗時に set -e がここで終了して終了コードの表示に到達せず、
  #   表示されないまま rc が 1 に化ける。remove_cert と同じ「削除 → 確認」に揃える。
  rm -f .env || true
  if [ -e .env ]; then
    CLEANUP_LEFT=1
    info "警告: .env を削除できませんでした（$APP_DIR/.env を手動で削除してください）" || true
  fi
  # 残存があるのに 0 で終わらない（次回実行が初回ガードで止まる状態を成功と偽らないため）。
  #   既に非 0（1/2/129/130/143）ならその値を保つ — 中断や失敗の原因の方が情報量が多い。
  if [ "$_rc" -eq 0 ] && [ "$CLEANUP_LEFT" = "1" ]; then _rc=1; fi
  # 出力先が先に閉じていると echo が失敗し、set -e で終了コードが 1 に化けるため無視する。
  info || true
  info "終了コード: $_rc" || true
  exit "$_rc"
}
trap on_exit EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

# ── .env の生成と compose 設定の検証 ─────────────────────────────────────────────────────────────────────
# メールアドレスは .env に書かない。
printf 'DOMAIN=%s\nOWNER=%s\n' "$DOMAIN" "$OWNER" > .env
info ".env を生成しました（DOMAIN / OWNER）"

# compose 設定を検証（export した APP_IMAGE/PROXY_IMAGE と生成 .env の DOMAIN で通る）。
docker compose config >/dev/null || die "docker compose config に失敗（docker-compose.yml の記述エラー / 上記エラーを確認）"
info "compose 設定 OK"

# ── コンテナ列挙ヘルパ（関数定義）─────────────────────────────────────────────────────────────────────────
# 本プロジェクトのコンテナ ID を列挙する（引数に -a を渡すと停止済みも含む）。後始末の残存確認で使う。
ours_containers() {
  docker ps "$@" --filter "label=com.docker.compose.project.working_dir=$APP_DIR" \
    --format '{{.ID}}' 2>/dev/null || true
}

# 本プロジェクトのコンテナのうち 80番をホストに公開しているものの ID を列挙する
#   （compose down 後の取りこぼしの特定と、rm -f 後の解放確認で使う）。
ours_on_80() {
  docker ps --filter "label=com.docker.compose.project.working_dir=$APP_DIR" \
    --format '{{.ID}}|{{.Ports}}' 2>/dev/null | grep ':80->' | awk -F'|' '{print $1}' || true
}

# ── 80番の確保（自プロジェクトの残骸は停止し、他が握っていれば中断）──────────────────────────────────────────
# 検知は docker ps（ホスト公開ポート）＋ ss（非 Docker）で、1 回の docker ps 出力を
#   '|' 区切りにして全体（holders）と自プロジェクト分（our_ids）の 2 通りに絞る。
#   本プロジェクトの残骸だけ down し、他プロジェクト/素コンテナ/非 Docker プロセスは情報を出して中断する。
ports80="$(docker ps --format '{{.ID}}|{{.Ports}}|{{.Label "com.docker.compose.project.working_dir"}}' 2>/dev/null \
             | grep ':80->' || true)"
holders="$(printf '%s\n' "$ports80" | awk -F'|' 'NF > 1 {print $1}')"
our_ids="$(printf '%s\n' "$ports80" | awk -F'|' -v d="$APP_DIR" '$3 == d {print $1}')"
listen80="$(ss -ltn 2>/dev/null | grep ':80 ' || true)"
if [ -z "$holders" ] && [ -z "$listen80" ]; then
  info "80番は空き OK"
elif [ -n "$our_ids" ]; then
  info "80番は本プロジェクトの残存コンテナが使用中のため停止します ..."
  docker compose down --remove-orphans >/dev/null 2>&1 || true
  # compose down が空振りしても確実に空けるため、残っていれば ID を直接落とす。
  remaining_ids="$(ours_on_80)"
  # shellcheck disable=SC2086
  [ -n "$remaining_ids" ] && docker rm -f $remaining_ids >/dev/null 2>&1 || true
  # down も rm -f も失敗を握り潰しているため、空いたことをここで確認する。
  #   見逃すと 80番を塞いだまま進み、ACME チャレンジの失敗として初めて表面化する。
  remaining_ids="$(ours_on_80)"
  if [ -n "$remaining_ids" ]; then
    info "  停止できずに残っているコンテナ:"
    # shellcheck disable=SC2086
    docker inspect --format '    {{.Name}}' $remaining_ids 2>/dev/null || true
    info "  解放するには: docker rm -f <上記コンテナ名>"
    die "本プロジェクトの残存コンテナを停止できませんでした（80番は使用中のまま）
     上記コンテナを停止してから再実行してください"
  fi
  info "本プロジェクトのスタックを停止しました（続行）"
elif [ -n "$holders" ]; then
  info "  80番を他の Docker コンテナが使用中です:"
  # shellcheck disable=SC2086
  docker inspect --format '    {{.Name}}  (project: {{index .Config.Labels "com.docker.compose.project"}})' \
    $holders 2>/dev/null || true
  info "  解放するには: docker stop <上記コンテナ名>"
  die "80番が使用中です（他の Docker コンテナ）
     上記コンテナを停止してから再実行してください"
else
  info "  80番を Docker 以外のプロセスが使用中です:"
  ss -ltnp 2>/dev/null | grep ':80 ' | sed 's/^/    /' || true
  info "  正体確認: sudo ss -ltnp | grep ':80 '   （root で実行するとプロセス名/PID が出ます）"
  die "80番が使用中です（Docker 以外のプロセス）
     停止してから再実行してください"
fi

# ── 証明書の削除（関数定義）──────────────────────────────────────────────────────────────────────────────
#   certbot が archive/ renewal/ を root 所有で書くため、非 root の実行ユーザーでは中身を unlink できない。
#   そのため削除も同じくコンテナ内 root で行う。
#   （ダミー証明書は実行ユーザー所有だが、経路を1本にするため通常はこの関数で消す）。
#   削除後に必ず残存を確認する。見逃すと certbot が live/<ドメイン>-0001 を作り、nginx は
#   古い証明書を参照し続けるため。残っていれば 1 を返すので、呼び出し側は必ず結果を扱うこと。
MSG_CERT_LEFT="証明書ファイル（live / archive / renewal）を削除できませんでした（$CERTBOT_DIR/conf を手動で整理してから再実行してください）"
remove_cert() {
  local _p
  docker compose run --rm --entrypoint sh cert -c \
    "rm -rf /etc/letsencrypt/live/$DOMAIN \
            /etc/letsencrypt/archive/$DOMAIN \
            /etc/letsencrypt/renewal/$DOMAIN.conf" >/dev/null 2>&1 || true
  # 親ディレクトリは全て他ユーザーから辿れる（0755）ため、非 root でも残存は判定できる。
  for _p in "live/$DOMAIN" "archive/$DOMAIN" "renewal/$DOMAIN.conf"; do
    if [ -e "$CERTBOT_DIR/conf/$_p" ]; then
      info "  削除できずに残っています: $CERTBOT_DIR/conf/$_p"
      return 1
    fi
  done
}

# ── 証明書取得（関数定義: ダミー作成 → proxy 起動 → ダミー削除 → 本物取得 → リロード）────────────────────────
#   引数: $1 = staging フラグ（1=ステージング, 0=本番）
#   ※ ダミーを proxy 起動より前に作るので、proxy が証明書なしで起動する瞬間がなくクラッシュしない。
obtain_cert() {
  local staging="$1"
  local staging_arg=""
  if [ "$staging" = "1" ]; then staging_arg="--staging"; fi
  local live_dir="$CERTBOT_DIR/conf/live/$DOMAIN"

  info "ダミー証明書を作成（$DOMAIN）..."
  mkdir -p "$live_dir"
  CERT_STATE=dummy   # openssl の鍵生成中に中断されても live/ を回収できるよう、作成を始める前に立てる
  # 失敗をそのまま set -e に任せると、作ったばかりの live/<ドメイン> が残って次回実行が guard で止まる。
  #   このディレクトリに certbot はまだ触れておらず（本番の回も直前に remove_cert が消している）、
  #   mkdir -p も openssl も実行ユーザーとして走るため、ホスト側から消せる。
  if ! openssl req -x509 -nodes -newkey "rsa:$DUMMY_KEY_BITS" -days 1 \
    -keyout "$live_dir/privkey.pem" \
    -out    "$live_dir/fullchain.pem" \
    -subj "/CN=localhost" >/dev/null; then
    rm -rf "$live_dir"
    CERT_STATE=none   # 自前で消したのでトラップの担当から外す
    die "ダミー証明書の作成に失敗（上記の openssl のエラーを確認してください）"
  fi

  # proxy 起動（ダミーで起動し、80番で ACME チャレンジを受けられる状態に）。
  info "proxy を起動 ..."
  # 起動失敗時：まだ本物取得前なので、ダミー証明書を消してから中断する。
  #   STACK_UP は up の前に立てる（depends_on で app も起動するため、途中失敗でも残骸を停止できるように）。
  STACK_UP=1
  if ! docker compose up --force-recreate -d proxy; then
    local cleaned="ダミー証明書は削除しました"
    remove_cert || cleaned="ダミー証明書も削除できませんでした"
    CERT_STATE=none   # 結果はここで報告済み（成功・失敗を問わずトラップの担当から外す）
    die "proxy の起動に失敗（$cleaned）
     $(hint_log proxy)"
  fi

  info "ダミー証明書を削除 ..."
  remove_cert || { CERT_STATE=none; die "$MSG_CERT_LEFT"; }
  CERT_STATE=none

  local email_arg="--register-unsafely-without-email"
  [ -n "$EMAIL" ] && email_arg="--email $EMAIL"

  # cert の entrypoint は更新ループに上書き済みのため、一回限りの certonly は --entrypoint certbot で既定に戻す。
  #   -n: 想定外のプロンプトで止まらず即失敗させる（run は TTY を割り当てるため）。
  info "Let's Encrypt から証明書を取得 ..."
  # 実行中に中断された場合に備えて、取得を始める前にどちらの証明書を作っているかを立てる。
  if [ "$staging" = "1" ]; then CERT_STATE=staging; else CERT_STATE=production; fi
  # shellcheck disable=SC2086
  if ! docker compose run --rm --entrypoint certbot cert certonly \
    --webroot -w /var/www/certbot \
    -n \
    $staging_arg \
    $email_arg \
    -d "$DOMAIN" \
    --agree-tos \
    --no-eff-email \
    --force-renewal; then
    # ステージングは使い捨てなので、certbot が書いた可能性のあるファイルを残さず消す。
    if [ "$staging" = "1" ]; then
      local cleaned="証明書ファイル（live / archive / renewal）は残っていません"
      remove_cert || cleaned="$MSG_CERT_LEFT"
      CERT_STATE=none
      die "証明書の取得に失敗（DNS / 80番の到達性 / レート制限 / 上記のエラーを確認）
     $cleaned"
    fi
    # 本番は CERT_STATE=production のまま die する（certbot が発行を終えてから失敗した可能性があり、
    #   消すと重複証明書のレート制限だけを消費するため）。保持と手動確認の案内はトラップが出す。
    die "証明書の取得に失敗（DNS / 80番の到達性 / レート制限 / 上記のエラーを確認）"
  fi

  info "proxy をリロード ..."
  # リロード失敗時：ステージングは使い捨てなので消して再実行を guard で止めないようにする。
  #   本番証明書は貴重・レート制限のため消さず残す（手動で調査）。
  if ! docker compose exec proxy nginx -s reload; then
    if [ "$staging" = "1" ]; then
      local cleaned="ステージング証明書は削除しました"
      remove_cert || cleaned="$MSG_CERT_LEFT"
      CERT_STATE=none
      die "proxy のリロードに失敗（$cleaned）
     $(hint_log proxy)"
    fi
    # 本番証明書の保持と手動確認の案内はトラップが出す（ここで重ねて書かない）。
    die "proxy のリロードに失敗
     $(hint_log proxy)"
  fi
}

# ── イメージの取得（cert / proxy を使う以降の処理の前提）───────────────────────────────────────────────────
docker compose pull || die "docker compose pull に失敗（GHCR 未ログイン / OWNER 名の誤り / イメージ未 push を確認）"

# ── ステージングで取得（本番前の試行）─────────────────────────────────────────────────────────────────────
info "ステージングで証明書取得を試行 ..."
obtain_cert 1
info "ステージング証明書を取得しました"
info

# ── ステージング結果を見てから本番へ進むか確認 ─────────────────────────────────────────────────────────────
if confirm "本番証明書を取得しますか？"; then
  info
else
  info
  info "本番証明書の取得を中止します ..."
  exit 0
fi

# ── 本番証明書に切り替えて取得 ───────────────────────────────────────────────────────────────────────────
info "ステージング証明書を削除し、本番証明書を取得 ..."
# 成功・失敗を問わず担当から外す（失敗は die が報告済みで、トラップが再試行しても同じく失敗するだけ）。
remove_cert || { CERT_STATE=none; die "$MSG_CERT_LEFT"; }
CERT_STATE=none
obtain_cert 0
info "本番証明書を取得しました"

# ── 検証（発行者が STAGING/Fake でないこと）──────────────────────────────────────────────────────────────
info "発行者（issuer）を検証 ..."
CERT="$CERTBOT_DIR/conf/live/$DOMAIN/fullchain.pem"
[ -f "$CERT" ] || die "証明書が見つかりません: $CERT"
ISSUER="$(openssl x509 -in "$CERT" -noout -issuer)"
ENDDATE="$(openssl x509 -in "$CERT" -noout -enddate)"
info "  $ISSUER"
info "  有効期限: ${ENDDATE#notAfter=}"
if echo "$ISSUER" | grep -qiE 'staging|fake'; then
  CERT_STATE=staging   # 本番証明書でないと検査で確定したので、トラップが削除してよい
  die "まだステージング証明書です（発行者に staging/fake）
     上記の発行者を確認のうえ再実行してください"
fi
info "  発行者 OK（staging/fake でない）"
CERT_STATE=verified    # 以降はどこで失敗しても証明書・コンテナを残す

# ── 全サービス起動と proxy の起動確認 ────────────────────────────────────────────────────────────────────
info "全サービスを起動（docker compose up -d）..."
docker compose up -d
sleep "$START_WAIT"

# proxy が起動しているか（証明書を読めずクラッシュループ等になっていないか）。
#   compose ps の表示文字列ではなく、docker ps の State を直接見る（表示揺れに依存させない）。
#   State が取れない場合は止めない（ラベル不一致のことがあり、正常な環境を誤って中断するより後続の動作確認に委ねる）。
proxy_state="$(docker ps -a --filter "label=com.docker.compose.project.working_dir=$APP_DIR" \
                 --filter "label=com.docker.compose.service=proxy" \
                 --format '{{.State}}' 2>/dev/null | head -1 || true)"
case "$proxy_state" in
  running)    info "  proxy OK（State=running）" ;;
  "")         info "  proxy の State を取得できませんでした（後続の動作確認で判断します）" ;;
  restarting) die "proxy が Restarting です
     $(hint_log proxy)" ;;
  *)          die "proxy が起動していません（State=$proxy_state）
     $(hint_log proxy)" ;;
esac

# ── ローカル動作確認（HTTPS 200 / HTTP 301）──────────────────────────────────────────────────────────────
# ローカルから実ホスト名の vhost をテスト（--resolve で 127.0.0.1 へ向けるので、EC2 が自分の外部IPに回り込めなくても確認できる）。
#   起動直後の一過性を吸収するため、期待コードになるまで数回リトライする。
probe() {  # $1=ポート $2=スキーム → 200/301 になれば即返す
  local code=000 i
  for i in $(seq 1 "$PROBE_RETRIES"); do
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time "$PROBE_TIMEOUT" \
            --resolve "$DOMAIN:$1:127.0.0.1" "$2://$DOMAIN/" || true)"
    case "$code" in 200|301) break ;; esac
    [ "$i" -lt "$PROBE_RETRIES" ] && sleep "$PROBE_INTERVAL"   # 最終試行の後は待たない
  done
  echo "$code"
}

info "ローカル動作確認 ..."
CODE_HTTPS="$(probe 443 https)"
CODE_HTTP="$(probe 80 http)"
verify_ng=0
if [ "$CODE_HTTPS" = "200" ]; then
  info "  HTTPS(443) -> $CODE_HTTPS OK （期待: 200）"
else
  info "  HTTPS(443) -> $CODE_HTTPS NG （期待: 200）"
  verify_ng=1
fi
if [ "$CODE_HTTP" = "301" ]; then
  info "  HTTP(80)   -> $CODE_HTTP OK （期待: 301）"
else
  info "  HTTP(80)   -> $CODE_HTTP NG （期待: 301）"
  info "    nginx 設定を確認: 生成元はリポジトリの proxy/nginx.conf.template / 環境変数 DOMAIN / 稼働中はコンテナ内 /etc/nginx/nginx.conf"; verify_ng=1
fi

# ── 結果表示と終了コード ─────────────────────────────────────────────────────────────────────────────────
info
if [ "$verify_ng" -eq 0 ]; then
  info "セットアップ完了です"
else
  info "証明書の取得と docker compose up -d は完了しましたが、上記の動作確認に失敗があります"
  info "  $(hint_log proxy)"
  info "  $(hint_log app)"
fi
info "  外部からの最終確認は手元の PC から: curl -I https://$DOMAIN/  （200 が返れば OK）"
info "  ブラウザで https://$DOMAIN を開き、鍵マークが出れば完了です"

# 動作確認の失敗は die の 1 と区別して 2 で終わる（証明書は取得済みで、配信だけが疑わしい状態）。
[ "$verify_ng" -eq 0 ] || exit 2
exit 0
