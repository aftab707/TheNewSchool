"""
Seed service for CSV import and deterministic history generation (Service de peuplement pour l'import CSV et la génération d'historique réaliste).
Ensures reproducible demonstrations and test data (Garantit des démonstrations reproductibles et des données de test fiables).
"""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta, datetime as dt
from typing import Any

from app.core.config import get_today, cadence_days, DB_PATH
from app.core.database import init_db
from app.repositories.lead_repository import (
    upsert_lead,
    add_interaction,
    delete_interactions_for_lead,
)
from app.services.calendar_service import next_business_day
from app.services.workflow_service import REAL_CONVERSATION_OUTCOMES, CLOSED_OUTCOMES


def _outcome_weights(chaleur: int) -> dict[str, float]:
    """
    Return call outcome probabilities weighted by lead warmth (Probabilités de résultats d'appel selon la chaleur du lead).
    Hot leads have higher chance of interest; cold leads more likely no-answer (Les leads chauds ont plus de chances d'intérêt).
    """
    if chaleur >= 8:
        return {
            "interested": 0.25,
            "callback_requested": 0.20,
            "no_answer": 0.25,
            "voicemail": 0.15,
            "needs_funding_info": 0.10,
            "not_interested": 0.03,
            "enrolled": 0.02,
        }
    if chaleur >= 5:
        return {
            "interested": 0.15,
            "callback_requested": 0.10,
            "no_answer": 0.35,
            "voicemail": 0.20,
            "needs_funding_info": 0.10,
            "not_interested": 0.07,
            "enrolled": 0.03,
        }
    return {
        "interested": 0.05,
        "callback_requested": 0.05,
        "no_answer": 0.40,
        "voicemail": 0.25,
        "needs_funding_info": 0.05,
        "not_interested": 0.15,
        "enrolled": 0.05,
    }


def _weighted_choice(rng: random.Random, weights: dict[str, float]) -> str:
    """Select random outcome by probability weight (Sélection aléatoire pondérée par les probabilités)."""
    keys = list(weights.keys())
    vals = [weights[k] for k in keys]
    return rng.choices(keys, weights=vals, k=1)[0]


