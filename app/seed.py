"""app/seed.py — CSV import + deterministic mock history generation.

Usage:
    python -m app.seed --csv data/Grid_view.csv [--db crm.db]

Idempotent: re-running will upsert (not duplicate) leads.
Mock data is generated with random.Random(42) for full reproducibility.
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import date, timedelta
from typing import Any

from app.config import get_today, cadence_days
from app.calendar_utils import next_business_day
from app.db import init_db, DB_PATH
from app.repository import upsert_lead, add_interaction, delete_interactions_for_lead
from app.workflow import apply_outcome, REAL_CONVERSATION_OUTCOMES, CLOSED_OUTCOMES


# ---------------------------------------------------------------------------
# Outcome weights by chaleur band (used for deterministic mock generation)
# ---------------------------------------------------------------------------

def _outcome_weights(chaleur: int) -> dict[str, float]:
    """Return sampling weights for outcomes, biased by chaleur."""
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
    # cold
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
    keys = list(weights.keys())
    vals = [weights[k] for k in keys]
    return rng.choices(keys, weights=vals, k=1)[0]


# ---------------------------------------------------------------------------
# Generate mock history for one lead
# ---------------------------------------------------------------------------

def _generate_mock_history(
    lead_data: dict[str, Any],
    rng: random.Random,
    today: date,
) -> dict[str, Any]:
    """Return (updated lead fields, list of interaction dicts)."""
    call_count: int = lead_data["call_count"]
    chaleur: int = lead_data["chaleur"]
    arrived_on = date.fromisoformat(lead_data["arrived_on"])
    rep: str = lead_data["rep"]

    # --- Generate interaction timestamps spread between arrived_on and today ---
    span = (today - arrived_on).days
    if span < 1:
        span = 1

    interactions: list[dict[str, Any]] = []
    status = "new"
    consecutive_na = 0
    last_outcome: str | None = None
    last_contact_date: date | None = None
    next_followup_date: date | None = None
    funding_status = "unknown"

    outcome_weights = _outcome_weights(chaleur)

    for i in range(call_count):
        # Spread calls evenly with some randomness
        offset = int((i + 1) * span / (call_count + 1)) + rng.randint(-2, 2)
        offset = max(0, min(span, offset))
        interaction_date = arrived_on + timedelta(days=offset)
        if interaction_date > today:
            interaction_date = today

        # Choose outcome
        outcome = _weighted_choice(rng, outcome_weights)

        # Don't generate closing outcomes mid-history; only allow on last call
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

        # Update status
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

        # Update consecutive_na
        if outcome in ("no_answer", "voicemail"):
            consecutive_na += 1
        elif outcome in REAL_CONVERSATION_OUTCOMES:
            consecutive_na = 0

    # --- Compute next follow-up using real cadence ---
    if last_outcome in CLOSED_OUTCOMES or status in ("enrolled", "lost"):
        next_followup_date = None
    elif last_contact_date:
        days_since = (today - last_contact_date).days
        # Vary last contact: 0–20 days before today
        last_contact_offset = rng.randint(0, min(20, days_since)) if days_since > 0 else 0
        last_contact_date = today - timedelta(days=last_contact_offset)

        if last_outcome == "callback_requested":
            # Random near-future or overdue callback
            delta = rng.randint(-3, 5)
            candidate = today + timedelta(days=delta)
            next_followup_date = candidate
        elif last_outcome == "interested":
            next_followup_date = next_business_day(last_contact_date, 2)
        elif last_outcome == "needs_funding_info":
            next_followup_date = next_business_day(last_contact_date, 3)
        else:
            next_followup_date = next_business_day(
                last_contact_date, cadence_days(chaleur)
            )
    else:
        # No contacts yet — set follow-up from arrived_on
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


# ---------------------------------------------------------------------------
# CSV import
# ---------------------------------------------------------------------------

def import_csv(csv_path: str, db_path: str = DB_PATH) -> dict[str, Any]:
    """Import leads from the CSV and generate mock history.

    Returns a report dict.
    """
    import csv

    init_db(db_path)

    today = get_today()
    rng = random.Random(42)

    ok = 0
    skipped = 0
    skipped_reasons: list[str] = []
    rep_counts: dict[str, int] = {}
    hot_one_call = 0

    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    for i, row in enumerate(rows, start=2):  # row 1 is header
        try:
            email = row.get("Mail", "").strip()
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

            # Validate chaleur
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

            # Parse arrival date
            from datetime import datetime as dt
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

            # Generate mock history
            updates, interactions = _generate_mock_history(lead_data, rng, today)
            lead_data.update(updates)

            # Upsert lead
            saved = upsert_lead(lead_data, db_path)

            # Reset and re-insert interactions
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


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Smart CRM database from CSV.")
    parser.add_argument("--csv", required=True, help="Path to Grid_view.csv")
    parser.add_argument("--db", default=DB_PATH, help="Path to SQLite database")
    args = parser.parse_args()

    print(f"\n[SEED] Seeding database: {args.db}")
    print(f"   CSV: {args.csv}")
    print(f"   Reference date (today): {get_today()}\n")

    report = import_csv(args.csv, args.db)

    print(f"[OK] Imported:  {report['ok']} leads")
    print(f"[!]  Skipped:   {report['skipped']} rows")

    print("\n[STATS] Leads per rep:")
    for rep, count in sorted(report["rep_counts"].items()):
        print(f"   {rep}: {count}")

    print(f"\n[HOT] Hot leads (Chaleur >= 7) with only 1 call: {report['hot_one_call']}")
    print("   --> These are the highest-priority forgotten leads!")

    if report["skipped_reasons"]:
        print("\n[SKIP] Skipped rows:")
        for reason in report["skipped_reasons"]:
            print(f"   {reason}")

    print("\n[DONE] Run: uvicorn app.main:app --reload\n")


if __name__ == "__main__":
    main()
