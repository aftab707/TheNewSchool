"""
Calendar utility service for business day operations (Service calendrier pour les calculs en jours ouvrés).
Skips weekends automatically (Ignore automatiquement les samedis et dimanches).
"""
from __future__ import annotations

from datetime import date, timedelta


# Official fixed French public holidays (Jours fériés légaux français à date fixe)
_FRENCH_HOLIDAYS: set[tuple[int, int]] = {
    (1, 1),   # New Year's Day (Jour de l'An)
    (5, 1),   # Labor Day (Fête du Travail)
    (5, 8),   # Victory in Europe 1945 (Victoire 1945)
    (7, 14),  # Bastille Day (Fête Nationale)
    (8, 15),  # Assumption of Mary (Assomption)
    (11, 1),  # All Saints' Day (Toussaint)
    (11, 11), # Armistice 1918 (Armistice)
    (12, 25), # Christmas Day (Noël)
}


def is_business_day(d: date, skip_holidays: bool = False) -> bool:
    """
    Check if a date is a Monday-Friday business day (Vérifie si une date correspond à un jour ouvré du lundi au vendredi).
    """
    # Exclude Saturday (5) and Sunday (6) (Exclut le samedi (5) et le dimanche (6))
    if d.weekday() >= 5:
        return False

    # Optionally exclude French national holidays (Exclut optionnellement les jours fériés français)
    if skip_holidays and (d.month, d.day) in _FRENCH_HOLIDAYS:
        return False

    return True


def next_business_day(d: date, days: int = 1, skip_holidays: bool = False) -> date:
    """
    Calculate the date N business days in the future (Calcule la date N jours ouvrés dans le futur).
    Example: Friday + 1 business day = Monday (Exemple : Vendredi + 1 jour ouvré = Lundi).
    """
    if days <= 0:
        raise ValueError("days must be >= 1 (le nombre de jours doit être supérieur ou égal à 1)")

    current = d
    counted = 0

    while counted < days:
        current += timedelta(days=1)
        if is_business_day(current, skip_holidays=skip_holidays):
            counted += 1

    return current
