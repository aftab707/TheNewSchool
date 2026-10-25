"""app/calendar_utils.py — Business-day helpers.

Only Saturday and Sunday are excluded by default.
French public holidays are listed but their enforcement is controlled by
SKIP_FRENCH_HOLIDAYS in config (stretch goal, disabled by default).
"""
from __future__ import annotations

from datetime import date, timedelta


# French national holidays (fixed dates only; moveable feasts not included)
# Stretch goal: add Easter-derived dates.
_FRENCH_HOLIDAYS: set[tuple[int, int]] = {
    (1, 1),   # Jour de l'An
    (5, 1),   # Fête du Travail
    (5, 8),   # Victoire 1945
    (7, 14),  # Fête Nationale
    (8, 15),  # Assomption
    (11, 1),  # Toussaint
    (11, 11), # Armistice
    (12, 25), # Noël
}


def is_business_day(d: date, skip_holidays: bool = False) -> bool:
    """Return True if *d* is a Monday–Friday (and not a French holiday when enabled)."""
    if d.weekday() >= 5:   # 5 = Saturday, 6 = Sunday
        return False
    if skip_holidays and (d.month, d.day) in _FRENCH_HOLIDAYS:
        return False
    return True


def next_business_day(d: date, days: int = 1, skip_holidays: bool = False) -> date:
    """Return the date *days* business days after *d* (not counting *d* itself).

    Examples
    --------
    >>> from datetime import date
    >>> next_business_day(date(2026, 7, 17), 1)   # Friday → Monday
    datetime.date(2026, 7, 20)
    """
    if days <= 0:
        raise ValueError("days must be >= 1")
    current = d
    counted = 0
    while counted < days:
        current += timedelta(days=1)
        if is_business_day(current, skip_holidays=skip_holidays):
            counted += 1
    return current
