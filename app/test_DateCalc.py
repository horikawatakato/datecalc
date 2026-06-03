"""DateCalc.py のユニットテスト（カバレッジ100%）"""

import runpy
from datetime import date, timedelta
from unittest import mock

import pytest

import DateCalc as D

TODAY = date(2026, 6, 3)


def test_get_weekday():
    assert D.get_weekday(date(2026, 6, 3)) == "水"
    assert D.get_weekday(date(2026, 6, 1)) == "月"
    assert D.get_weekday(date(2026, 6, 7)) == "日"


def test_historical_to_proleptic():
    assert D.historical_to_proleptic(-1) == 0
    assert D.historical_to_proleptic(-2) == -1
    assert D.historical_to_proleptic(2026) == 2026


def test_is_valid_date():
    assert D.is_valid_date(2026, 6, 3) is True
    assert D.is_valid_date(0, 1, 1) is False
    assert D.is_valid_date(2026, 13, 1) is False
    assert D.is_valid_date(2026, 0, 1) is False
    assert D.is_valid_date(2020, 2, 29) is True
    assert D.is_valid_date(2021, 2, 29) is False
    assert D.is_valid_date(2026, 4, 31) is False
    assert D.is_valid_date(-1, 12, 31) is True


def test_format_year_label():
    assert D.format_year_label(2026) == "2026"
    assert D.format_year_label(-100) == "紀元前100"


def test_diff_days():
    assert D.diff_days(date(2026, 6, 13), TODAY) == 10
    assert D.diff_days(date(2026, 5, 24), TODAY) == -10


def test_parse_year():
    assert D.parse_year("2026") == 2026
    assert D.parse_year(" -999 ") == -999
    assert D.parse_year("9999") == 9999
    assert D.parse_year("abc") is None
    assert D.parse_year("12a") is None
    assert D.parse_year("10000") is None
    assert D.parse_year("-1000") is None
    assert D.parse_year("0") is None


def test_parse_month_or_day():
    assert D.parse_month_or_day("6") == 6
    assert D.parse_month_or_day("99") == 99
    assert D.parse_month_or_day("abc") is None
    assert D.parse_month_or_day("0") is None
    assert D.parse_month_or_day("100") is None
    assert D.parse_month_or_day("5", min_val=10, max_val=20) is None


def test_calculate_today():
    r = D.calculate(2026, 6, 3, TODAY)
    assert r["ok"] is True
    assert r["cls"] == "today"
    assert r["diff"] == 0
    assert r["diff_label"] == "今日"
    assert r["date_label"] == "2026年6月3日(水)"


def test_calculate_future_small():
    r = D.calculate(2026, 6, 13, TODAY)
    assert r["cls"] == "future"
    assert r["diff"] == 10
    assert r["diff_label"] == "10日後"


def test_calculate_past_small():
    r = D.calculate(2026, 5, 24, TODAY)
    assert r["cls"] == "past"
    assert r["diff"] == -10
    assert r["diff_label"] == "10日前"


def test_calculate_future_big_with_days():
    r = D.calculate(2030, 3, 15, TODAY)
    assert r["cls"] == "future"
    assert r["diff"] == 1381
    assert r["diff_label"] == "1381日後 / 3年285日後"


def test_calculate_future_big_anniversary_not_passed():
    r = D.calculate(2030, 8, 1, TODAY)
    assert r["cls"] == "future"
    assert r["diff_label"].endswith("4年59日後")


def test_calculate_future_exact_years_no_day_part():
    r = D.calculate(2031, 6, 3, TODAY)
    assert r["cls"] == "future"
    assert r["diff_label"].endswith("5年後")
    assert "日後 /" in r["diff_label"]


def test_calculate_past_big():
    r = D.calculate(2025, 1, 1, TODAY)
    assert r["cls"] == "past"
    assert r["diff"] == -518
    assert r["diff_label"] == "518日前 / 1年153日前"


def test_calculate_365_days_leap_crossing_future_no_zero_year():
    r = D.calculate(2024, 12, 31, date(2024, 1, 1))
    assert r["diff"] == 365
    assert r["diff_label"] == "365日後"
    assert "0年" not in r["diff_label"]


def test_calculate_365_days_leap_crossing_past_no_zero_year():
    r = D.calculate(2023, 3, 1, date(2024, 2, 29))
    assert r["diff"] == -365
    assert r["diff_label"] == "365日前"
    assert "0年" not in r["diff_label"]


