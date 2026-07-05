"""
日数計算機 (DateCalc.py)

入力した日付と今日の差を日数で求める計算エンジン。Web アプリ（DateCalc_server.py 経由の /api/*）から利用される。

主な特徴:
  - 紀元前（負の年）に対応。日付計算はすべて先発グレゴリオ暦（proleptic Gregorian calendar）で行う。
  - 利用者が入出力で使うのは「歴史年代」（…紀元前2年, 紀元前1年, 西暦1年… と 0 年が無い体系）。
    内部では計算しやすい連続値の「天文年代」（…-1, 0, 1, …）に変換して扱う。
  - 西暦1年以降は標準の datetime.date を使い、それ以前（天文年0以下）は date が非対応のため、
    通日(ordinal)だけを保持する自前の _ProlepticDate で補う。
"""

from datetime import date, datetime, timedelta, timezone

# ── 定数 ──────────────────────────────────────────────────────────────────────
# date.weekday() は 月曜=0 … 日曜=6 を返すので、その並びに合わせて漢字を並べる
WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]
# 日本標準時（UTC+9）
JST = timezone(timedelta(hours=9))


# ── ユーティリティ ────────────────────────────────────────────────────────────
def get_today() -> date:
    """今日の日付を日本標準時で返す。"""
    return datetime.now(JST).date()


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
    """年を表示用の文字列にする（紀元前は「BCN」、西暦はそのまま）。"""
    return f"BC{abs(year)}" if year < 0 else str(year)


# ── メインロジック ────────────────────────────────────────────────────────────
def calculate(year: int, month: int, day: int, today: date) -> dict:
    """日付を検証し、今日との差分情報をまとめた辞書を返す。

    成功時の辞書:
        ok         : True
        date_label : 表示用の日付（例: "2030年3月15日 (金)"）
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
    date_label = f"{year_label}年{month}月{day}日 ({weekday})"

    cls = "today" if diff == 0 else ("future" if diff > 0 else "past")

    # describe_diff には両日付を (天文年, 月, 日, 通日) の形で渡す
    target_parts = (astro_year, month, day, target_ord)
    today_parts = (today.year, today.month, today.day, today.toordinal())
    diff_label = describe_diff(diff, target_parts, today_parts)

    return {
        "ok": True,
        "date_label": date_label,
        "diff": diff,          # 公開API用の符号付き日数（HTMLは未使用だが契約として返す）
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
