"""
test_datecalc.py
DateCalc.py の各関数に対するユニットテスト
"""

import pytest
from datetime import date
from DateCalc import (
    get_weekday,
    is_valid_date,
    historical_to_proleptic,
    diff_days,
    describe_diff,
    format_year_label,
    parse_year,
    parse_month_or_day,
    calculate,
)


# ── get_weekday ───────────────────────────────────────────────────────────────
class TestGetWeekday:
    def test_monday(self):
        assert get_weekday(date(2025, 1, 6)) == "月"

    def test_friday(self):
        assert get_weekday(date(2025, 1, 10)) == "金"

    def test_sunday(self):
        assert get_weekday(date(2025, 1, 12)) == "日"


# ── is_valid_date ─────────────────────────────────────────────────────────────
class TestIsValidDate:
    def test_valid_date(self):
        assert is_valid_date(2025, 5, 20) is True

    def test_year_zero_is_invalid(self):
        assert is_valid_date(0, 1, 1) is False

    def test_invalid_month(self):
        assert is_valid_date(2025, 13, 1) is False

    def test_invalid_day(self):
        assert is_valid_date(2025, 1, 32) is False

    def test_leap_year_feb29(self):
        assert is_valid_date(2024, 2, 29) is True

    def test_non_leap_year_feb29(self):
        assert is_valid_date(2025, 2, 29) is False

    def test_bc_year(self):
        assert is_valid_date(-1, 1, 1) is True


# ── historical_to_proleptic ───────────────────────────────────────────────────
class TestHistoricalToProleptic:
    def test_ad_year_unchanged(self):
        assert historical_to_proleptic(2025) == 2025

    def test_bc1_to_astro0(self):
        assert historical_to_proleptic(-1) == 0

    def test_bc2_to_astro_minus1(self):
        assert historical_to_proleptic(-2) == -1


# ── diff_days ─────────────────────────────────────────────────────────────────
class TestDiffDays:
    def test_future(self):
        today = date(2025, 1, 1)
        target = date(2025, 1, 11)
        assert diff_days(target, today) == 10

    def test_past(self):
        today = date(2025, 1, 11)
        target = date(2025, 1, 1)
        assert diff_days(target, today) == -10

    def test_same_day(self):
        today = date(2025, 5, 20)
        assert diff_days(today, today) == 0


# ── describe_diff ─────────────────────────────────────────────────────────────
class TestDescribeDiff:
    def test_today(self):
        today = date(2025, 5, 20)
        assert describe_diff(0, today, today) == "今日"

    def test_future_within_365(self):
        today = date(2025, 1, 1)
        target = date(2025, 6, 1)
        result = describe_diff(diff_days(target, today), target, today)
        assert "日後" in result
        assert "年" not in result

    def test_past_within_365(self):
        today = date(2025, 6, 1)
        target = date(2025, 1, 1)
        result = describe_diff(diff_days(target, today), target, today)
        assert "日前" in result
        assert "年" not in result

    def test_future_over_365(self):
        today = date(2025, 1, 1)
        target = date(2027, 1, 1)
        result = describe_diff(diff_days(target, today), target, today)
        assert "年" in result
        assert "日後" in result

    def test_past_over_365(self):
        today = date(2027, 1, 1)
        target = date(2025, 1, 1)
        result = describe_diff(diff_days(target, today), target, today)
        assert "年" in result
        assert "日前" in result


# ── format_year_label ─────────────────────────────────────────────────────────
class TestFormatYearLabel:
    def test_ad_year(self):
        assert format_year_label(2025) == "2025"

    def test_bc_year(self):
        assert format_year_label(-100) == "紀元前100"

    def test_year_1(self):
        assert format_year_label(1) == "1"


# ── parse_year ────────────────────────────────────────────────────────────────
class TestParseYear:
    def test_valid_ad(self):
        assert parse_year("2025") == 2025

    def test_valid_bc(self):
        assert parse_year("-100") == -100

    def test_zero_is_invalid(self):
        assert parse_year("0") is None

    def test_out_of_range_large(self):
        assert parse_year("10000") is None

    def test_out_of_range_small(self):
        assert parse_year("-1000") is None

    def test_non_numeric(self):
        assert parse_year("abc") is None

    def test_empty(self):
        assert parse_year("") is None


