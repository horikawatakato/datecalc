"""
日数計算機 (DateCalc.py)
入力した日付と今日の差分を計算し、履歴を管理するCLIツールです。
"""

from datetime import date, timedelta
import re

# ── 定数 ──────────────────────────────────────────────────────────────────────
WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]
MAX_HISTORY = 8


# ── ユーティリティ ────────────────────────────────────────────────────────────
def get_weekday(d: date) -> str:
    """date オブジェクトの曜日を漢字1文字で返す（月〜日）。"""
    # weekday(): 月=0 … 日=6
    return WEEKDAYS[d.weekday()]


def is_valid_date(hist_year: int, month: int, day: int) -> bool:
    """
    存在する日付かどうかを検証する（hist_year は歴史年代）。
    JavaScript版と同様に、歴史年代0年は不正とし、
    月・日が範囲外の場合も False を返す。
    """
    if hist_year == 0:
        return False
    if not (1 <= month <= 12):
        return False
    max_day = DAYS_IN_MONTH[month]
    astro = historical_to_proleptic(hist_year)
    if month == 2 and _is_leap(astro):
        max_day = 29
    return 1 <= day <= max_day


def historical_to_proleptic(year: int) -> int:
    """
    歴史年代（紀元前 = 負の整数）を先発グレゴリオ暦（天文年代）に変換する。

    歴史年代に 0 年は存在しないため:
        紀元前 1 年 → 天文 0 年
        紀元前 2 年 → 天文 -1 年
        西暦 1 年〜 → そのまま

    Python の datetime.date は先発グレゴリオ暦を使うが、
    date(0, ...) を直接扱えないため year=1 以上が必要。
    このツールでは紀元前の日付も「差分計算のみ」で扱い、
    表示ラベルは元の歴史年代年号を使う。
    """
    return year + 1 if year < 0 else year


def diff_days(target: date, today: date) -> int:
    """target と today の差を日数で返す（未来は正、過去は負）。"""
    return (target - today).days


def describe_diff(diff: int, target: tuple, today: tuple) -> str:
    """
    日数差を人間が読みやすい文字列に変換する。

    target / today は (天文年, 月, 日, ordinal) のタプル。
    天文年は 0 や負数を含む連続した整数で表すため、紀元前をまたぐ
    経過年数も正しく数えられる（紀元前1年の翌年が西暦1年＝1年経過）。

    365日未満 → 「N日後/前」
    365日以上 → 「N日後/前 / Y年D日後/前」
    """
    if diff == 0:
        return "今日"

    abs_diff = abs(diff)
    suffix = "後" if diff > 0 else "前"

    if abs_diff < 365:
        return f"{abs_diff}日{suffix}"

    # 古い方を from、新しい方を to とする
    from_p, to_p = (today, target) if diff > 0 else (target, today)
    fay, fm, fd, ford = from_p
    tay, tm, td, tord = to_p

    # 経過年数（連続した天文年で計算するので紀元前↔西暦も正しく数えられる）
    years = tay - fay

    # 記念日（from + years年後）が to を超えていれば years を1減らす
    if _anniversary_ordinal(fay, fm, fd, years) > tord:
        years -= 1

    base_ord = _anniversary_ordinal(fay, fm, fd, years)
    remain_days = tord - base_ord

    year_part = f"{years}年"
    day_part = f"{remain_days}日" if remain_days > 0 else ""
    return f"{abs_diff}日{suffix} / {year_part}{day_part}{suffix}"


def format_year_label(year: int) -> str:
    """歴史年代の年を表示用文字列に変換する（紀元前は「紀元前N」）。"""
    return f"紀元前{abs(year)}" if year < 0 else str(year)


# ── 入力バリデーション ────────────────────────────────────────────────────────
def parse_year(s: str) -> int | None:
    """
    年の文字列をパースして整数を返す。
    不正・0・範囲外（-999〜-1, 1〜9999）の場合は None を返す。
    """
    s = s.strip()
    if not re.fullmatch(r'-?[1-9]\d*', s):
        return None
    val = int(s)
    if val == 0 or val > 9999 or val < -999:
        return None
    return val


def parse_month_or_day(s: str, min_val: int = 1, max_val: int = 99) -> int | None:
    """月または日の文字列をパースして整数を返す。不正な場合は None。"""
    s = s.strip()
    if not re.fullmatch(r'[1-9]\d*', s):
        return None
    val = int(s)
    if val < min_val or val > max_val:
        return None
    return val


# ── メインロジック ────────────────────────────────────────────────────────────
def calculate(year: int, month: int, day: int, today: date) -> dict:
    """
    日付を検証して差分情報を計算し、結果を辞書で返す。

    Returns:
        {
            "ok": bool,
            "error": str | None,         # エラーメッセージ（ok=False 時）
            "date_label": str,           # 例: "2025年1月1日(水)"
            "diff": int,                 # 日数差
            "diff_label": str,           # 例: "30日後 / 1ヶ月後"
            "cls": str,                  # "today" / "future" / "past"
        }
    """
    if not is_valid_date(year, month, day):
        return {"ok": False, "error": "この日付は存在しません"}

    astro_year = historical_to_proleptic(year)

    # Python の date は proleptic Gregorian calendar を使い、year >= 1 が必要。
    # 紀元前（astro_year <= 0）は差分計算に ordinal を用いる。
    if astro_year >= 1:
        target = date(astro_year, month, day)
    else:
        # Python date は年 1 以上しか扱えないため、ordinal で代替計算
        target = _proleptic_date(astro_year, month, day)

    diff = diff_days(target, today) if isinstance(target, date) else _diff_proleptic(target, today)

    weekday = get_weekday(target) if isinstance(target, date) else _weekday_proleptic(target)
    year_label = format_year_label(year)
    date_label = f"{year_label}年{month}月{day}日({weekday})"

    cls = "today" if diff == 0 else ("future" if diff > 0 else "past")

    # 差分表示用に (天文年, 月, 日, ordinal) のタプルを組み立てる。
    # 紀元前は date を作れないため astro_year と ordinal を直接使う。
    target_ord = target.toordinal() if isinstance(target, date) else target.ordinal
    target_parts = (astro_year, month, day, target_ord)
    today_parts = (today.year, today.month, today.day, today.toordinal())
    diff_label = describe_diff(diff, target_parts, today_parts)

    return {
        "ok": True,
        "date_label": date_label,
        "diff": diff,
        "diff_label": diff_label,
        "cls": cls,
    }


