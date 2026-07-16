"""DateCalc.py のユニットテスト（カバレッジ100%）"""

import ast
import os
import re
from datetime import date, datetime, timedelta, timezone

import pytest

import DateCalc as D

TODAY = date(2026, 6, 3)


def test_get_today_is_jst(monkeypatch):
    # get_today は日本標準時(UTC+9)の「今日」を返す。
    # 時計を固定して、UTC ではまだ 6/3 の時刻に JST の 6/4 を返すことを確かめる
    # （23:30 UTC = 翌 08:30 JST）。実時刻と比べると日付が変わる瞬間に落ちるため固定する。
    assert D.JST == timezone(timedelta(hours=9))
    fixed = datetime(2026, 6, 3, 23, 30, tzinfo=timezone.utc)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed.astimezone(tz)

    monkeypatch.setattr(D, "datetime", FixedDatetime)
    assert D.get_today() == date(2026, 6, 4)


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


@pytest.mark.parametrize("hist_year, astro_year, valid", [
    (-97,  -96,  True),   # 天文年 -96：4の倍数 → 閏年
    (-100, -99,  False),  # 天文年 -99：平年（紀元前100年は閏年ではない）
    (-101, -100, False),  # 天文年 -100：100の倍数だが400の倍数でない → 平年
    (-401, -400, True),   # 天文年 -400：400の倍数 → 閏年
    (-1,     0,  True),   # 天文年 0：閏年（紀元前1年に 2月29日 が存在する）
])
def test_is_valid_date_bc_leap_day(hist_year, astro_year, valid):
    # 紀元前の閏年は歴史年代のままでは判定できない（1年ぶんずれる）。
    # 天文年代へ直してから判定していることを、閏日の実在で固定する
    assert D.historical_to_proleptic(hist_year) == astro_year
    assert D.is_valid_date(hist_year, 2, 29) is valid
    assert D.calculate(hist_year, 2, 29, TODAY)["ok"] is valid


def test_format_year_label():
    assert D.format_year_label(2026) == "2026"
    assert D.format_year_label(-100) == "BC100"


def test_diff_days():
    assert D.diff_days(date(2026, 6, 13), TODAY) == 10
    assert D.diff_days(date(2026, 5, 24), TODAY) == -10


def test_calculate_today():
    r = D.calculate(2026, 6, 3, TODAY)
    assert r["ok"] is True
    assert r["cls"] == "today"
    assert r["diff"] == 0
    assert r["diff_label"] == "今日"
    assert r["date_label"] == "2026年6月3日 (水)"


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
    assert r["date_label"].startswith("BC100年1月1日")
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


def test_calculate_feb29_anniversary_rolls_to_last_day():
    # 2020/2/29 の「6年後の記念日」は平年 2026年 に 2/29 が無いので末日 2/28 に丸められ、
    # そこ（2026/2/28）から TODAY(6/3) までの端数が 95日 になる
    r = D.calculate(2020, 2, 29, TODAY)
    assert r["cls"] == "past"
    assert r["diff_label"].endswith("6年95日前")


def test_calculate_feb29_anniversary_last_day_boundary():
    # 2/29 起点の年数表示の境界（末日丸めの新仕様を calculate 経由で固定する）。
    # 対象年が平年なので応当日は 2/28 に丸められ、そこを追い越すかどうかで年数が決まる。
    #   today = 2023/2/28 … 記念日ちょうど → 端数なしの「3年前」
    assert D.calculate(2020, 2, 29, date(2023, 2, 28))["diff_label"] == "1095日前 / 3年前"
    #   today = 2023/3/1  … 末日の翌日 → 「3年1日前」
    assert D.calculate(2020, 2, 29, date(2023, 3, 1))["diff_label"] == "1096日前 / 3年1日前"


def test_calculate_invalid_date():
    r = D.calculate(2021, 2, 29, TODAY)
    assert r["ok"] is False
    assert r["error"] == "この日付は存在しません"


def test_calculate_year_range_boundaries_ok():
    # 対応範囲の両端はそのまま計算できる
    assert D.calculate(D.MAX_HIST_YEAR, 12, 31, TODAY)["ok"] is True
    assert D.calculate(D.MIN_HIST_YEAR, 1, 1, TODAY)["ok"] is True


