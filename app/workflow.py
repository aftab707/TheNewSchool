"""app/workflow.py — Pure functions implementing the outcome→update rules.

Every function takes plain data + today and returns plain data.
No DB access, no side effects → trivially testable.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app import config
from app.calendar_utils import next_business_day


# Outcomes that count as a "real conversation"
REAL_CONVERSATION_OUTCOMES = frozenset({
    "interested",
    "callback_requested",
    "needs_funding_info",
})

# Outcomes that close the lead
CLOSED_OUTCOMES = frozenset({"not_interested", "wrong_number", "enrolled"})


def compute_next_followup(
    chaleur: int,
    outcome: str,
    callback_at: str | None,
    today: date,
) -> date | None:
    """Return the next follow-up date based on outcome and chaleur.

    Returns None when the lead should be closed (no further follow-up needed).
    """
    if outcome in CLOSED_OUTCOMES:
        return None

    if outcome == "callback_requested":
        if callback_at:
            # callback_at may be "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM"
            date_part = callback_at.split("T")[0]
            return date.fromisoformat(date_part)
        # Fallback: 1 business day (should not happen — validator enforces callback_at)
        return next_business_day(today, 1)

    if outcome == "interested":
        days = config.OUTCOME_FOLLOWUP_DAYS.get("interested", 2)
        return next_business_day(today, days)  # type: ignore[arg-type]

    if outcome == "needs_funding_info":
        days = config.OUTCOME_FOLLOWUP_DAYS.get("needs_funding_info", 3)
        return next_business_day(today, days)  # type: ignore[arg-type]

    # no_answer / voicemail → cadence, with a 1-day override for hot leads
    if chaleur >= 8:
        return next_business_day(today, config.NO_ANSWER_HOT_DAYS)
    return next_business_day(today, config.cadence_days(chaleur))


def new_status_after_outcome(current_status: str, outcome: str) -> str:
    """Return the new pipeline status given the current status and call outcome."""
    if outcome == "enrolled":
        return "enrolled"
    if outcome in ("not_interested", "wrong_number"):
        return "lost"
    if outcome in ("interested", "callback_requested"):
        # Only promote; don't demote a lead that's already further along
        if current_status in ("new", "contacting"):
            return "qualified"
        return current_status
    if outcome == "needs_funding_info":
        return "funding"
    # no_answer / voicemail
    if current_status == "new":
        return "contacting"
    return current_status


def apply_outcome(lead: dict[str, Any], request: dict[str, Any], today: date) -> dict[str, Any]:
    """Apply a logged outcome to a lead dict and return the updated fields.

    Parameters
    ----------
    lead:
        Current lead data (dict with the same keys as the DB row).
    request:
        Validated log-contact payload as a plain dict:
        {outcome, note, channel, callback_at, funding_status, lost_reason}
    today:
        The reference date (from config.get_today()).

    Returns
    -------
    dict of fields that changed (suitable for SQL UPDATE or dict merge).
    """
    outcome: str = request["outcome"]
    callback_at: str | None = request.get("callback_at")
    funding_status: str | None = request.get("funding_status")
    lost_reason: str | None = request.get("lost_reason")

    chaleur: int = lead["chaleur"]
    current_status: str = lead["status"]
    consecutive_na: int = lead.get("consecutive_no_answer", 0)

    # --- Status transition ---
    new_status = new_status_after_outcome(current_status, outcome)

    # --- Follow-up date ---
    next_date = compute_next_followup(chaleur, outcome, callback_at, today)

    # --- next_followup_time ---
    next_time: str | None = None
    if outcome == "callback_requested" and callback_at and "T" in callback_at:
        next_time = callback_at.split("T")[1][:5]   # "HH:MM"

    # --- Consecutive no-answer counter ---
    if outcome in ("no_answer", "voicemail"):
        consecutive_na += 1
    elif outcome in REAL_CONVERSATION_OUTCOMES:
        consecutive_na = 0
    # closed outcomes: counter irrelevant

    # --- Build update dict ---
    updates: dict[str, Any] = {
        "status":               new_status,
        "last_contact_date":    today.isoformat(),
        "next_followup_date":   next_date.isoformat() if next_date else None,
        "next_followup_time":   next_time,
        "last_outcome":         outcome,
        "consecutive_no_answer": consecutive_na,
        "call_count":           lead["call_count"] + 1,
    }

    if funding_status is not None:
        updates["funding_status"] = funding_status
    if lost_reason is not None:
        updates["lost_reason"] = lost_reason

    return updates


def suggested_channel(consecutive_no_answer: int) -> str:
    """Suggest an alternate channel after repeated no-answers."""
    if consecutive_no_answer >= 2:
        return "email"
    return "call"