# ── 紀元前対応ヘルパー ─────────────────────────────────────────────────────────
class _ProlepticDate:
    """Python の date では扱えない天文年代0以下の日付を保持する簡易クラス。"""
    def __init__(self, ordinal: int):
        self.ordinal = ordinal  # proleptic Gregorian ordinal（date(1,1,1)=1 基準）

    def __sub__(self, other):
        if isinstance(other, _ProlepticDate):
            return timedelta(days=self.ordinal - other.ordinal)
        if isinstance(other, date):
            return timedelta(days=self.ordinal - other.toordinal())
        return NotImplemented

    def __rsub__(self, other):
        if isinstance(other, date):
            return timedelta(days=other.toordinal() - self.ordinal)
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, _ProlepticDate):
            return self.ordinal < other.ordinal
        if isinstance(other, date):
            return self.ordinal < other.toordinal()
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, _ProlepticDate):
            return self.ordinal > other.ordinal
        if isinstance(other, date):
            return self.ordinal > other.toordinal()
        return NotImplemented


def _is_leap(year: int) -> bool:
    """先発グレゴリオ暦の閏年判定（天文年代）。"""
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


DAYS_IN_MONTH = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _days_in_year(year: int) -> int:
    return 366 if _is_leap(year) else 365


def _proleptic_ordinal(astro_year: int, month: int, day: int) -> int:
    """
    天文年代（year <= 0 を含む）の日付を proleptic Gregorian ordinal に変換する。
    date(1,1,1).toordinal() == 1 を基準とする。

    正しい計算式:
        天文 astro_year の 1/1 の ordinal
            = 1 - sum(_days_in_year(y) for y in range(astro_year, 1))
        例) astro_year=0:  1 - 366        = -365  (0年は閏年)
            astro_year=-1: 1 - 366 - 365  = -730
    """
    if astro_year >= 1:
        return date(astro_year, month, day).toordinal()

    jan1_ordinal = 1 - sum(_days_in_year(y) for y in range(astro_year, 1))
    days_before_month = sum(
        DAYS_IN_MONTH[m] + (1 if m == 2 and _is_leap(astro_year) else 0)
        for m in range(1, month)
    )
    return jan1_ordinal + days_before_month + (day - 1)


def _anniversary_ordinal(astro_year: int, month: int, day: int, years: int) -> int:
    """
    (astro_year, month, day) の years 年後（負なら前）の記念日を ordinal で返す。
    天文年は連続した整数なので、紀元前をまたいでも単純な加算で扱える。
    2月29日は対象年が閏年でなければ3月1日に補正する（元実装と同じ挙動）。
    """
    target_year = astro_year + years
    if month == 2 and day == 29 and not _is_leap(target_year):
        return _proleptic_ordinal(target_year, 3, 1)
    return _proleptic_ordinal(target_year, month, day)


def _proleptic_date(astro_year: int, month: int, day: int) -> "_ProlepticDate | date":
    """
    天文年代（year <= 0 を含む）の日付を表すオブジェクトを返す。
    year >= 1 は通常の date、それ以外は _ProlepticDate（ordinal 保持）。
    """
    if astro_year >= 1:
        return date(astro_year, month, day)
    return _ProlepticDate(_proleptic_ordinal(astro_year, month, day))


def _diff_proleptic(target, today: date) -> int:
    """_ProlepticDate と date の差分を日数で返す。"""
    return (target - today).days


def _weekday_proleptic(target: _ProlepticDate) -> str:
    """
    _ProlepticDate の曜日を返す。
    date(1,1,1) は月曜で ordinal=1 なので (ordinal-1) % 7 でインデックスを求める。
    """
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


def print_history(history: list[dict]) -> None:
    """履歴をコンソールに表示する。"""
    if not history:
        print("  (履歴なし)")
        return
    for i, h in enumerate(history, 1):
        print(f"  {i}. {h['date_label']}  →  {h['diff_label']}")


def main() -> None:
    today = date.today()
    weekday_today = get_weekday(today)
    print(f"日数計算機")
    print(f"今日 — {today.year}年{today.month}月{today.day}日({weekday_today})")
    print("=" * 40)
    print("コマンド: 日付入力（例: 2030 3 15）/ h=履歴 / c=履歴クリア / q=終了")
    print()

    history: list[dict] = []

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

        # 入力パース
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
            # 重複エントリを除去して先頭に追加し、最大件数を維持する
            history = [result] + [h for h in history if h["date_label"] != result["date_label"]]
            history = history[:MAX_HISTORY]

        print()


if __name__ == "__main__":
    main()
