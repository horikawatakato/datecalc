"""
DateCalc.py のユニットテスト（カバレッジ100%を目標）

実行例:
    pytest --cov=DateCalc --cov-report=term-missing test_DateCalc.py
"""

import runpy
from datetime import date, timedelta
from unittest import mock

import pytest

import DateCalc as D


TODAY = date(2026, 6, 3)  # テストの基準日（固定）


# ── get_weekday ───────────────────────────────────────────────────────────────
def test_get_weekday():
    assert D.get_weekday(date(2026, 6, 3)) == "水"
    assert D.get_weekday(date(2026, 6, 1)) == "月"
    assert D.get_weekday(date(2026, 6, 7)) == "日"


# ── historical_to_proleptic ───────────────────────────────────────────────────
def test_historical_to_proleptic():
    assert D.historical_to_proleptic(-1) == 0     # 紀元前1年 → 天文0年
    assert D.historical_to_proleptic(-2) == -1    # 紀元前2年 → 天文-1年
    assert D.historical_to_proleptic(2026) == 2026


# ── is_valid_date ─────────────────────────────────────────────────────────────
def test_is_valid_date():
    assert D.is_valid_date(2026, 6, 3) is True
    assert D.is_valid_date(0, 1, 1) is False           # 0年は不正
    assert D.is_valid_date(2026, 13, 1) is False        # 月が範囲外
    assert D.is_valid_date(2026, 0, 1) is False         # 月が範囲外（下限）
    assert D.is_valid_date(2020, 2, 29) is True         # 閏年の2月29日
    assert D.is_valid_date(2021, 2, 29) is False        # 非閏年の2月29日
    assert D.is_valid_date(2026, 4, 31) is False        # 4月31日は存在しない
    assert D.is_valid_date(-1, 12, 31) is True          # 紀元前1年12月31日


# ── format_year_label ─────────────────────────────────────────────────────────
def test_format_year_label():
    assert D.format_year_label(2026) == "2026"
    assert D.format_year_label(-100) == "紀元前100"


# ── diff_days ─────────────────────────────────────────────────────────────────
def test_diff_days():
    assert D.diff_days(date(2026, 6, 13), TODAY) == 10
    assert D.diff_days(date(2026, 5, 24), TODAY) == -10


# ── parse_year ────────────────────────────────────────────────────────────────
def test_parse_year():
    assert D.parse_year("2026") == 2026
    assert D.parse_year(" -999 ") == -999
    assert D.parse_year("9999") == 9999
    assert D.parse_year("abc") is None       # 正規表現で不一致
    assert D.parse_year("12a") is None
    assert D.parse_year("10000") is None      # 上限超過
    assert D.parse_year("-1000") is None      # 下限未満
    assert D.parse_year("0") is None          # 0は正規表現で不一致


# ── parse_month_or_day ────────────────────────────────────────────────────────
def test_parse_month_or_day():
    assert D.parse_month_or_day("6") == 6
    assert D.parse_month_or_day("99") == 99
    assert D.parse_month_or_day("abc") is None   # 正規表現で不一致
    assert D.parse_month_or_day("0") is None      # 0は正規表現で不一致
    assert D.parse_month_or_day("100") is None    # 範囲外（max=99）
    assert D.parse_month_or_day("5", min_val=10, max_val=20) is None  # 下限未満


# ── calculate: 通常（西暦）ケース ─────────────────────────────────────────────
def test_calculate_today():
    r = D.calculate(2026, 6, 3, TODAY)
    assert r["ok"] is True
    assert r["cls"] == "today"
    assert r["diff"] == 0
    assert r["diff_label"] == "今日"
    assert r["date_label"] == "2026年6月3日(水)"


def test_calculate_future_small():
    r = D.calculate(2026, 6, 13, TODAY)  # 10日後（365日未満）
    assert r["cls"] == "future"
    assert r["diff"] == 10
    assert r["diff_label"] == "10日後"


def test_calculate_past_small():
    r = D.calculate(2026, 5, 24, TODAY)  # 10日前（365日未満）
    assert r["cls"] == "past"
    assert r["diff"] == -10
    assert r["diff_label"] == "10日前"


def test_calculate_future_big_with_days():
    r = D.calculate(2030, 3, 15, TODAY)  # 365日以上・記念日超過で years-=1 する分岐
    assert r["cls"] == "future"
    assert "年" in r["diff_label"]
    assert "日後 / " in r["diff_label"]
    # 1381日後 / 3年285日後
    assert r["diff"] == 1381
    assert r["diff_label"] == "1381日後 / 3年285日後"


