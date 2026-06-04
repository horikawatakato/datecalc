"""
日数計算機 (DateCalc.py)

入力した日付と「今日」の差を日数で求め、人間に読みやすい形（例:「1380日後 / 3年284日後」）で
表示する対話型 CLI ツール。計算結果は最新順に最大 MAX_HISTORY 件まで履歴として保持する。

主な特徴:
  - 紀元前（負の年）に対応。日付計算はすべて先発グレゴリオ暦（proleptic Gregorian calendar）で行う。
  - 利用者が入出力で使うのは「歴史年代」（…紀元前2年, 紀元前1年, 西暦1年… と 0 年が無い体系）。
    内部では計算しやすい連続値の「天文年代」（…-1, 0, 1, …）に変換して扱う。
  - 西暦1年以降は標準の datetime.date を使い、それ以前（天文年0以下）は date が非対応のため、
    通日(ordinal)だけを保持する自前の _ProlepticDate で補う。
"""

from datetime import date, timedelta
import re

# ── 定数 ──────────────────────────────────────────────────────────────────────
# date.weekday() は 月曜=0 … 日曜=6 を返すので、その並びに合わせて漢字を並べる
WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]
# 履歴として保持する最大件数
MAX_HISTORY = 8


# ── ユーティリティ ────────────────────────────────────────────────────────────
def get_weekday(d: date) -> str:
    """date の曜日を漢字1文字（月〜日）で返す。"""
    return WEEKDAYS[d.weekday()]


def is_valid_date(hist_year: int, month: int, day: int) -> bool:
    """暦上に実在する日付かを検証する。

    hist_year は歴史年代（紀元前=負）。歴史年代に 0 年は無いため 0 は不正とする。
    閏年判定は天文年代へ直してから行い、紀元前の 2月29日 も正しく扱う。
    """
    if hist_year == 0:                      # 歴史年代に 0 年は存在しない
        return False
    if not (1 <= month <= 12):
        return False
    max_day = DAYS_IN_MONTH[month]          # その月の日数（平年）
    astro = historical_to_proleptic(hist_year)
    if month == 2 and _is_leap(astro):      # 閏年の2月だけ29日まで許可
        max_day = 29
    return 1 <= day <= max_day


def historical_to_proleptic(year: int) -> int:
    """歴史年代を連続値の天文年代へ変換する。

    歴史年代は 紀元前1年 の次が 西暦1年 で 0 年を飛ばすため、紀元前側を1つ繰り上げて
    連続値にする（紀元前1年→0、紀元前2年→-1）。西暦（正の年）はそのまま返す。
    """
    return year + 1 if year < 0 else year


def diff_days(target: "date | _ProlepticDate", today: date) -> int:
    """target と today の差を日数で返す（未来=正、過去=負）。

    target は date でも _ProlepticDate でもよい（どちらも today との減算が定義済み）。
    """
    return (target - today).days


def describe_diff(diff: int, target: tuple, today: tuple) -> str:
    """日数差を人間が読みやすい文字列へ整形する。

    target / today はそれぞれ (天文年, 月, 日, 通日ordinal) の4要素タプル。
    表示ルール:
        差が 0    → 「今日」
        365日未満 → 「N日後」「N日前」
        365日以上 → 「N日後 / Y年D日後」（暦上の年数 Y と端数日 D を併記）
    閏日をまたぐ等で総日数が365日でも暦の上で1年未満になる場合は、日数のみ表示する。
    """
    if diff == 0:
        return "今日"

    abs_diff = abs(diff)
    suffix = "後" if diff > 0 else "前"

    if abs_diff < 365:
        return f"{abs_diff}日{suffix}"

    # 過去・未来どちらでも「古い側(from) → 新しい側(to)」に並べ替えてから年数を数える
    from_p, to_p = (today, target) if diff > 0 else (target, today)
    fay, fm, fd, _ = from_p      # from（古い側）の 年・月・日
    tay, _, _, tord = to_p       # to （新しい側）の 年・通日

    # まず単純な年差を仮に置き、記念日が新しい側を追い越していたら1年戻す
    years = tay - fay
    anniv_ord = _anniversary_ordinal(fay, fm, fd, years)
    if anniv_ord > tord:
        years -= 1
        anniv_ord = _anniversary_ordinal(fay, fm, fd, years)

    # 暦の上で1年未満（閏日をまたぐ365日ちょうど等）は日数のみ表示
    if years == 0:
        return f"{abs_diff}日{suffix}"

    remain_days = tord - anniv_ord   # 直近の記念日からの端数日数

    year_part = f"{years}年"
    day_part = f"{remain_days}日" if remain_days > 0 else ""
    return f"{abs_diff}日{suffix} / {year_part}{day_part}{suffix}"