# ── parse_month_or_day ────────────────────────────────────────────────────────
class TestParseMonthOrDay:
    def test_valid_month(self):
        assert parse_month_or_day("6", 1, 12) == 6

    def test_invalid_month_zero(self):
        assert parse_month_or_day("0", 1, 12) is None

    def test_invalid_month_over(self):
        assert parse_month_or_day("13", 1, 12) is None

    def test_valid_day(self):
        assert parse_month_or_day("31", 1, 31) == 31

    def test_non_numeric(self):
        assert parse_month_or_day("abc") is None


# ── calculate ─────────────────────────────────────────────────────────────────
class TestCalculate:
    def test_today(self):
        today = date.today()
        result = calculate(today.year, today.month, today.day, today)
        assert result["ok"] is True
        assert result["cls"] == "today"
        assert result["diff"] == 0

    def test_future(self):
        today = date(2025, 1, 1)
        result = calculate(2025, 12, 31, today)
        assert result["ok"] is True
        assert result["cls"] == "future"
        assert result["diff"] > 0

    def test_past(self):
        today = date(2025, 6, 1)
        result = calculate(2025, 1, 1, today)
        assert result["ok"] is True
        assert result["cls"] == "past"
        assert result["diff"] < 0

    def test_invalid_date(self):
        today = date(2025, 1, 1)
        result = calculate(2025, 2, 30, today)
        assert result["ok"] is False
        assert "error" in result

    def test_date_label_format(self):
        today = date(2025, 1, 1)
        result = calculate(2025, 3, 15, today)
        assert "2025" in result["date_label"]
        assert "3" in result["date_label"]
        assert "15" in result["date_label"]

    def test_bc_year(self):
        today = date(2025, 1, 1)
        result = calculate(-100, 1, 1, today)
        assert result["ok"] is True
        assert "紀元前100" in result["date_label"]


# ══════════════════════════════════════════════════════════════════════════════
#  以下、カバレッジ100%達成のための追加テスト
# ══════════════════════════════════════════════════════════════════════════════
import runpy
import builtins
from datetime import timedelta
from DateCalc import (
    _ProlepticDate,
    _proleptic_date,
    _diff_proleptic,
    _weekday_proleptic,
    print_result,
    print_history,
    main,
)


# ── describe_diff: 2/29 の閏年補正・年数繰り下げ分岐 ───────────────────────────
class TestDescribeDiffEdgeCases:
    def test_leap_feb29_anniversary_correction(self):
        # from_date が 2/29 → replace(year) が ValueError となり 3/1 補正に入る
        today  = date(2024, 2, 29)   # 閏日
        target = date(2025, 3, 1)
        result = describe_diff(diff_days(target, today), target, today)
        assert result == "366日後 / 1年後"

    def test_year_decrement_branch(self):
        # 記念日が to_date を超える → years -= 1 の分岐を踏む
        today  = date(2025, 6, 1)
        target = date(2027, 3, 1)
        result = describe_diff(diff_days(target, today), target, today)
        assert result == "638日後 / 1年273日後"

    def test_past_feb29_anniversary_correction(self):
        # 過去方向で from_date(=target) が 2/29 のケース
        today  = date(2025, 3, 1)
        target = date(2024, 2, 29)
        result = describe_diff(diff_days(target, today), target, today)
        assert result.endswith("前")
        assert "年" in result


# ── _ProlepticDate: 各演算子（BC 差分計算の中核） ─────────────────────────────
class TestProlepticDate:
    def test_sub_proleptic_minus_proleptic(self):
        assert _ProlepticDate(100) - _ProlepticDate(40) == timedelta(days=60)

    def test_sub_proleptic_minus_date(self):
        assert _ProlepticDate(100) - date(1, 1, 1) == timedelta(days=99)

    def test_sub_notimplemented(self):
        assert _ProlepticDate(5).__sub__("x") is NotImplemented

    def test_rsub_date_minus_proleptic(self):
        assert date(1, 1, 1) - _ProlepticDate(-9) == timedelta(days=10)

    def test_rsub_notimplemented(self):
        assert _ProlepticDate(5).__rsub__(123) is NotImplemented

    def test_lt_proleptic(self):
        assert (_ProlepticDate(10) < _ProlepticDate(20)) is True

    def test_lt_date(self):
        assert (_ProlepticDate(-5) < date(1, 1, 1)) is True

    def test_lt_notimplemented(self):
        assert _ProlepticDate(5).__lt__("x") is NotImplemented

    def test_gt_proleptic(self):
        assert (_ProlepticDate(20) > _ProlepticDate(10)) is True

    def test_gt_date(self):
        assert (_ProlepticDate(10) > date(1, 1, 1)) is True

    def test_gt_notimplemented(self):
        assert _ProlepticDate(5).__gt__("x") is NotImplemented