def test_calculate_bc_100():
    r = D.calculate(-100, 1, 1, TODAY)
    assert r["ok"] is True
    assert r["cls"] == "past"
    assert r["date_label"].startswith("紀元前100年1月1日")
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
    r = D.calculate(-1, 12, 31, date(1, 1, 1))
    assert r["diff"] == -1
    assert r["diff_label"] == "1日前"


def test_calculate_bc_feb29_anniversary_branch():
    r = D.calculate(2020, 2, 29, TODAY)
    assert r["cls"] == "past"
    assert r["diff_label"].endswith("6年94日前")


def test_calculate_invalid_date():
    r = D.calculate(2021, 2, 29, TODAY)
    assert r["ok"] is False
    assert r["error"] == "この日付は存在しません"


def test_is_leap():
    assert D._is_leap(2020) is True
    assert D._is_leap(2021) is False
    assert D._is_leap(1900) is False
    assert D._is_leap(2000) is True
    assert D._is_leap(0) is True


def test_days_in_year():
    assert D._days_in_year(2020) == 366
    assert D._days_in_year(2021) == 365


def test_proleptic_ordinal():
    assert D._proleptic_ordinal(2026, 6, 3) == date(2026, 6, 3).toordinal()
    assert D._proleptic_ordinal(0, 1, 1) == -365
    assert D._proleptic_ordinal(-1, 1, 1) == -730


def test_anniversary_ordinal():
    assert D._anniversary_ordinal(2020, 1, 1, 6) == date(2026, 1, 1).toordinal()
    assert D._anniversary_ordinal(2020, 2, 29, 1) == date(2021, 3, 1).toordinal()
    assert D._anniversary_ordinal(2020, 2, 29, 4) == date(2024, 2, 29).toordinal()


def test_proleptic_date():
    d = D._proleptic_date(2026, 6, 3)
    assert isinstance(d, date)
    assert d == date(2026, 6, 3)
    pd = D._proleptic_date(0, 1, 1)
    assert isinstance(pd, D._ProlepticDate)
    assert pd.ordinal == -365


def test_diff_proleptic():
    pd = D._proleptic_date(0, 1, 1)
    assert D._diff_proleptic(pd, date(1, 1, 1)) == -365 - 1


def test_weekday_proleptic():
    assert D._weekday_proleptic(D._ProlepticDate(1)) == "月"
    assert D._weekday_proleptic(D._ProlepticDate(2)) == "火"


def test_proleptic_date_dunders():
    a = D._ProlepticDate(100)
    b = D._ProlepticDate(150)
    assert (b - a) == timedelta(days=50)
    assert (a - date(1, 1, 1)) == timedelta(days=99)
    assert a.__sub__("x") is NotImplemented
    assert (date(1, 1, 1) - a) == timedelta(days=1 - 100)
    assert a.__rsub__("x") is NotImplemented
    assert (a < b) is True
    assert (a < date(1, 1, 1)) is False
    assert a.__lt__("x") is NotImplemented
    assert (b > a) is True
    assert (a > date(1, 1, 1)) is True
    assert a.__gt__("x") is NotImplemented


def test_print_result_ok(capsys):
    r = D.calculate(2030, 3, 15, TODAY)
    D.print_result(r)
    out = capsys.readouterr().out
    assert "2030年3月15日" in out
    assert "[未来]" in out


def test_print_result_error(capsys):
    r = D.calculate(2021, 2, 29, TODAY)
    D.print_result(r)
    assert "エラー" in capsys.readouterr().out


def test_print_history_empty(capsys):
    D.print_history([])
    assert "(履歴なし)" in capsys.readouterr().out


def test_print_history_items(capsys):
    r = D.calculate(2030, 3, 15, TODAY)
    D.print_history([r])
    out = capsys.readouterr().out
    assert "1." in out
    assert "2030年3月15日" in out


def test_main_full_flow(capsys):
    inputs = [
        "h", "2021 2 29", "5 6 7", "1 2 3", "1 2 3", "h",
        "x y", "0 1 1", "2020 0 1", "2020 1 0", "c", "q",
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
    with mock.patch("builtins.input", side_effect=EOFError):
        D.main()
    assert "終了します" in capsys.readouterr().out


def test_main_quit_variants(capsys):
    for cmd in ("quit", "exit"):
        with mock.patch("builtins.input", side_effect=[cmd]):
            D.main()
    assert "終了します" in capsys.readouterr().out


def test_module_run_as_main(capsys):
    with mock.patch("builtins.input", side_effect=EOFError):
        runpy.run_path(D.__file__, run_name="__main__")
    assert "日数計算機" in capsys.readouterr().out