def format_year_label(year: int) -> str:
    """年を表示用の文字列にする（紀元前は「紀元前N」、西暦はそのまま）。"""
    return f"紀元前{abs(year)}" if year < 0 else str(year)


# ── 入力バリデーション ────────────────────────────────────────────────────────
def parse_year(s: str) -> int | None:
    """年の入力文字列を整数に変換する。妥当でなければ None。

    受け付けるのは符号付き整数のみで、許容範囲は -999〜-1 と 1〜9999。
    正規表現が先頭桁を 1-9 に限定するため「0」「01」「-0」などは弾かれる。
    """
    s = s.strip()
    if not re.fullmatch(r'-?[1-9]\d*', s):
        return None
    val = int(s)
    if val > 9999 or val < -999:
        return None
    return val


def parse_month_or_day(s: str, min_val: int, max_val: int) -> int | None:
    """月または日の入力文字列を整数に変換する。妥当でなければ None。

    ここでは「正の整数で min_val〜max_val に収まるか」という大まかな確認だけを行う。
    月が12を超える・日が月末を超える等の暦上の正確な妥当性は is_valid_date が最終判定する。
    """
    s = s.strip()
    if not re.fullmatch(r'[1-9]\d*', s):
        return None
    val = int(s)
    if val < min_val or val > max_val:
        return None
    return val


# ── メインロジック ────────────────────────────────────────────────────────────
def calculate(year: int, month: int, day: int, today: date) -> dict:
    """日付を検証し、今日との差分情報をまとめた辞書を返す。

    成功時の辞書:
        ok         : True
        date_label : 表示用の日付（例: "2030年3月15日(金)"）
        diff       : 今日との差（日数。未来=正、過去=負）
        diff_label : 差を整形した文字列（例: "1380日後 / 3年284日後"）
        cls        : "today" | "future" | "past"
    失敗時は {"ok": False, "error": ...} を返す。
    """
    if not is_valid_date(year, month, day):
        return {"ok": False, "error": "この日付は存在しません"}

    astro_year = historical_to_proleptic(year)

    # 西暦1年以降は標準の date、それ以前(天文年0以下)は date が非対応なので _ProlepticDate を使う
    if astro_year >= 1:
        target = date(astro_year, month, day)
        weekday = get_weekday(target)
        target_ord = target.toordinal()
    else:
        target = _proleptic_date(astro_year, month, day)
        weekday = _weekday_proleptic(target)
        target_ord = target.ordinal

    diff = diff_days(target, today)
    year_label = format_year_label(year)
    date_label = f"{year_label}年{month}月{day}日({weekday})"

    cls = "today" if diff == 0 else ("future" if diff > 0 else "past")

    # describe_diff には両日付を (天文年, 月, 日, 通日) の形で渡す
    target_parts = (astro_year, month, day, target_ord)
    today_parts = (today.year, today.month, today.day, today.toordinal())
    diff_label = describe_diff(diff, target_parts, today_parts)

    return {
        "ok": True,
        "date_label": date_label,
        "diff": diff,          # 公開API(/api/calculate)用の符号付き日数。CLI・同梱HTMLは未使用だが契約として返す
        "diff_label": diff_label,
        "cls": cls,
    }


# ── 紀元前対応ヘルパー ─────────────────────────────────────────────────────────
class _ProlepticDate:
    """datetime.date が扱えない天文年代0以下の日付を表す軽量クラス。

    日付の実体は持たず、先発グレゴリオ暦の通日（ordinal, date(1,1,1)=1）だけを保持する。
    today（date）との差さえ取れればよいので、引き算 __sub__ のみを実装する。
    """
    def __init__(self, ordinal: int):
        self.ordinal = ordinal

    def __sub__(self, other):
        # _ProlepticDate - date → 通日同士の差。today は常に date 側に来る
        if isinstance(other, date):
            return timedelta(days=self.ordinal - other.toordinal())
        return NotImplemented


def _is_leap(year: int) -> bool:
    """閏年か（先発グレゴリオ暦・天文年代）。4の倍数かつ100の倍数でない、または400の倍数なら閏年。"""
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


# 各月の日数（添字 1〜12 を使う。先頭の 0 は1始まりにするためのダミー。2月は平年値28）
DAYS_IN_MONTH = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _days_in_year(year: int) -> int:
    """その年の日数（閏年=366、平年=365）。"""
    return 366 if _is_leap(year) else 365


