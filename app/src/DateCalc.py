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
from typing import NamedTuple

# ── 定数 ──────────────────────────────────────────────────────────────────────
# date.weekday() は 月曜=0 … 日曜=6 を返すので、その並びに合わせて漢字を並べる
WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]
# 日本標準時（UTC+9）
JST = timezone(timedelta(hours=9))

# サポートする歴史年代の範囲。ここが仕様の唯一の基準（HTML 側の入力制限もエラーメッセージも同じ値）。
# 上限は datetime.date が扱える年の上限。これを外すと calculate が date(10000, ...) を組む段で
# ValueError を投げて HTTP 500 になるため、範囲チェックが date() 前の防波堤になっている。
# 下限は紀元前をどこまで遡るかという仕様上の取り決め（通日計算は O(1) なので性能上の制約ではない）。
MIN_HIST_YEAR = -999   # 紀元前999年
MAX_HIST_YEAR = 9999   # 西暦9999年

# 「暦年に満たないか」を日数だけで表示するかどうかの閾値。
# （365日ちょうどでも閏日をまたげば暦の上では1年未満になりうる。その判定は describe_diff が持つ）
DAYS_PER_YEAR = 365

# 各月の日数（添字 1〜12 を使う。先頭の 0 は1始まりにするためのダミー。2月は平年値28）
DAYS_IN_MONTH = (0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


# ── ユーティリティ ────────────────────────────────────────────────────────────
def get_today() -> date:
    """今日の日付を日本標準時で返す。

    ホストの TZ 設定に左右されないよう、date.today() ではなく固定オフセットの JST を使う。
    """
    return datetime.now(JST).date()


def get_weekday(d: "date | _ProlepticDate") -> str:
    """日付の曜日を漢字1文字（月〜日）で返す。weekday() を持つ型ならどちらでもよい。"""
    return WEEKDAYS[d.weekday()]


def is_valid_date(hist_year: int, month: int, day: int) -> bool:
    """暦上に実在する日付かを検証する。

    hist_year は歴史年代（紀元前=負）。歴史年代に 0 年は無いため 0 は不正とする。
    閏年判定は天文年代へ直してから行い、紀元前の 2月29日 も正しく扱う。

    ここでは年の対応範囲（MIN/MAX_HIST_YEAR）は検証しない。「暦上実在するか」と
    「対応範囲内か」は別の関心事で、範囲保証は呼び出し側（calculate）の責務。
    """
    if hist_year == 0:
        return False
    if not (1 <= month <= 12):
        return False
    astro_year = historical_to_proleptic(hist_year)
    return 1 <= day <= _days_in_month(astro_year, month)


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


class DateParts(NamedTuple):
    """describe_diff に渡す日付の内訳。"""
    astro_year: int   # 天文年代
    month: int
    day: int
    ordinal: int      # 先発グレゴリオ暦の通日


def describe_diff(diff: int, target: DateParts, today: DateParts) -> str:
    """日数差を人間が読みやすい文字列へ整形する。

    表示ルール:
        差が 0    → 「今日」
        365日未満 → 「N日後」「N日前」
        365日以上 → 「N日後 / Y年D日後」（暦上の年数 Y と端数日 D を併記）
    ただし 365日以上でも暦の上で1年未満なら（閏日をまたぐ365日ちょうど等）日数のみ表示する。
    年数の記念日は、起点が 2月29日 で対象年が平年のときはその月の末日（2/28）に丸める。
    """
    if diff == 0:
        return "今日"

    abs_diff = abs(diff)
    suffix = "後" if diff > 0 else "前"

    if abs_diff < DAYS_PER_YEAR:
        return f"{abs_diff}日{suffix}"

    # 過去・未来どちらでも「古い側(from) → 新しい側(to)」に並べ替えてから年数を数える
    from_p, to_p = (today, target) if diff > 0 else (target, today)

    # 年差の補正は高々1回で足りる（理由↓）。
    # まず単純な年差を仮に置き、記念日が新しい側を追い越していたら1年戻す。
    # from≤to かつ years=年差なので anniversary(years) は to と同一暦年に入り、
    # 追い越していても anniversary(years-1) は前年=確実に to 以前になるため。
    years = to_p.astro_year - from_p.astro_year
    anniv_ord = _anniversary_ordinal(from_p.astro_year, from_p.month, from_p.day, years)
    if anniv_ord > to_p.ordinal:
        years -= 1
        anniv_ord = _anniversary_ordinal(from_p.astro_year, from_p.month, from_p.day, years)

    # 暦の上で1年未満（閏日をまたぐ365日ちょうど等）は日数のみ表示
    if years == 0:
        return f"{abs_diff}日{suffix}"

    remain_days = to_p.ordinal - anniv_ord   # 直近の記念日からの端数日数

    year_part = f"{years}年"
    day_part = f"{remain_days}日" if remain_days > 0 else ""
    return f"{abs_diff}日{suffix} / {year_part}{day_part}{suffix}"


def format_year_label(year: int) -> str:
    """年を表示用の文字列にする（紀元前は「BC」+数字、例: -100 → "BC100"。西暦はそのまま）。"""
    return f"BC{abs(year)}" if year < 0 else str(year)


# ── メインロジック ────────────────────────────────────────────────────────────
def calculate(year: int, month: int, day: int, today: date) -> dict:
    """日付を検証し、今日との差分情報をまとめた辞書を返す。

    year / month / day は int 前提（呼び出し側で整数化・数値検証を済ませること）。
    float / str などが来た場合の挙動は未定義（date() が TypeError を投げうる）。
    本番の唯一の呼び出し元 DateCalc_server.api_calculate は int() でキャストし非整数は 400 にする。

    成功時の辞書:
        ok         : True
        date_label : 表示用の日付（例: "2030年3月15日 (金)"）
        diff       : 今日との差（日数。未来=正、過去=負）
        diff_label : 差を整形した文字列（例: "1380日後 / 3年284日後"）
        cls        : "today" | "future" | "past"
    失敗時は {"ok": False, "error": ...} を返す。
    """
    # 対応範囲チェックは is_valid_date とは別の関心事（is_valid_date の docstring 参照）。先に見る
    if not (MIN_HIST_YEAR <= year <= MAX_HIST_YEAR):
        # メッセージも定数から組み立てる（範囲を変えたときに文言だけ古くならないように）
        return {
            "ok": False,
            "error": f"対応範囲は紀元前{abs(MIN_HIST_YEAR)}年〜西暦{MAX_HIST_YEAR}年です",
        }

    if not is_valid_date(year, month, day):
        return {"ok": False, "error": "この日付は存在しません"}

    astro_year = historical_to_proleptic(year)

    # 西暦1年以降は標準の date、それ以前(天文年0以下)は date が非対応なので _ProlepticDate を使う。
    # どちらも weekday() / toordinal() を持つので、以降は同じ扱いでよい
    if astro_year >= 1:
        target = date(astro_year, month, day)
    else:
        target = _ProlepticDate(_proleptic_ordinal(astro_year, month, day))

    weekday = get_weekday(target)
    target_ord = target.toordinal()

    diff = diff_days(target, today)
    year_label = format_year_label(year)
    date_label = f"{year_label}年{month}月{day}日 ({weekday})"

    cls = "today" if diff == 0 else ("future" if diff > 0 else "past")

    target_parts = DateParts(astro_year, month, day, target_ord)
    today_parts = DateParts(today.year, today.month, today.day, today.toordinal())
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
    calculate が date と同じように扱えるよう、必要な範囲で date の振る舞いを真似る
    （today との引き算 __sub__、weekday、toordinal）。
    """
    def __init__(self, ordinal: int):
        self.ordinal = ordinal

    def toordinal(self) -> int:
        return self.ordinal

    def weekday(self) -> int:
        """date.weekday() と同じく 月曜=0 … 日曜=6 を返す。通日1 = date(1,1,1) = 月曜。"""
        return (self.ordinal - 1) % 7

    def __sub__(self, other):
        """通日同士の差を timedelta で返す（左辺専用）。

        定義しているのは `_ProlepticDate - date` の向きだけで、__rsub__ は持たない。
        差分は必ず diff_days(target, today) の形で、target（この型が来うる側）を左辺に置くこと。
        """
        if isinstance(other, date):
            return timedelta(days=self.ordinal - other.toordinal())
        return NotImplemented


def _is_leap(year: int) -> bool:
    """先発グレゴリオ暦の閏年判定（引数は天文年代）。

    Python の % は負数でも非負を返すため、この式が天文年代の負の年（紀元前）にもそのまま成り立つ。
    """
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


def _days_in_month(astro_year: int, month: int) -> int:
    """その月の日数（天文年代。閏年の2月だけ29日）。"""
    return 29 if (month == 2 and _is_leap(astro_year)) else DAYS_IN_MONTH[month]


def _proleptic_ordinal(astro_year: int, month: int, day: int) -> int:
    """日付を先発グレゴリオ暦の通日（ordinal, date(1,1,1)=1）へ変換する。

    閏年の400年周期から閉じた式で求める（年数に比例するループを持たないので、
    どんな年を渡しても O(1)）。// は床除算なので天文年0以下（負の年）でもそのまま成立し、
    西暦1年以降は date.toordinal() と一致する。
    """
    y = astro_year - 1
    days_before_year = 365 * y + y // 4 - y // 100 + y // 400   # 対象年の元日の前日までの累積日数
    days_before_month = sum(_days_in_month(astro_year, m) for m in range(1, month))
    return days_before_year + days_before_month + day


def _anniversary_ordinal(astro_year: int, month: int, day: int, years: int) -> int:
    """基準日 (astro_year, month, day) の years 年後の記念日を通日で返す。

    対象年に応当日が無い場合（起点が 2月29日 で対象年が平年）は、その月の末日に丸める
    （民法143条2項の考え方。2/29 → 2/28）。応当日があれば min はそのまま day を返す。
    """
    target_year = astro_year + years
    eff_day = min(day, _days_in_month(target_year, month))
    return _proleptic_ordinal(target_year, month, eff_day)