def test_calculate_future_big_anniversary_not_passed():
    # 記念日が to を超えない分岐（years -=1 されない）かつ余り日数あり
    r = D.calculate(2030, 8, 1, TODAY)
    assert r["cls"] == "future"
    assert r["diff_label"].endswith("4年59日後")


def test_calculate_future_exact_years_no_day_part():
    # ちょうど年数単位で割り切れ、余り日数0 → day_part が空になる分岐
    r = D.calculate(2031, 6, 3, TODAY)
    assert r["cls"] == "future"
    assert r["diff_label"].endswith("5年後")
    assert "年後 /" not in r["diff_label"].split("/")[1] if "/" in r["diff_label"] else True


def test_calculate_past_big():
    r = D.calculate(2025, 1, 1, TODAY)  # 365日以上前
    assert r["cls"] == "past"
    assert r["diff"] == -518
    assert r["diff_label"] == "518日前 / 1年153日前"


# ── calculate: 紀元前ケース（今回の修正対象） ─────────────────────────────────
def test_calculate_bc_100():
    r = D.calculate(-100, 1, 1, TODAY)
    assert r["ok"] is True
    assert r["cls"] == "past"
    assert r["date_label"].startswith("紀元前100年1月1日")
    # 紀元前100年 → 西暦2026年 は 2125年経過（0年が無い前提と一致）
    assert r["diff_label"] == "776294日前 / 2125年153日前"
    assert "0年前" not in r["diff_label"]


def test_calculate_bc_1():
    r = D.calculate(-1, 1, 1, TODAY)
    assert r["diff_label"].startswith("740135日前 / 2026年")
    assert "0年" not in r["diff_label"].split("/")[1]


def test_calculate_bc_999():
    r = D.calculate(-999, 1, 1, TODAY)
    assert "3024年" in r["diff_label"]


def test_calculate_bc_ad_boundary_consecutive():
    # 紀元前1年12月31日 と 西暦1年1月1日 は連続（1日差・0年なし）
    r = D.calculate(-1, 12, 31, date(1, 1, 1))
    assert r["diff"] == -1
    assert r["diff_label"] == "1日前"


def test_calculate_bc_feb29_anniversary_branch():
    # from_p が 2月29日（閏年）→ 記念日が非閏年で3月1日補正される分岐を踏む
    r = D.calculate(2020, 2, 29, TODAY)
    assert r["cls"] == "past"
    assert r["diff_label"].endswith("6年94日前")


def test_calculate_invalid_date():
    r = D.calculate(2021, 2, 29, TODAY)  # 非閏年の2月29日
    assert r["ok"] is False
    assert r["error"] == "この日付は存在しません"


# ── 低レベルヘルパー ──────────────────────────────────────────────────────────
def test_is_leap():
    assert D._is_leap(2020) is True
    assert D._is_leap(2021) is False
    assert D._is_leap(1900) is False   # 100で割れるが400で割れない
    assert D._is_leap(2000) is True    # 400で割れる
    assert D._is_leap(0) is True       # 天文0年は閏年


def test_days_in_year():
    assert D._days_in_year(2020) == 366
    assert D._days_in_year(2021) == 365


def test_proleptic_ordinal():
    # 西暦（>=1）は date.toordinal と一致
    assert D._proleptic_ordinal(2026, 6, 3) == date(2026, 6, 3).toordinal()
    # 天文0年1月1日 = ordinal -365（0年は閏年で前年366日ぶん手前）
    assert D._proleptic_ordinal(0, 1, 1) == -365
    assert D._proleptic_ordinal(-1, 1, 1) == -730


def test_anniversary_ordinal():
    # 通常の年加算
    assert D._anniversary_ordinal(2020, 1, 1, 6) == date(2026, 1, 1).toordinal()
    # 2月29日 → 非閏年では3月1日に補正
    assert D._anniversary_ordinal(2020, 2, 29, 1) == date(2021, 3, 1).toordinal()
    # 2月29日 → 閏年ならそのまま
    assert D._anniversary_ordinal(2020, 2, 29, 4) == date(2024, 2, 29).toordinal()


