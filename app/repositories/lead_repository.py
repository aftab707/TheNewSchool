"""
Repository layer handling all SQLite database queries (Couche repository gérant toutes les requêtes SQL SQLite).
Isolates SQL logic from business services (Isole la logique SQL des services métier).
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone, timedelta
from typing import Any, Optional

from app.core.config import DB_PATH, UPCOMING_WINDOW_DAYS
from app.core.database import get_conn


# ---------------------------------------------------------------------------
# Internal Helpers (Fonctions d'aide internes)
# ---------------------------------------------------------------------------

def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert SQLite Row object to python dictionary (Convertir une ligne SQLite en dictionnaire)."""
    return dict(row)


def _now_iso() -> str:
    """Current UTC timestamp in ISO 8601 format (Horodatage UTC actuel au format ISO 8601)."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Lead Query & Persistence (Requêtes et persistance des prospects)
# ---------------------------------------------------------------------------

def get_lead(lead_id: int, db_path: str = DB_PATH) -> Optional[dict[str, Any]]:
    """
    Fetch a single lead by ID (Récupérer un lead par son identifiant unique).
    """
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM leads WHERE id = ?", (lead_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def get_lead_by_email(email: str, db_path: str = DB_PATH) -> Optional[dict[str, Any]]:
    """
    Fetch a single lead by email address (Récupérer un lead par son adresse email).
    """
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM leads WHERE email = ?", (email,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_leads(
    rep: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
    db_path: str = DB_PATH,
) -> list[dict[str, Any]]:
    """
    Filter leads for Kanban board and search view (Filtrer les leads pour le tableau Kanban et la recherche).
    """
    clauses: list[str] = []
    params: list[Any] = []

    # Optional filter by assigned sales rep (Filtre optionnel par commercial)
    if rep:
        clauses.append("rep = ?")
        params.append(rep)

    # Optional filter by pipeline status (Filtre optionnel par statut)
    if status:
        clauses.append("status = ?")
        params.append(status)

    # Optional keyword search in name or email (Recherche textuelle dans le nom ou l'email)
    if q:
        pattern = f"%{q}%"
        clauses.append("(first_name LIKE ? OR last_name LIKE ? OR email LIKE ?)")
        params.extend([pattern, pattern, pattern])

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM leads {where} ORDER BY next_followup_date ASC"

    with get_conn(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def list_leads_for_queue(rep: str, db_path: str = DB_PATH) -> list[dict[str, Any]]:
    """
    Retrieve all open active leads for a given rep (Récupérer tous les leads actifs et ouverts d'un commercial).
    Excludes leads that are enrolled or lost (Exclut les leads inscrits ou perdus).
    """
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM leads
            WHERE rep = ?
              AND status NOT IN ('enrolled', 'lost')
            ORDER BY next_followup_date ASC NULLS LAST
            """,
            (rep,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def upsert_lead(data: dict[str, Any], db_path: str = DB_PATH) -> dict[str, Any]:
    """
    Insert or update a lead by email address (Insérer ou mettre à jour un lead par son adresse email - idempotent).
    """
    now = _now_iso()
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO leads (
                email, last_name, first_name, rep, chaleur, arrived_on,
                call_count, status, last_contact_date, next_followup_date,
                next_followup_time, last_outcome, consecutive_no_answer,
                funding_status, lost_reason, notes, created_at, updated_at
            ) VALUES (
                :email, :last_name, :first_name, :rep, :chaleur, :arrived_on,
                :call_count, :status, :last_contact_date, :next_followup_date,
                :next_followup_time, :last_outcome, :consecutive_no_answer,
                :funding_status, :lost_reason, :notes, :created_at, :updated_at
            )
            ON CONFLICT(email) DO UPDATE SET
                last_name             = excluded.last_name,
                first_name            = excluded.first_name,
                rep                   = excluded.rep,
                chaleur               = excluded.chaleur,
                arrived_on            = excluded.arrived_on,
                call_count            = excluded.call_count,
                status                = excluded.status,
                last_contact_date     = excluded.last_contact_date,
                next_followup_date    = excluded.next_followup_date,
                next_followup_time    = excluded.next_followup_time,
                last_outcome          = excluded.last_outcome,
                consecutive_no_answer = excluded.consecutive_no_answer,
                funding_status        = excluded.funding_status,
                lost_reason           = excluded.lost_reason,
                notes                 = excluded.notes,
                updated_at            = :updated_at
            """,
            {
                **data,
                "created_at": data.get("created_at", now),
                "updated_at": now,
                "last_contact_date": data.get("last_contact_date"),
                "next_followup_date": data.get("next_followup_date"),
                "next_followup_time": data.get("next_followup_time"),
                "last_outcome": data.get("last_outcome"),
                "lost_reason": data.get("lost_reason"),
                "notes": data.get("notes", ""),
                "funding_status": data.get("funding_status", "unknown"),
                "consecutive_no_answer": data.get("consecutive_no_answer", 0),
            },
        )
        row = conn.execute(
            "SELECT * FROM leads WHERE email = ?", (data["email"],)
        ).fetchone()
    return _row_to_dict(row)


def update_lead(lead_id: int, updates: dict[str, Any], db_path: str = DB_PATH) -> Optional[dict[str, Any]]:
    """
    Apply a partial update dictionary to a lead (Appliquer une mise à jour partielle à un lead).
    """
    if not updates:
        return get_lead(lead_id, db_path)

    updates["updated_at"] = _now_iso()
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["id"] = lead_id

    with get_conn(db_path) as conn:
        conn.execute(f"UPDATE leads SET {set_clause} WHERE id = :id", updates)
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    return _row_to_dict(row) if row else None


# ---------------------------------------------------------------------------
# Interaction History Operations (Gestion de l'historique des interactions)
# ---------------------------------------------------------------------------

def add_interaction(data: dict[str, Any], db_path: str = DB_PATH) -> dict[str, Any]:
    """
    Record an outreach interaction in history (Enregistrer une nouvelle interaction dans l'historique).
    """
    with get_conn(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO interactions (lead_id, at, rep, channel, outcome, note)
            VALUES (:lead_id, :at, :rep, :channel, :outcome, :note)
            """,
            data,
        )
        row = conn.execute(
            "SELECT * FROM interactions WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return _row_to_dict(row)


def get_interactions(lead_id: int, db_path: str = DB_PATH) -> list[dict[str, Any]]:
    """
    Get full timeline of interactions for a lead (Récupérer l'historique chronologique des interactions d'un lead).
    """
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM interactions WHERE lead_id = ? ORDER BY at ASC",
            (lead_id,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def delete_interactions_for_lead(lead_id: int, db_path: str = DB_PATH) -> None:
    """
    Clear interactions for a lead (Supprimer l'historique d'un lead - utilisé lors du re-seed).
    """
    with get_conn(db_path) as conn:
        conn.execute("DELETE FROM interactions WHERE lead_id = ?", (lead_id,))


# ---------------------------------------------------------------------------
# Reps & Statistics Aggregations (Statistiques et récapitulatif par commercial)
# ---------------------------------------------------------------------------

def list_reps(db_path: str = DB_PATH) -> list[dict[str, Any]]:
    """
    List sales reps and count of open leads (Lister les commerciaux avec leur total de leads ouverts).
    """
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT rep,
                   COUNT(*) AS open_leads
            FROM leads
            WHERE status NOT IN ('enrolled', 'lost')
            GROUP BY rep
            ORDER BY rep
            """,
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def count_all_leads(db_path: str = DB_PATH) -> int:
    """
    Count total number of leads in database (Compter le nombre total de leads en base).
    Gracefully returns 0 if table does not exist yet (Retourne 0 si la table n'existe pas encore).
    """
    try:
        with get_conn(db_path) as conn:
            row = conn.execute("SELECT COUNT(*) FROM leads").fetchone()
        return row[0] if row else 0
    except sqlite3.OperationalError:
        return 0


def count_leads_by_criteria(
    rep: Optional[str],
    today: date,
    db_path: str = DB_PATH,
) -> dict[str, int]:
    """
    Compute aggregate counters for stats cards (Calculer les compteurs agrégés pour le tableau de bord).
    """
    rep_filter = "AND rep = :rep" if rep else ""
    window_end = (today + timedelta(days=UPCOMING_WINDOW_DAYS)).isoformat()
    params: dict[str, Any] = {
        "rep": rep,
        "today": today.isoformat(),
        "window_end": window_end,
    }

    with get_conn(db_path) as conn:
        def q(sql: str) -> int:
            return conn.execute(sql, params).fetchone()[0]

        # Total open active leads (Total des leads actifs ouverts)
        open_leads = q(
            f"SELECT COUNT(*) FROM leads WHERE status NOT IN ('enrolled','lost') {rep_filter}"
        )

        # Overdue leads (Leads en retard de rappel)
        overdue = q(
            f"SELECT COUNT(*) FROM leads WHERE status NOT IN ('enrolled','lost') AND next_followup_date < :today {rep_filter}"
        )

        # Leads due today (Leads à relancer aujourd'hui)
        due_today = q(
            f"SELECT COUNT(*) FROM leads WHERE status NOT IN ('enrolled','lost') AND next_followup_date = :today {rep_filter}"
        )

        # Upcoming in the next 7 days (Leads à relancer dans les 7 prochains jours)
        upcoming = q(
            f"SELECT COUNT(*) FROM leads WHERE status NOT IN ('enrolled','lost') AND next_followup_date > :today AND next_followup_date <= :window_end {rep_filter}"
        )

        # Hot leads with only 1 call attempted (Leads chauds avec un seul appel passé)
        forgotten_hot = q(
            f"""SELECT COUNT(*) FROM leads
                WHERE status NOT IN ('enrolled','lost')
                  AND chaleur >= 7 AND call_count = 1 AND status IN ('new','contacting')
                  {rep_filter}"""
        )

        # Fatigued leads with 3+ no-answers (Leads fatigués avec 3 appels sans réponse ou plus)
        fatigued = q(
            f"SELECT COUNT(*) FROM leads WHERE consecutive_no_answer >= 3 AND status NOT IN ('enrolled','lost') {rep_filter}"
        )

        # Leads reaching the stop rule of 5 fruitless calls (Leads ayant atteint le plafond de 5 appels sans échange)
        at_stop = q(
            f"""SELECT COUNT(*) FROM leads
                WHERE call_count >= 5
                  AND (last_outcome IS NULL OR last_outcome NOT IN ('interested','callback_requested','needs_funding_info'))
                  AND status NOT IN ('enrolled','lost')
                  {rep_filter}"""
        )

        # Closed converted leads (Leads convertis en inscrits)
        enrolled = q(f"SELECT COUNT(*) FROM leads WHERE status = 'enrolled' {rep_filter}")

        # Closed lost leads (Leads clôturés en perdus)
        lost = q(f"SELECT COUNT(*) FROM leads WHERE status = 'lost' {rep_filter}")

    return {
        "open_leads": open_leads,
        "overdue": overdue,
        "due_today": due_today,
        "upcoming": upcoming,
        "forgotten_hot": forgotten_hot,
        "fatigued": fatigued,
        "at_stop_rule": at_stop,
        "enrolled": enrolled,
        "lost": lost,
    }
