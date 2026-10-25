"""
Workflow engine service managing automated status transitions and follow-up scheduling (Moteur de workflow gérant les transitions de statut et la planification automatique des relances).
Pure business logic functions (Fonctions pures de logique métier sans dépendance externe).
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.core import config
from app.services.calendar_service import next_business_day


# Outcomes confirming real two-way conversation (Résultats d'appel confirmant un échange réel avec le prospect)
REAL_CONVERSATION_OUTCOMES = frozenset({
    "interested",
    "callback_requested",
    "needs_funding_info",
})

# Final closing outcomes (Résultats entraînant la clôture définitive du dossier)
CLOSED_OUTCOMES = frozenset({"not_interested", "wrong_number", "enrolled"})


def compute_next_followup(
    chaleur: int,
    outcome: str,
    callback_at: str | None,
    today: date,
) -> date | None:
    """
    Compute next contact date based on call outcome and lead warmth (Calculer la date du prochain contact selon le résultat de l'appel et la chaleur).
    Returns None if the lead is closed (Retourne None si le dossier est clos).
    """
    # No follow-up if lead is closed (Aucune relance si le lead est clos)
    if outcome in CLOSED_OUTCOMES:
        return None

    # Exact date requested by prospect (Date et heure précises demandées par le prospect)
    if outcome == "callback_requested":
        if callback_at:
            try:
                date_part = callback_at.split("T")[0]
                return date.fromisoformat(date_part)
            except Exception:
                pass
        return next_business_day(today, 1)

    # 2 business days to send quote/info (2 jours ouvrés pour envoyer devis et programme)
    if outcome == "interested":
        days = config.OUTCOME_FOLLOWUP_DAYS.get("interested", 2)
        return next_business_day(today, days)  # type: ignore[arg-type]

    # 3 business days for funding application review (3 jours ouvrés pour le suivi du dossier de financement)
    if outcome == "needs_funding_info":
        days = config.OUTCOME_FOLLOWUP_DAYS.get("needs_funding_info", 3)
        return next_business_day(today, days)  # type: ignore[arg-type]

    # For no-answer/voicemail: retry in 1 day for hot leads, otherwise standard cadence (Pour répondeur/sans réponse : J+1 pour les chauds, sinon cadence standard)
    if chaleur >= 8:
        return next_business_day(today, config.NO_ANSWER_HOT_DAYS)
    return next_business_day(today, config.cadence_days(chaleur))


def new_status_after_outcome(current_status: str, outcome: str) -> str:
    """
    Determine the updated pipeline stage following a call (Déterminer la nouvelle étape du pipeline après un appel).
    """
    if outcome == "enrolled":
        return "enrolled"  # Won (Gagné)

    if outcome in ("not_interested", "wrong_number"):
        return "lost"      # Lost (Perdu)

    if outcome in ("interested", "callback_requested"):
        # Promote to qualified if earlier in funnel (Faire progresser vers Qualifié si le lead était au début du tunnel)
        if current_status in ("new", "contacting"):
            return "qualified"
        return current_status

    if outcome == "needs_funding_info":
        return "funding"   # In funding dossier phase (En cours de montage de financement)

    # If first call attempt went unanswered, promote from new to contacting (Si première tentative sans réponse, passe de Nouveau à En contact)
    if current_status == "new":
        return "contacting"

    return current_status


def apply_outcome(lead: dict[str, Any], request: dict[str, Any], today: date) -> dict[str, Any]:
    """
    Apply call outcome to a lead and compute all updated attributes (Appliquer le résultat d'un appel à un prospect et calculer les modifications).
    Returns a dictionary of updated fields ready to persist (Retourne le dictionnaire des champs mis à jour).
    """
    outcome: str = request["outcome"]
    callback_at: str | None = request.get("callback_at")
    funding_status: str | None = request.get("funding_status")
    lost_reason: str | None = request.get("lost_reason")

    chaleur: int = lead["chaleur"]
    current_status: str = lead["status"]
    consecutive_na: int = lead.get("consecutive_no_answer", 0)

    # 1. Update pipeline status (Mise à jour du statut dans le pipeline)
    new_status = new_status_after_outcome(current_status, outcome)

    # 2. Automatically compute next follow-up date (Calcul automatique de la date de relance)
    next_date = compute_next_followup(chaleur, outcome, callback_at, today)

    # 3. Extract time part if callback requested (Extraction de l'heure si un rappel précis est prévu)
    next_time: str | None = None
    if outcome == "callback_requested" and callback_at and "T" in callback_at:
        next_time = callback_at.split("T")[1][:5]

    # 4. Track consecutive unanswered calls for fatigue logic (Suivi des échecs consécutifs pour la détection de fatigue)
    if outcome in ("no_answer", "voicemail"):
        consecutive_na += 1
    elif outcome in REAL_CONVERSATION_OUTCOMES:
        consecutive_na = 0  # Reset on real conversation (Remise à zéro dès qu'un échange a lieu)

    updates: dict[str, Any] = {
        "status":                new_status,
        "last_contact_date":     today.isoformat(),
        "next_followup_date":    next_date.isoformat() if next_date else None,
        "next_followup_time":    next_time,
        "last_outcome":          outcome,
        "consecutive_no_answer": consecutive_na,
        "call_count":            lead["call_count"] + 1,
    }

    if funding_status is not None:
        updates["funding_status"] = funding_status

    if lost_reason is not None:
        updates["lost_reason"] = lost_reason

    return updates


def suggested_channel(consecutive_no_answer: int) -> str:
    """
    Suggest an alternative communication channel after multiple phone failures (Suggérer un canal alternatif après plusieurs échecs téléphoniques).
    Suggest email after 2+ missed calls (Suggère l'e-mail après 2 appels sans réponse ou plus).
    """
    if consecutive_no_answer >= 2:
        return "email"
    return "call"