def test_proleptic_date():
    # 西暦は date を返す
    d = D._proleptic_date(2026, 6, 3)
    assert isinstance(d, date)
    assert d == date(2026, 6, 3)
    # 紀元前は _ProlepticDate を返す
    pd = D._proleptic_date(0, 1, 1)
    assert isinstance(pd, D._ProlepticDate)
    assert pd.ordinal == -365


def test_diff_proleptic():
    pd = D._proleptic_date(0, 1, 1)  # ordinal -365
    assert D._diff_proleptic(pd, date(1, 1, 1)) == -365 - 1


def test_weekday_proleptic():
    # ordinal=1 は date(1,1,1)=月曜
    assert D._weekday_proleptic(D._ProlepticDate(1)) == "月"
    assert D._weekday_proleptic(D._ProlepticDate(2)) == "火"


# ── _ProlepticDate のダンダーメソッド ─────────────────────────────────────────
def test_proleptic_date_dunders():
    a = D._ProlepticDate(100)
    b = D._ProlepticDate(150)

    # __sub__
    assert (b - a) == timedelta(days=50)
    assert (a - date(1, 1, 1)) == timedelta(days=99)
    assert a.__sub__("x") is NotImplemented

    # __rsub__（date - _ProlepticDate）
    assert (date(1, 1, 1) - a) == timedelta(days=1 - 100)
    assert a.__rsub__("x") is NotImplemented

    # __lt__
    assert (a < b) is True
    assert (a < date(1, 1, 1)) is False
    assert a.__lt__("x") is NotImplemented

    # __gt__
    assert (b > a) is True
    assert (a > date(1, 1, 1)) is True
    assert a.__gt__("x") is NotImplemented


# ── print_result / print_history ──────────────────────────────────────────────
def test_print_result_ok(capsys):
    r = D.calculate(2030, 3, 15, TODAY)
    D.print_result(r)
    out = capsys.readouterr().out
    assert "2030年3月15日" in out
    assert "[未来]" in out


def test_print_result_error(capsys):
    r = D.calculate(2021, 2, 29, TODAY)
    D.print_result(r)
    out = capsys.readouterr().out
    assert "エラー" in out


def test_print_history_empty(capsys):
    D.print_history([])
    assert "(履歴なし)" in capsys.readouterr().out


def test_print_history_items(capsys):
    r = D.calculate(2030, 3, 15, TODAY)
    D.print_history([r])
    out = capsys.readouterr().out
    assert "1." in out
    assert "2030年3月15日" in out


# ── main(): CLIループの全分岐 ─────────────────────────────────────────────────
def test_main_full_flow(capsys):
    inputs = [
        "h",            # 履歴（空）
        "2021 2 29",    # 存在しない日付 → print_result エラー
        "5 6 7",        # 有効（別エントリ）
        "1 2 3",        # 有効（追加）
        "1 2 3",        # 重複 → dedup フィルタ（残す分・除く分の両方を踏む）
        "h",            # 履歴（非空）
        "x y",          # 形式不正（パーツ数 != 3）
        "0 1 1",        # 年が不正（parse_year None）
        "2020 0 1",     # 月が不正（parse_month_or_day None）
        "2020 1 0",     # 日が不正（parse_month_or_day None）
        "c",            # 履歴クリア
        "q",            # 終了
    ]
    with mock.patch("builtins.input", side_effect=inputs):
        D.main()
    out = capsys.readouterr().out
    assert "日数計算機" in out
    assert "(履歴なし)" in out
    assert "この日付は存在しません" in out
    assert "履歴をクリアしました" in out
    assert "終了します" in out


def test_main_eof(capsys):
    # 入力で EOFError/KeyboardInterrupt → except 節で break
    with mock.patch("builtins.input", side_effect=EOFError):
        D.main()
    assert "終了します" in capsys.readouterr().out


def test_main_quit_variants(capsys):
    for cmd in ("quit", "exit"):
        with mock.patch("builtins.input", side_effect=[cmd]):
            D.main()
    assert "終了します" in capsys.readouterr().out


# ── `if __name__ == "__main__"` ガード行のカバレッジ ──────────────────────────
def test_module_run_as_main(capsys):
    # run_name="__main__" で実行し、ガード内の main() 呼び出し行をカバーする
    with mock.patch("builtins.input", side_effect=EOFError):
        runpy.run_path(D.__file__, run_name="__main__")
    assert "日数計算機" in capsys.readouterr().out