def test_calculate_year_out_of_range():
    # 範囲外の年は例外ではなくエラー辞書で返す（西暦10000年は date が扱えない）
    for year in (D.MAX_HIST_YEAR + 1, D.MIN_HIST_YEAR - 1):
        r = D.calculate(year, 1, 1, TODAY)
        assert r["ok"] is False
        assert r["error"] == "対応範囲は紀元前999年〜西暦9999年です"


def test_calculate_huge_negative_year_returns_immediately():
    # 巨大な負の年は範囲チェックで即座に弾く（通日計算の年ループへ入らせない）
    r = D.calculate(-999999999, 1, 1, TODAY)
    assert r["ok"] is False


def test_is_leap():
    assert D._is_leap(2020) is True
    assert D._is_leap(2021) is False
    assert D._is_leap(1900) is False
    assert D._is_leap(2000) is True
    assert D._is_leap(0) is True
    # 負の天文年（紀元前）。Python の % は負数でも非負を返すので、正の年と同じ規則がそのまま成立する
    assert D._is_leap(-4) is True
    assert D._is_leap(-1) is False
    assert D._is_leap(-100) is False   # 100の倍数だが400の倍数でない
    assert D._is_leap(-400) is True


def test_days_in_month():
    assert D._days_in_month(2021, 2) == 28
    assert D._days_in_month(2020, 2) == 29
    assert D._days_in_month(2026, 4) == 30
    assert D._days_in_month(2026, 12) == 31
    assert D._days_in_month(-96, 2) == 29   # 紀元前97年（天文年 -96）は閏年


def test_proleptic_ordinal():
    assert D._proleptic_ordinal(2026, 6, 3) == date(2026, 6, 3).toordinal()
    assert D._proleptic_ordinal(0, 1, 1) == -365
    assert D._proleptic_ordinal(-1, 1, 1) == -730


def test_proleptic_ordinal_matches_date_and_is_contiguous():
    # 西暦側は datetime.date と完全に一致する（閉じた式が date の暦と同じ暦であることの担保）
    for y, m, d in [(1, 1, 1), (4, 2, 29), (100, 3, 1), (2026, 6, 3), (9999, 12, 31)]:
        assert D._proleptic_ordinal(y, m, d) == date(y, m, d).toordinal()

    # 紀元前1年12月31日（天文年0）の翌日が 西暦1年1月1日（歴史年代に 0 年は無い）
    assert D._proleptic_ordinal(0, 12, 31) + 1 == date(1, 1, 1).toordinal()

    # 紀元前側でも通日が1日ずつ連続する（年またぎ・閏日の前後で飛びが無い）
    for year in (-400, -100, -96, 0):
        assert D._proleptic_ordinal(year, 12, 31) + 1 == D._proleptic_ordinal(year + 1, 1, 1)
        # 2月の末日の翌日が3月1日（閏年なら 2/29、平年なら 2/28 の次）
        last_feb_day = 29 if D._is_leap(year) else 28
        assert D._proleptic_ordinal(year, 2, last_feb_day) + 1 == D._proleptic_ordinal(year, 3, 1)


def test_anniversary_ordinal():
    assert D._anniversary_ordinal(2020, 1, 1, 6) == date(2026, 1, 1).toordinal()
    # 対象年が平年なら 2/29 → 末日 2/28 に丸める（民法143条2項）
    assert D._anniversary_ordinal(2020, 2, 29, 1) == date(2021, 2, 28).toordinal()
    # 対象年が閏年なら 2/29 のまま
    assert D._anniversary_ordinal(2020, 2, 29, 4) == date(2024, 2, 29).toordinal()


def _parts(year, month, day):
    """describe_diff に渡す DateParts を天文年代から組み立てる。"""
    return D.DateParts(year, month, day, D._proleptic_ordinal(year, month, day))