# ── _proleptic_date / BC 計算の数値検証 ───────────────────────────────────────
class TestProlepticCalculation:
    def test_proleptic_date_ad_returns_date(self):
        # astro_year >= 1 の早期 return（通常の date を返す分岐）
        assert _proleptic_date(2025, 1, 1) == date(2025, 1, 1)

    def test_bc1_ad1_boundary_continuity(self):
        # 天文0年(=紀元前1年)12/31 の翌日が 西暦1年1/1 と連続している
        bc1_1231 = _proleptic_date(0, 12, 31)
        assert bc1_1231.ordinal + 1 == date(1, 1, 1).toordinal()

    def test_bc_diff_value(self):
        # calculate(-100,1,1) の差分日数を独立計算値と突き合わせ
        today = date(2025, 1, 1)
        res = calculate(-100, 1, 1, today)
        assert res["ok"] is True
        assert res["diff"] == -775776
        assert res["date_label"] == "紀元前100年1月1日(火)"

    def test_bc_leap_feb29_valid_and_counted(self):
        # 紀元前1年(=天文0年)は閏年。2/29 が存在し計算できる
        assert is_valid_date(-1, 2, 29) is True
        today = date(2025, 1, 1)
        res = calculate(-1, 2, 29, today)
        assert res["ok"] is True

    def test_diff_proleptic_helper(self):
        target = _proleptic_date(0, 1, 1)
        assert _diff_proleptic(target, date(1, 1, 1)) == target.ordinal - 1

    def test_weekday_proleptic_helper(self):
        # date(1,1,1)=月曜=ordinal1。ordinal1 を渡すと「月」
        assert _weekday_proleptic(_ProlepticDate(1)) == "月"


# ── print_result / print_history（CLI 表示） ─────────────────────────────────
class TestPrintFunctions:
    def test_print_result_error(self, capsys):
        print_result({"ok": False, "error": "この日付は存在しません"})
        assert "エラー" in capsys.readouterr().out

    def test_print_result_success(self, capsys):
        print_result({
            "ok": True, "date_label": "2025年3月15日(土)",
            "diff_label": "73日後", "cls": "future",
        })
        out = capsys.readouterr().out
        assert "2025年3月15日(土)" in out
        assert "未来" in out

    def test_print_history_empty(self, capsys):
        print_history([])
        assert "履歴なし" in capsys.readouterr().out

    def test_print_history_items(self, capsys):
        print_history([{"date_label": "2025年3月15日(土)", "diff_label": "73日後"}])
        assert "1. 2025年3月15日(土)" in capsys.readouterr().out


# ── main（CLI ループ）の全分岐 ────────────────────────────────────────────────
class TestMainLoop:
    def test_main_all_branches(self, capsys, monkeypatch):
        inputs = iter([
            "",               # 形式不正（パーツ数 != 3）
            "abc 1 1",        # 年が不正
            "2025 abc 1",     # 月が不正
            "2025 1 abc",     # 日が不正
            "2025 2 30",      # 存在しない日付（calculate が ok=False）
            "2025 3 15",      # 正常 → 履歴追加
            "2025 3 15",      # 重複 → 履歴で重複排除
            "h",              # 履歴表示
            "c",              # 履歴クリア
            "q",              # 終了
        ])
        monkeypatch.setattr(builtins, "input", lambda *a, **k: next(inputs))
        main()
        out = capsys.readouterr().out
        assert "日数計算機" in out
        assert "入力形式が正しくありません" in out
        assert "年の入力が正しくありません" in out
        assert "月の入力が正しくありません" in out
        assert "日の入力が正しくありません" in out
        assert "この日付は存在しません" in out
        assert "履歴をクリアしました" in out
        assert "終了します" in out

    def test_main_eof(self, capsys, monkeypatch):
        def raise_eof(*a, **k):
            raise EOFError
        monkeypatch.setattr(builtins, "input", raise_eof)
        main()
        assert "終了します" in capsys.readouterr().out

    def test_dunder_main_entrypoint(self, monkeypatch):
        # if __name__ == "__main__": main() の行を実行する
        monkeypatch.setattr(builtins, "input", lambda *a, **k: "q")
        runpy.run_path("DateCalc.py", run_name="__main__")
