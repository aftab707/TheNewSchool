"""app/scoring.py — Pure scoring functions for lead prioritisation.

All weights and thresholds come from config.py.
Every function is pure: takes data + today, returns data.  No DB access.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app import config
from app.models import ReasonChip


# ---------------------------------------------------------------------------
# Value score (0–100)
# ---------------------------------------------------------------------------

def compute_value(lead: dict[str, Any]) -> float:
    """Return the value score (0–100) measuring how worth this lead is."""
    value = lead["chaleur"] * 10.0

    last_outcome = lead.get("last_outcome") or ""
    if last_outcome == "interested":
        value += config.VALUE_BONUS_INTERESTED
    if last_outcome == "callback_requested":
        value += config.VALUE_BONUS_CALLBACK

    funding = lead.get("funding_status", "unknown")
    if funding in config.FUNDING_PATH_STATUSES:
        value += config.VALUE_BONUS_FUNDING_PATH

    return min(value, config.VALUE_MAX)


# ---------------------------------------------------------------------------
# Urgency score (0–100)
# ---------------------------------------------------------------------------

def compute_urgency(lead: dict[str, Any], today: date) -> float:
    """Return the urgency score (0–100) measuring time-criticality."""
    nfd_raw = lead.get("next_followup_date")
    if not nfd_raw:
        return 0.0

    nfd = date.fromisoformat(nfd_raw)
    d = (today - nfd).days   # positive = overdue, negative = in the future

    if d >= 0:
        # Due today or overdue
        urgency = config.URGENCY_DUE_TODAY + min(
            config.URGENCY_MAX - config.URGENCY_DUE_TODAY,
            d * config.URGENCY_PER_OVERDUE_DAY,
        )
    else:
        # Due in the future: k = days until due
        k = -d
        urgency = max(0, config.URGENCY_FUTURE_BASE - k * config.URGENCY_PER_FUTURE_DAY)

    return float(urgency)


# ---------------------------------------------------------------------------
# Reason chips
# ---------------------------------------------------------------------------

def build_reason_chips(
    lead: dict[str, Any],
    today: date,
    value: float,
    urgency: float,
) -> list[ReasonChip]:
    """Return human-readable explanation chips for why this lead is ranked here."""
    chips: list[ReasonChip] = []
    chaleur = lead["chaleur"]
    call_count = lead["call_count"]
    status = lead.get("status", "new")
    last_outcome = lead.get("last_outcome") or ""
    consecutive_na = lead.get("consecutive_no_answer", 0)
    funding = lead.get("funding_status", "unknown")

    # HOT lead chip
    if chaleur >= config.HOT_CHALEUR_THRESHOLD:
        chips.append(ReasonChip(
            code="HOT",
            label_fr=f"Chaleur {chaleur}/10",
            label_en=f"Heat {chaleur}/10",
            weight=chaleur * 10.0,
        ))

    # Overdue / urgency
    if lead.get("next_followup_date"):
        nfd = date.fromisoformat(lead["next_followup_date"])
        d = (today - nfd).days
        if d > 0:
            chips.append(ReasonChip(
                code="OVERDUE",
                label_fr=f"{d} jour{'s' if d > 1 else ''} de retard",
                label_en=f"{d} day{'s' if d > 1 else ''} overdue",
                weight=urgency,
            ))
        elif d == 0:
            chips.append(ReasonChip(
                code="DUE_TODAY",
                label_fr="À contacter aujourd'hui",
                label_en="Due today",
                weight=urgency,
            ))

    # Forgotten hot lead
    if (chaleur >= config.HOT_CHALEUR_THRESHOLD
            and call_count == 1
            and status in ("new", "contacting")):
        chips.append(ReasonChip(
            code="FORGOTTEN_HOT",
            label_fr="Lead chaud : un seul appel",
            label_en="Hot lead, only 1 call",
            weight=config.BONUS_FORGOTTEN_HOT,
        ))

    # Callback promised
    if last_outcome == "callback_requested":
        chips.append(ReasonChip(
            code="CALLBACK",
            label_fr="Rappel demandé",
            label_en="Callback requested",
            weight=config.BONUS_CALLBACK_OVERDUE,
        ))

    # Funding pending
    if funding in config.FUNDING_PATH_STATUSES or status == "funding":
        chips.append(ReasonChip(
            code="FUNDING_PENDING",
            label_fr="Financement en attente",
            label_en="Funding pending",
            weight=config.VALUE_BONUS_FUNDING_PATH,
        ))

    # Fatigue
    if consecutive_na >= config.FATIGUE_THRESHOLD:
        chips.append(ReasonChip(
            code="FATIGUE",
            label_fr=f"{consecutive_na} appels sans réponse — essayer un e-mail",
            label_en=f"{consecutive_na} unanswered calls — try email",
            weight=-(1 - config.FATIGUE_MULTIPLIER) * 100,
        ))

    # Stop rule
    if _is_at_stop_rule(lead):
        chips.append(ReasonChip(
            code="STOP",
            label_fr="5 tentatives — passer en nurture",
            label_en="5 attempts, no contact — move to nurture",
            weight=-50,
        ))

    return chips


# ---------------------------------------------------------------------------
# Stop rule helper
# ---------------------------------------------------------------------------

def _is_at_stop_rule(lead: dict[str, Any]) -> bool:
    """Return True if the lead has reached the stop rule threshold."""
    call_count = lead["call_count"]
    last_outcome = lead.get("last_outcome") or ""
    # Check the lead has never had a real conversation
    # (We use last_outcome as a proxy; ideally we'd check full history)
    real_outcomes = {"interested", "callback_requested", "needs_funding_info"}
    return call_count >= config.STOP_RULE_CALLS and last_outcome not in real_outcomes


# ---------------------------------------------------------------------------
# Priority score
# ---------------------------------------------------------------------------

def compute_priority(lead: dict[str, Any], today: date) -> tuple[float, float, float, list[ReasonChip]]:
    """Return (priority, value, urgency, reasons) for a lead.

    priority = WEIGHT_VALUE * value + WEIGHT_URGENCY * urgency + bonuses
    Fatigue multiplier is applied. Result is clamped to 0–100.
    """
    value = compute_value(lead)
    urgency = compute_urgency(lead, today)

    priority = config.WEIGHT_VALUE * value + config.WEIGHT_URGENCY * urgency

    # Bonuses
    chaleur = lead["chaleur"]
    call_count = lead["call_count"]
    status = lead.get("status", "new")
    last_outcome = lead.get("last_outcome") or ""
    consecutive_na = lead.get("consecutive_no_answer", 0)

    # Forgotten hot lead bonus
    if (chaleur >= config.HOT_CHALEUR_THRESHOLD
            and call_count == 1
            and status in ("new", "contacting")):
        priority += config.BONUS_FORGOTTEN_HOT

    # Callback overdue bonus
    if last_outcome == "callback_requested":
        if lead.get("next_followup_date"):
            nfd = date.fromisoformat(lead["next_followup_date"])
            if today >= nfd:
                priority += config.BONUS_CALLBACK_OVERDUE

    # Fatigue penalty (multiplicative)
    if consecutive_na >= config.FATIGUE_THRESHOLD:
        priority *= config.FATIGUE_MULTIPLIER

    priority = max(0.0, min(100.0, priority))

    reasons = build_reason_chips(lead, today, value, urgency)
    return round(priority, 2), round(value, 2), round(urgency, 2), reasons


def should_exclude_from_queue(lead: dict[str, Any]) -> bool:
    """Return True if the lead must not appear in the work queue."""
    if lead.get("status") in ("enrolled", "lost"):
        return True
    if _is_at_stop_rule(lead):
        return True
    return False
