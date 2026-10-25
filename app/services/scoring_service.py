"""
Scoring engine service implementing pure prioritisation logic (Moteur de scoring implémentant la logique pure de priorité).
Pure functions with no database side effects (Fonctions pures sans accès direct à la base de données).
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.core import config
from app.models.schemas import ReasonChip


# ---------------------------------------------------------------------------
# Value Calculation (Calcul de la valeur du prospect)
# ---------------------------------------------------------------------------

def compute_value(lead: dict[str, Any]) -> float:
    """
    Calculate commercial value score between 0 and 100 (Calcul du score de valeur commerciale de 0 à 100).
    Based on warmth level plus qualifying signals (Basé sur le niveau de chaleur plus les signaux d'intérêt).
    """
    value = lead["chaleur"] * 10.0

    last_outcome = lead.get("last_outcome") or ""
    # Bonus if prospect expressed direct interest (Bonus si le prospect a manifesté un intérêt direct)
    if last_outcome == "interested":
        value += config.VALUE_BONUS_INTERESTED

    # Bonus if prospect asked for a callback (Bonus si le prospect a demandé à être rappelé)
    if last_outcome == "callback_requested":
        value += config.VALUE_BONUS_CALLBACK

    # Bonus if eligible financing scheme identified (Bonus si un financement éligible comme le CPF est identifié)
    funding = lead.get("funding_status", "unknown")
    if funding in config.FUNDING_PATH_STATUSES:
        value += config.VALUE_BONUS_FUNDING_PATH

    # Cap value at 100 maximum (Plafonne le score de valeur à 100 maximum)
    return min(value, config.VALUE_MAX)


# ---------------------------------------------------------------------------
# Urgency Calculation (Calcul de l'urgence temporelle de rappel)
# ---------------------------------------------------------------------------

def compute_urgency(lead: dict[str, Any], today: date) -> float:
    """
    Calculate urgency score between 0 and 100 (Calcul du score d'urgence de 0 à 100).
    Higher score means more urgent to contact today (Un score plus élevé signifie un contact plus urgent aujourd'hui).
    """
    nfd_raw = lead.get("next_followup_date")
    if not nfd_raw:
        return 0.0

    nfd = date.fromisoformat(nfd_raw)
    d = (today - nfd).days  # Positive = overdue, Negative = in future (Positif = en retard, Négatif = futur)

    if d >= 0:
        # Due today or overdue: starts at 60, increases by 5/day up to 100 (Prévu aujourd'hui ou en retard : base 60, +5/jour jusqu'à 100)
        urgency = config.URGENCY_DUE_TODAY + min(
            config.URGENCY_MAX - config.URGENCY_DUE_TODAY,
            d * config.URGENCY_PER_OVERDUE_DAY,
        )
    else:
        # Due in the future: decays to 0 (Prévu dans le futur : décroît rapidement vers 0)
        k = -d
        urgency = max(0, config.URGENCY_FUTURE_BASE - k * config.URGENCY_PER_FUTURE_DAY)

    return float(urgency)


# ---------------------------------------------------------------------------
# Reason Chips Generation (Génération des badges explicatifs 'Pourquoi ce lead')
# ---------------------------------------------------------------------------

def build_reason_chips(
    lead: dict[str, Any],
    today: date,
    value: float,
    urgency: float,
) -> list[ReasonChip]:
    """
    Build human-readable reason chips explaining the rank (Construire des badges explicatifs compréhensibles par les humains).
    """
    chips: list[ReasonChip] = []
    chaleur = lead["chaleur"]
    call_count = lead["call_count"]
    status = lead.get("status", "new")
    last_outcome = lead.get("last_outcome") or ""
    consecutive_na = lead.get("consecutive_no_answer", 0)
    funding = lead.get("funding_status", "unknown")

    # High warmth badge (Badge prospect très chaud)
    if chaleur >= config.HOT_CHALEUR_THRESHOLD:
        chips.append(ReasonChip(
            code="HOT",
            label_fr=f"Chaleur {chaleur}/10",
            label_en=f"Heat {chaleur}/10",
            weight=chaleur * 10.0,
        ))

    # Overdue delay badge (Badge de retard de rappel)
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

    # Forgotten hot lead: high chaleur but only 1 call attempt (Lead chaud oublié : forte chaleur mais un seul appel tenté)
    if (chaleur >= config.HOT_CHALEUR_THRESHOLD
            and call_count == 1
            and status in ("new", "contacting")):
        chips.append(ReasonChip(
            code="FORGOTTEN_HOT",
            label_fr="Lead chaud : un seul appel",
            label_en="Hot lead, only 1 call",
            weight=config.BONUS_FORGOTTEN_HOT,
        ))

    # Scheduled callback badge (Badge rappel promis au prospect)
    if last_outcome == "callback_requested":
        chips.append(ReasonChip(
            code="CALLBACK",
            label_fr="Rappel demandé",
            label_en="Callback requested",
            weight=config.BONUS_CALLBACK_OVERDUE,
        ))

    # Funding dossier pending (Badge dossier de financement en cours d'instruction)
    if funding in config.FUNDING_PATH_STATUSES or status == "funding":
        chips.append(ReasonChip(
            code="FUNDING_PENDING",
            label_fr="Financement en attente",
            label_en="Funding pending",
            weight=config.VALUE_BONUS_FUNDING_PATH,
        ))

    # Contact fatigue warning (Alerte de fatigue : trop de tentatives infructueuses)
    if consecutive_na >= config.FATIGUE_THRESHOLD:
        chips.append(ReasonChip(
            code="FATIGUE",
            label_fr=f"{consecutive_na} appels sans réponse — essayer un e-mail",
            label_en=f"{consecutive_na} unanswered calls — try email",
            weight=-(1 - config.FATIGUE_MULTIPLIER) * 100,
        ))

    # Stop rule suggestion (Suggestion d'abandon après 5 échecs consécutifs)
    if _is_at_stop_rule(lead):
        chips.append(ReasonChip(
            code="STOP",
            label_fr="5 tentatives — passer en nurture",
            label_en="5 attempts, no contact — move to nurture",
            weight=-50,
        ))

    return chips


# ---------------------------------------------------------------------------
# Stop Rule Logic (Règle d'arrêt des relances stériles)
# ---------------------------------------------------------------------------

def _is_at_stop_rule(lead: dict[str, Any]) -> bool:
    """
    Check if lead reached 5 calls without any real conversation (Vérifie si le lead a atteint 5 appels sans véritable échange).
    """
    call_count = lead["call_count"]
    last_outcome = lead.get("last_outcome") or ""
    real_outcomes = {"interested", "callback_requested", "needs_funding_info"}
    return call_count >= config.STOP_RULE_CALLS and last_outcome not in real_outcomes


# ---------------------------------------------------------------------------
# Global Priority Score Calculation (Calcul du score de priorité globale)
# ---------------------------------------------------------------------------

def compute_priority(lead: dict[str, Any], today: date) -> tuple[float, float, float, list[ReasonChip]]:
    """
    Calculate combined priority: 55% Value + 45% Urgency + Bonuses (Calcul de la priorité : 55% Valeur + 45% Urgence + Bonus).
    Applies fatigue penalty if calls keep going unanswered (Applique une pénalité si les appels restent sans réponse).
    """
    value = compute_value(lead)
    urgency = compute_urgency(lead, today)

    # Weighted baseline formula (Formule de base pondérée)
    priority = config.WEIGHT_VALUE * value + config.WEIGHT_URGENCY * urgency

    chaleur = lead["chaleur"]
    call_count = lead["call_count"]
    status = lead.get("status", "new")
    last_outcome = lead.get("last_outcome") or ""
    consecutive_na = lead.get("consecutive_no_answer", 0)

    # Apply forgotten hot lead boost (Appliquer le bonus pour lead chaud oublié)
    if (chaleur >= config.HOT_CHALEUR_THRESHOLD
            and call_count == 1
            and status in ("new", "contacting")):
        priority += config.BONUS_FORGOTTEN_HOT

    # Apply overdue callback bonus (Appliquer le bonus pour rappel promis en retard)
    if last_outcome == "callback_requested":
        if lead.get("next_followup_date"):
            nfd = date.fromisoformat(lead["next_followup_date"])
            if today >= nfd:
                priority += config.BONUS_CALLBACK_OVERDUE

    # Apply fatigue penalty multiplier (Appliquer le coefficient réducteur de fatigue)
    if consecutive_na >= config.FATIGUE_THRESHOLD:
        priority *= config.FATIGUE_MULTIPLIER

    # Clamp priority between 0.0 and 100.0 (Borner la priorité entre 0.0 et 100.0)
    priority = max(0.0, min(100.0, priority))

    reasons = build_reason_chips(lead, today, value, urgency)
    return round(priority, 2), round(value, 2), round(urgency, 2), reasons


def should_exclude_from_queue(lead: dict[str, Any]) -> bool:
    """
    Check if a lead should be hidden from the active work queue (Détermine si un lead doit être masqué de la file d'appels).
    Closed leads (enrolled, lost) or dead leads reaching stop rule are hidden (Les leads clos ou ayant atteint le stop rule sont masqués).
    """
    if lead.get("status") in ("enrolled", "lost"):
        return True
    if _is_at_stop_rule(lead):
        return True
    return False