def generate_mock_history(
    lead_data: dict[str, Any],
    rng: random.Random,
    today: date,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    Generate realistic interaction timeline matching call_count and warmth (Générer un historique cohérent avec le nombre d'appels et la chaleur).
    Uses the exact same cadence rules as the live application (Utilise exactement les mêmes règles de cadence que l'application).
    """
    call_count: int = lead_data["call_count"]
    chaleur: int = lead_data["chaleur"]
    arrived_on = date.fromisoformat(lead_data["arrived_on"])
    rep: str = lead_data["rep"]

    span = max(1, (today - arrived_on).days)
    interactions: list[dict[str, Any]] = []
    status = "new"
    consecutive_na = 0
    last_outcome: str | None = None
    last_contact_date: date | None = None
    next_followup_date: date | None = None
    funding_status = "unknown"

    outcome_weights = _outcome_weights(chaleur)

    for i in range(call_count):
        # Distribute calls between arrival date and today (Répartir les appels entre l'arrivée et aujourd'hui)
        offset = int((i + 1) * span / (call_count + 1)) + rng.randint(-2, 2)
        offset = max(0, min(span, offset))
        interaction_date = arrived_on + timedelta(days=offset)
        if interaction_date > today:
            interaction_date = today

        outcome = _weighted_choice(rng, outcome_weights)

        # Do not close a lead in the middle of history (Ne pas clôturer le dossier avant le dernier appel)
        if i < call_count - 1 and outcome in ("not_interested", "wrong_number", "enrolled"):
            outcome = "no_answer"

        interactions.append({
            "at": interaction_date.isoformat() + "T10:00:00",
            "rep": rep,
            "channel": "call",
            "outcome": outcome,
            "note": "",
        })

        last_contact_date = interaction_date
        last_outcome = outcome

        # Update status (Mise à jour du statut)
        if outcome == "enrolled":
            status = "enrolled"
        elif outcome in ("not_interested", "wrong_number"):
            status = "lost"
        elif outcome in ("interested", "callback_requested"):
            if status in ("new", "contacting"):
                status = "qualified"
        elif outcome == "needs_funding_info":
            status = "funding"
            funding_status = rng.choice(["cpf", "opco", "france_travail", "self", "employer"])
        elif outcome in ("no_answer", "voicemail"):
            if status == "new":
                status = "contacting"

        if outcome in ("no_answer", "voicemail"):
            consecutive_na += 1
        elif outcome in REAL_CONVERSATION_OUTCOMES:
            consecutive_na = 0

    # Calculate next follow-up with real application cadence (Calcul de la date de relance selon la cadence réelle)
    if last_outcome in CLOSED_OUTCOMES or status in ("enrolled", "lost"):
        next_followup_date = None
    elif last_contact_date:
        days_since = (today - last_contact_date).days
        last_contact_offset = rng.randint(0, min(20, days_since)) if days_since > 0 else 0
        last_contact_date = today - timedelta(days=last_contact_offset)

        if last_outcome == "callback_requested":
            delta = rng.randint(-3, 5)
            next_followup_date = today + timedelta(days=delta)
        elif last_outcome == "interested":
            next_followup_date = next_business_day(last_contact_date, 2)
        elif last_outcome == "needs_funding_info":
            next_followup_date = next_business_day(last_contact_date, 3)
        else:
            next_followup_date = next_business_day(last_contact_date, cadence_days(chaleur))
    else:
        next_followup_date = next_business_day(arrived_on, cadence_days(chaleur))

    updates: dict[str, Any] = {
        "status": status,
        "last_contact_date": last_contact_date.isoformat() if last_contact_date else None,
        "next_followup_date": next_followup_date.isoformat() if next_followup_date else None,
        "last_outcome": last_outcome,
        "consecutive_no_answer": consecutive_na,
        "funding_status": funding_status,
    }
    return updates, interactions


def import_csv(csv_path: str, db_path: str = DB_PATH) -> dict[str, Any]:
    """
    Import leads from CSV file and seed database (Importer les leads du fichier CSV et peupler la base de données).
    Idempotent operation (Opération idempotente sans duplication).
    """
    init_db(db_path)
    today = get_today()
    rng = random.Random(42)  # Fixed seed for deterministic results (Graine fixe pour résultats déterministes)

    ok = 0
    skipped = 0
    skipped_reasons: list[str] = []
    rep_counts: dict[str, int] = {}
    hot_one_call = 0

    # Handle UTF-8 BOM encoding from Airtable export (Gestion de l'encodage UTF-8 BOM issu d'Airtable)
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    for i, row in enumerate(rows, start=2):
        try:
            email = row.get("Mail", "").strip()
            # Non-strict email validation allowing French accents (Validation tolérante acceptant les accents français)
            if "@" not in email:
                skipped += 1
                skipped_reasons.append(f"Row {i}: invalid email '{email}'")
                continue

            last_name = row.get("Nom", "").strip()
            first_name = row.get("Prénom", "").strip()
            rep = row.get("Commercial", "").strip()
            chaleur_raw = row.get("Chaleur", "").strip()
            arrived_raw = row.get("Date d'arrivée", "").strip()
            call_count_raw = row.get("Nombre d'appel", "0").strip()

            try:
                chaleur = int(chaleur_raw)
            except ValueError:
                skipped += 1
                skipped_reasons.append(f"Row {i}: invalid chaleur '{chaleur_raw}'")
                continue

            if not (0 <= chaleur <= 10):
                skipped += 1
                skipped_reasons.append(f"Row {i}: chaleur out of range {chaleur}")
                continue

            arrived_on = dt.strptime(arrived_raw, "%m/%d/%Y").date().isoformat()
            call_count = max(0, int(call_count_raw))

            lead_data: dict[str, Any] = {
                "email": email,
                "last_name": last_name,
                "first_name": first_name,
                "rep": rep,
                "chaleur": chaleur,
                "arrived_on": arrived_on,
                "call_count": call_count,
                "status": "new",
                "last_contact_date": None,
                "next_followup_date": None,
                "next_followup_time": None,
                "last_outcome": None,
                "consecutive_no_answer": 0,
                "funding_status": "unknown",
                "lost_reason": None,
                "notes": "",
            }

            updates, interactions = generate_mock_history(lead_data, rng, today)
            lead_data.update(updates)

            saved = upsert_lead(lead_data, db_path)

            delete_interactions_for_lead(saved["id"], db_path)
            for interaction in interactions:
                add_interaction({"lead_id": saved["id"], **interaction}, db_path)

            rep_counts[rep] = rep_counts.get(rep, 0) + 1
            if chaleur >= 7 and call_count == 1:
                hot_one_call += 1
            ok += 1

        except Exception as exc:
            skipped += 1
            skipped_reasons.append(f"Row {i}: {exc}")

    return {
        "ok": ok,
        "skipped": skipped,
        "skipped_reasons": skipped_reasons,
        "rep_counts": rep_counts,
        "hot_one_call": hot_one_call,
    }