def test_describe_diff_boundaries():
    # 0日 → 「今日」
    p = _parts(2026, 6, 3)
    assert D.describe_diff(0, p, p) == "今日"

    # 365日未満は日数のみ（364日が上限）
    today = _parts(2026, 6, 3)
    assert D.describe_diff(364, _parts(2027, 6, 2), today) == "364日後"
    assert D.describe_diff(-364, _parts(2025, 6, 4), today) == "364日前"

    # 365日ちょうどで年数の併記が始まる（平年をまたぐので暦の上でも1年）
    assert D.describe_diff(365, _parts(2027, 6, 3), today) == "365日後 / 1年後"

    # 閏年をまたぐ365日は暦の上では1年未満なので、日数のみに落ちる
    leap_today = _parts(2024, 1, 1)
    assert D.describe_diff(365, _parts(2024, 12, 31), leap_today) == "365日後"

    # 366日で1年＋端数
    assert D.describe_diff(366, _parts(2027, 6, 4), today) == "366日後 / 1年1日後"


def test_proleptic_date_quacks_like_date():
    # _ProlepticDate は date と同じ形で曜日・通日を返すので get_weekday がそのまま使える
    assert D._ProlepticDate(1).toordinal() == 1
    assert D._ProlepticDate(1).weekday() == date(1, 1, 1).weekday()  # 通日1 = 月曜
    assert D.get_weekday(D._ProlepticDate(1)) == "月"
    assert D.get_weekday(D._ProlepticDate(2)) == "火"


def test_proleptic_date_sub():
    a = D._ProlepticDate(100)
    # _ProlepticDate - date → 通日差（timedelta）
    assert (a - date(1, 1, 1)) == timedelta(days=99)
    # date 以外との減算は NotImplemented を返す
    assert a.__sub__("x") is NotImplemented


def test_calculate_bc_weekday_in_label():
    # 紀元前は _ProlepticDate.weekday()（(ordinal-1)%7）で曜日を出す。
    # date_label を曜日まで含めて固定し、通日→曜日の対応が壊れたら落ちるようにする。
    # 紀元前1年12月31日（天文年0の大晦日）の翌日が 西暦1年1月1日(月) なので、この日は日曜。
    assert D.calculate(-1, 12, 31, date(1, 1, 1))["date_label"] == "BC1年12月31日 (日)"


def test_is_valid_date_zero_and_negative_month_day():
    # 0 以下の月・日は暦上存在しない。サーバーは ?month=-1&day=0 を int() で通すので実際に到達しうる。
    assert D.is_valid_date(2026, 1, 0) is False
    assert D.is_valid_date(2026, 0, 1) is False
    assert D.is_valid_date(2026, -1, 1) is False
    assert D.is_valid_date(2026, 1, -1) is False
    assert D.calculate(2026, 1, 0, TODAY)["ok"] is False
    assert D.calculate(2026, -1, 1, TODAY)["ok"] is False


def test_proleptic_date_rsub_raises():
    # 規約は「target（_ProlepticDate が来うる側）を減算の左辺に置く」。逆向き（date 左辺）は
    # __rsub__ を持たないので TypeError になる。この規約を実行可能な形で固定する。
    with pytest.raises(TypeError):
        date(1, 1, 1) - D._ProlepticDate(1)


def test_calculate_return_dict_keys_are_the_contract():
    # 戻り辞書のキー集合は API（DateCalc_server）と HTML が共有する契約。
    # キー名を足し引きしたら落ちるように固定する。
    assert set(D.calculate(2026, 6, 3, TODAY)) == {"ok", "date_label", "diff", "diff_label", "cls"}
    assert set(D.calculate(2021, 2, 29, TODAY)) == {"ok", "error"}          # 存在しない日付
    assert set(D.calculate(D.MAX_HIST_YEAR + 1, 1, 1, TODAY)) == {"ok", "error"}  # 範囲外


def test_html_constants_match_python():
    # HTML 側の入力補助定数は Python 側（仕様の唯一の基準）と一致していなければならない。
    # 二重定義のドリフトを検知する（HTML だけ書き換えたらここで落ちる）。
    html_path = os.path.join(os.path.dirname(__file__), "..", "static", "DateCalc.html")
    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    def const(name, pattern):
        m = re.search(rf"const {name}\s*=\s*({pattern})", html)
        assert m, f"HTML に const {name} が見つからない"
        return m.group(1)

    assert int(const("MIN_YEAR", r"-?\d+")) == D.MIN_HIST_YEAR
    assert int(const("MAX_YEAR", r"-?\d+")) == D.MAX_HIST_YEAR
    assert ast.literal_eval(const("WEEKDAYS", r"\[[^\]]*\]")) == D.WEEKDAYS
