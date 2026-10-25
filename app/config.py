"""app/config.py — All tunables for the Smart CRM.
A sales manager can change any number here; tests lock the behaviour.
"""
import os
from datetime import date


# ---------------------------------------------------------------------------
# Reference date
# ---------------------------------------------------------------------------

def get_today() -> date:
    """Return the 'current' date.

    If the environment variable CRM_TODAY is set (format YYYY-MM-DD), use it.
    This is critical: the CSV data is from Apr–Jul 2026, so we default to
    2026-07-20 so the seeded demo looks alive.  Tests set CRM_TODAY to make
    results deterministic.
    """
    raw = os.environ.get("CRM_TODAY", "").strip()
    if raw:
        return date.fromisoformat(raw)
    return date.today()


# ---------------------------------------------------------------------------
# Scoring weights (priority = WEIGHT_VALUE * value + WEIGHT_URGENCY * urgency)
# ---------------------------------------------------------------------------
WEIGHT_VALUE: float = 0.55
WEIGHT_URGENCY: float = 0.45

# Urgency constants
URGENCY_DUE_TODAY: int = 60          # base urgency when follow-up is today
URGENCY_PER_OVERDUE_DAY: int = 5     # added per calendar day overdue
URGENCY_MAX: int = 100
URGENCY_FUTURE_BASE: int = 40        # urgency when due tomorrow
URGENCY_PER_FUTURE_DAY: int = 10     # subtracted per day in the future

# Value bonuses (on top of chaleur * 10)
VALUE_BONUS_INTERESTED: int = 10
VALUE_BONUS_CALLBACK: int = 10
VALUE_BONUS_FUNDING_PATH: int = 5
VALUE_MAX: int = 100

# Priority bonuses / penalties
BONUS_FORGOTTEN_HOT: int = 15       # hot lead with only 1 call
BONUS_CALLBACK_OVERDUE: int = 20    # promised callback is due/overdue
FATIGUE_MULTIPLIER: float = 0.6     # applied when consecutive_no_answer >= 3
FATIGUE_THRESHOLD: int = 3          # consecutive no-answers before fatigue
STOP_RULE_CALLS: int = 5            # calls with no real conversation → nurture

# Chaleur threshold for "hot" (forgotten-hot rule)
HOT_CHALEUR_THRESHOLD: int = 7

# ---------------------------------------------------------------------------
# Follow-up cadence (business days) by Chaleur band
# ---------------------------------------------------------------------------
CADENCE: dict[str, int] = {
    "hot":    1,   # chaleur 8–10
    "warm":   3,   # chaleur 5–7
    "cool":   7,   # chaleur 3–4
    "cold":   14,  # chaleur 0–2
}

def cadence_days(chaleur: int) -> int:
    """Return the default follow-up interval in business days for a chaleur score."""
    if chaleur >= 8:
        return CADENCE["hot"]
    if chaleur >= 5:
        return CADENCE["warm"]
    if chaleur >= 3:
        return CADENCE["cool"]
    return CADENCE["cold"]


# ---------------------------------------------------------------------------
# Outcome-specific follow-up intervals (business days), overriding cadence
# ---------------------------------------------------------------------------
OUTCOME_FOLLOWUP_DAYS: dict[str, int | None] = {
    "interested":         2,
    "needs_funding_info": 3,
    "no_answer":          None,   # use cadence (with hot override below)
    "voicemail":          None,   # same as no_answer
    "callback_requested": None,   # use the date chosen by the rep
    "not_interested":     None,   # lead is closed
    "wrong_number":       None,   # lead is closed
    "enrolled":           None,   # lead is closed
}
NO_ANSWER_HOT_DAYS: int = 1   # override for chaleur >= 8 after no_answer/voicemail

# ---------------------------------------------------------------------------
# Daily call capacity per rep (first N due leads = "À appeler aujourd'hui")
# ---------------------------------------------------------------------------
DAILY_CALL_CAPACITY: int = 15

# Upcoming window shown in queue (days)
UPCOMING_WINDOW_DAYS: int = 7

# ---------------------------------------------------------------------------
# Funding statuses that count as "funding path identified"
# ---------------------------------------------------------------------------
FUNDING_PATH_STATUSES: set[str] = {"cpf", "opco", "france_travail", "employer"}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DB_PATH: str = os.environ.get("CRM_DB_PATH", "crm.db")
