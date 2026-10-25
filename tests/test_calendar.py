"""tests/test_calendar.py — Unit tests for business-day helpers."""
import os
import pytest
from datetime import date

from app.services.calendar_service import next_business_day, is_business_day


class TestIsBusinessDay:
    def test_monday_is_business_day(self):
        assert is_business_day(date(2026, 7, 20)) is True  # Monday

    def test_saturday_is_not(self):
        assert is_business_day(date(2026, 7, 18)) is False  # Saturday

    def test_sunday_is_not(self):
        assert is_business_day(date(2026, 7, 19)) is False  # Sunday

    def test_french_holiday_excluded_when_flag_on(self):
        # 14 July 2026 = Wednesday (Fête Nationale)
        assert is_business_day(date(2026, 7, 14), skip_holidays=True) is False

    def test_french_holiday_included_when_flag_off(self):
        assert is_business_day(date(2026, 7, 14), skip_holidays=False) is True


class TestNextBusinessDay:
    def test_monday_plus_1_is_tuesday(self):
        assert next_business_day(date(2026, 7, 20), 1) == date(2026, 7, 21)

    def test_friday_plus_1_is_monday(self):
        # Friday 17 Jul → Monday 20 Jul
        assert next_business_day(date(2026, 7, 17), 1) == date(2026, 7, 20)

    def test_friday_plus_2_is_tuesday(self):
        assert next_business_day(date(2026, 7, 17), 2) == date(2026, 7, 21)

    def test_month_boundary(self):
        # 30 July (Thursday) + 3 = 4 Aug (Tuesday)
        assert next_business_day(date(2026, 7, 30), 3) == date(2026, 8, 4)

    def test_weekend_start(self):
        # Saturday + 1 business day = Monday
        assert next_business_day(date(2026, 7, 18), 1) == date(2026, 7, 20)

    def test_zero_days_raises(self):
        with pytest.raises(ValueError):
            next_business_day(date(2026, 7, 20), 0)
