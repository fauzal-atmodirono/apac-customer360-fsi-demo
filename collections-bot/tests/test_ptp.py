import ptp


def test_parse_ptp_fields_valid():
    date, amount = ptp.parse_ptp_fields({"ptp_date": "2026-07-10", "ptp_amount": 500})
    assert date == "2026-07-10"
    assert amount == 500.0


def test_parse_ptp_fields_coerces_string_amount():
    date, amount = ptp.parse_ptp_fields({"ptp_date": "2026-07-10", "ptp_amount": "350.50"})
    assert amount == 350.5


def test_parse_ptp_fields_rejects_garbage_date():
    date, amount = ptp.parse_ptp_fields({"ptp_date": "minggu depan", "ptp_amount": 100})
    assert date is None
    assert amount == 100.0


def test_parse_ptp_fields_missing_keys():
    assert ptp.parse_ptp_fields({}) == (None, None)


def test_parse_ptp_fields_non_numeric_amount():
    date, amount = ptp.parse_ptp_fields({"ptp_date": "2026-07-10", "ptp_amount": "lima ratus"})
    assert date == "2026-07-10"
    assert amount is None


def test_default_promise_date_adds_three_days():
    assert ptp.default_promise_date("2026-07-06") == "2026-07-09"


def test_default_promise_date_crosses_month():
    assert ptp.default_promise_date("2026-07-30") == "2026-08-02"


def test_is_suppressed_active_future():
    assert ptp.is_suppressed({"status": "ACTIVE", "promise_date": "2026-07-10"}, "2026-07-06") is True


def test_is_suppressed_active_today():
    # A promise due today still suppresses — give the debtor the whole day to pay.
    assert ptp.is_suppressed({"status": "ACTIVE", "promise_date": "2026-07-06"}, "2026-07-06") is True


def test_is_suppressed_active_past_due():
    assert ptp.is_suppressed({"status": "ACTIVE", "promise_date": "2026-07-05"}, "2026-07-06") is False


def test_is_suppressed_non_active_statuses():
    for status in ("KEPT", "BROKEN", "CANCELLED"):
        assert ptp.is_suppressed({"status": status, "promise_date": "2026-07-10"}, "2026-07-06") is False


def test_is_suppressed_none():
    assert ptp.is_suppressed(None, "2026-07-06") is False


def test_normalize_future_date_rolls_past_year_to_upcoming():
    # Debtor names "24 Julai"; the model guessed last year -> roll to the upcoming one.
    assert ptp.normalize_future_date("2025-07-24", "2026-07-07") == "2026-07-24"


def test_normalize_future_date_rolls_multiple_years_forward():
    assert ptp.normalize_future_date("2023-07-24", "2026-07-07") == "2026-07-24"


def test_normalize_future_date_keeps_already_future_date():
    assert ptp.normalize_future_date("2026-07-24", "2026-07-07") == "2026-07-24"


def test_normalize_future_date_today_is_kept():
    # A promise due today is still valid — the whole promise day counts.
    assert ptp.normalize_future_date("2026-07-07", "2026-07-07") == "2026-07-07"


def test_normalize_future_date_rolls_passed_day_this_year_to_next_year():
    # Today is 2026-07-07; "5 Julai" already went by this year -> next year's occurrence.
    assert ptp.normalize_future_date("2026-07-05", "2026-07-07") == "2027-07-05"


def test_normalize_future_date_handles_leap_day():
    # 29 Feb rolled into a non-leap year clamps to 28 Feb rather than raising.
    assert ptp.normalize_future_date("2024-02-29", "2026-07-07") == "2027-02-28"


def test_normalize_future_date_passes_through_garbage():
    assert ptp.normalize_future_date("minggu depan", "2026-07-07") == "minggu depan"
    assert ptp.normalize_future_date(None, "2026-07-07") is None
