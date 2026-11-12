from datetime import UTC

from ecosignal.domain import classify_coverage, parse_iso_datetime


def test_no_records_is_not_classified_as_stability_or_sufficiency():
    assert classify_coverage(0, 3, 3, 30) == "no_usable_data"
    assert classify_coverage(0, 0, 3, 30) == "source_unavailable"


def test_partial_sources_remain_limited_even_when_record_count_is_high():
    assert classify_coverage(100, 2, 3, 30) == "limited"


def test_date_precision_and_utc_are_preserved():
    value, precision, original_timezone = parse_iso_datetime("2024-06-15T12:30:00+03:00")

    assert value is not None
    assert value.tzinfo == UTC
    assert value.hour == 9
    assert precision == "second"
    assert original_timezone == "UTC+03:00"


def test_year_precision_is_not_expanded_into_a_claimed_day():
    value, precision, _ = parse_iso_datetime("2020")

    assert value is not None
    assert (value.year, value.month, value.day) == (2020, 1, 1)
    assert precision == "year"