def _proleptic_ordinal(astro_year: int, month: int, day: int) -> int:
    """日付を先発グレゴリオ暦の通日（ordinal, date(1,1,1)=1）へ変換する。

    天文年1以上は date.toordinal() に任せる。0 以下は date が非対応のため、
    対象年の元日の通日を年の累積から求め、月初までの日数と日を足して算出する。
    """
    if astro_year >= 1:
        return date(astro_year, month, day).toordinal()

    # 元日(1月1日)の通日 = 1 から、対象年〜0年ぶんの日数をさかのぼって引く
    jan1_ordinal = 1 - sum(_days_in_year(y) for y in range(astro_year, 1))
    # 1月から (month-1)月 までの日数合計（閏年の2月は +1）
    days_before_month = sum(
        DAYS_IN_MONTH[m] + (1 if m == 2 and _is_leap(astro_year) else 0)
        for m in range(1, month)
    )
    return jan1_ordinal + days_before_month + (day - 1)


def _anniversary_ordinal(astro_year: int, month: int, day: int, years: int) -> int:
    """基準日 (astro_year, month, day) の years 年後の記念日を通日で返す。

    対象年が平年で 2月29日 が無い場合は 3月1日 に丸める（年数計算を破綻させないため）。
    """
    target_year = astro_year + years
    if month == 2 and day == 29 and not _is_leap(target_year):  # 平年なら 2/29 → 3/1
        return _proleptic_ordinal(target_year, 3, 1)
    return _proleptic_ordinal(target_year, month, day)


def _proleptic_date(astro_year: int, month: int, day: int):
    """天文年代0以下の日付を _ProlepticDate（通日を保持）にして返す。"""
    return _ProlepticDate(_proleptic_ordinal(astro_year, month, day))


def _weekday_proleptic(target: _ProlepticDate) -> str:
    """_ProlepticDate の曜日を返す。通日1 = date(1,1,1) = 月曜 を基準に、7 で割った余りで求める。"""
    return WEEKDAYS[(target.ordinal - 1) % 7]


# ── CLIインターフェース ────────────────────────────────────────────────────────
def print_result(result: dict) -> None:
    """計算結果をコンソールに表示する。"""
    if not result["ok"]:
        print(f"  エラー: {result['error']}")
        return

    cls_label = {"today": "今日", "future": "未来", "past": "過去"}.get(result["cls"], "")
    print(f"  {result['date_label']}")
    print(f"  {result['diff_label']}  [{cls_label}]")


def print_history(history: list) -> None:
    """履歴をコンソールに表示する。"""
    if not history:
        print("  (履歴なし)")
        return
    for i, h in enumerate(history, 1):
        print(f"  {i}. {h['date_label']}  →  {h['diff_label']}")


def main() -> None:
    """対話ループ本体。日付入力のほか h=履歴 / c=履歴クリア / q=終了 を受け付ける。"""
    today = date.today()
    weekday_today = get_weekday(today)
    print("日数計算機")
    print(f"今日 — {today.year}年{today.month}月{today.day}日({weekday_today})")
    print("=" * 40)
    print("コマンド: 日付入力（例: 2030 3 15）/ h=履歴 / c=履歴クリア / q=終了")
    print()

    history: list = []

    while True:
        try:
            raw = input("日付を入力（年 月 日）> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n終了します。")
            break

        if raw in ("q", "quit", "exit"):
            print("終了します。")
            break

        if raw in ("h", "history"):
            print_history(history)
            continue

        if raw in ("c", "clear"):
            history.clear()
            print("  履歴をクリアしました。")
            continue

        parts = raw.split()
        if len(parts) != 3:
            print("  入力形式が正しくありません。「年 月 日」の順に半角スペース区切りで入力してください。")
            print("  例: 2030 3 15  /  -100 1 1（紀元前100年1月1日）")
            continue

        year = parse_year(parts[0])
        if year is None:
            print("  年の入力が正しくありません。-999〜-1 または 1〜9999 の整数を入力してください（0は不可）。")
            continue

        month = parse_month_or_day(parts[1], 1, 99)
        if month is None:
            print("  月の入力が正しくありません。1〜12 の整数を入力してください。")
            continue

        day = parse_month_or_day(parts[2], 1, 99)
        if day is None:
            print("  日の入力が正しくありません。1〜31 の整数を入力してください。")
            continue

        result = calculate(year, month, day, today)
        print_result(result)

        if result["ok"]:
            # 同じ日付は重複させず先頭へ移動。最新順に MAX_HISTORY 件で打ち切る
            history = [result] + [h for h in history if h["date_label"] != result["date_label"]]
            history = history[:MAX_HISTORY]

        print()


if __name__ == "__main__":
    main()
