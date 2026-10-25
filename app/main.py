"""app/main.py — FastAPI application with all API endpoints."""
from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app import config
from app.config import get_today, UPCOMING_WINDOW_DAYS, DAILY_CALL_CAPACITY, DB_PATH
from app.db import init_db
from app.models import (
    LeadOut, LogContactRequest, LogContactResponse, PatchLeadRequest,
    QueueGroup, QueueResponse, RepSummary, ReasonChip, SnoozeRequest,
    StatsResponse, InteractionOut,
)
from app.repository import (
    add_interaction, count_leads_by_criteria, get_interactions, get_lead,
    list_leads, list_leads_for_queue, list_reps, update_lead,
)
from app.scoring import compute_priority, should_exclude_from_queue
from app.workflow import apply_outcome, suggested_channel


# ---------------------------------------------------------------------------
# App init
# ---------------------------------------------------------------------------

app = FastAPI(title="Smart CRM — La Nouvelle École", version="1.0.0")

@app.on_event("startup")
def startup() -> None:
    init_db(DB_PATH)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _enrich_lead(lead: dict[str, Any], today: date) -> LeadOut:
    """Add computed priority, reasons, and suggested_channel to a lead dict."""
    priority, value, urgency, reasons = compute_priority(lead, today)
    interactions = get_interactions(lead["id"])
    return LeadOut(
        **lead,
        priority=priority,
        value_score=value,
        urgency_score=urgency,
        reasons=reasons,
        suggested_channel=suggested_channel(lead.get("consecutive_no_answer", 0)),
        interactions=[InteractionOut(**i) for i in interactions],
    )


def _toast_message(lead: dict[str, Any]) -> str:
    nfd = lead.get("next_followup_date")
    if nfd:
        try:
            d = date.fromisoformat(nfd)
            # Format as French weekday + date
            days_fr = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
            months_fr = ["jan", "fév", "mar", "avr", "mai", "juin",
                         "juil", "août", "sep", "oct", "nov", "déc"]
            return (
                f"Prochain suivi : {days_fr[d.weekday()]} "
                f"{d.day} {months_fr[d.month - 1]} {d.year}"
            )
        except Exception:
            return f"Prochain suivi : {nfd}"
    return "Lead fermé."


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "today": get_today().isoformat()}


# ---------------------------------------------------------------------------
# Reps
# ---------------------------------------------------------------------------

@app.get("/api/reps", response_model=list[RepSummary])
def reps_endpoint() -> list[RepSummary]:
    today = get_today()
    rep_rows = list_reps(DB_PATH)
    result = []
    for row in rep_rows:
        rep = row["rep"]
        stats = count_leads_by_criteria(rep, today, DB_PATH)
        result.append(RepSummary(
            rep=rep,
            open_leads=row["open_leads"],
            overdue=stats["overdue"],
            due_today=stats["due_today"],
            forgotten_hot=stats["forgotten_hot"],
            fatigued=stats["fatigued"],
        ))
    return result


# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------

@app.get("/api/queue", response_model=QueueResponse)
def queue_endpoint(rep: str = Query(..., description="Sales rep name")) -> QueueResponse:
    today = get_today()
    leads = list_leads_for_queue(rep, DB_PATH)
    window_end = today + timedelta(days=UPCOMING_WINDOW_DAYS)

    overdue_leads: list[LeadOut] = []
    today_leads: list[LeadOut] = []
    upcoming_leads: list[LeadOut] = []

    for lead in leads:
        if should_exclude_from_queue(lead):
            continue
        enriched = _enrich_lead(lead, today)
        nfd = lead.get("next_followup_date")
        if not nfd:
            upcoming_leads.append(enriched)
            continue
        nfd_date = date.fromisoformat(nfd)
        if nfd_date < today:
            overdue_leads.append(enriched)
        elif nfd_date == today:
            today_leads.append(enriched)
        elif nfd_date <= window_end:
            upcoming_leads.append(enriched)

    # Sort each group by priority descending
    for group in (overdue_leads, today_leads, upcoming_leads):
        group.sort(key=lambda x: x.priority or 0, reverse=True)

    return QueueResponse(
        rep=rep,
        today=today.isoformat(),
        daily_capacity=DAILY_CALL_CAPACITY,
        groups=[
            QueueGroup(group="overdue", label_fr="En retard", leads=overdue_leads),
            QueueGroup(group="today",   label_fr="Aujourd'hui", leads=today_leads),
            QueueGroup(group="upcoming", label_fr="À venir", leads=upcoming_leads),
        ],
    )


# ---------------------------------------------------------------------------
# Leads list (Kanban + search)
# ---------------------------------------------------------------------------

@app.get("/api/leads", response_model=list[LeadOut])
def leads_list(
    rep: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
) -> list[LeadOut]:
    today = get_today()
    leads = list_leads(rep=rep, status=status, q=q, db_path=DB_PATH)
    return [_enrich_lead(lead, today) for lead in leads]


# ---------------------------------------------------------------------------
# Lead detail
# ---------------------------------------------------------------------------

@app.get("/api/leads/{lead_id}", response_model=LeadOut)
def lead_detail(lead_id: int) -> LeadOut:
    today = get_today()
    lead = get_lead(lead_id, DB_PATH)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return _enrich_lead(lead, today)


# ---------------------------------------------------------------------------
# Log contact
# ---------------------------------------------------------------------------

@app.post("/api/leads/{lead_id}/log-contact", response_model=LogContactResponse)
def log_contact(lead_id: int, body: LogContactRequest) -> LogContactResponse:
    today = get_today()
    lead = get_lead(lead_id, DB_PATH)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Apply workflow
    updates = apply_outcome(lead, body.model_dump(), today)
    updated_lead_data = update_lead(lead_id, updates, DB_PATH)

    # Record interaction
    add_interaction({
        "lead_id": lead_id,
        "at": today.isoformat() + "T00:00:00",
        "rep": lead["rep"],
        "channel": body.channel.value,
        "outcome": body.outcome.value,
        "note": body.note or "",
    }, DB_PATH)

    updated_enriched = _enrich_lead(updated_lead_data, today)

    # Find next lead in queue for the same rep
    next_leads = list_leads_for_queue(lead["rep"], DB_PATH)
    window_end = today + timedelta(days=UPCOMING_WINDOW_DAYS)
    next_lead_out = None
    for nl in next_leads:
        if nl["id"] == lead_id:
            continue
        if should_exclude_from_queue(nl):
            continue
        nfd = nl.get("next_followup_date")
        if not nfd:
            continue
        nfd_date = date.fromisoformat(nfd)
        if nfd_date <= window_end:
            next_lead_out = _enrich_lead(nl, today)
            break

    return LogContactResponse(
        lead=updated_enriched,
        next_lead=next_lead_out,
        toast=_toast_message(updated_lead_data),
    )


# ---------------------------------------------------------------------------
# Patch lead (Kanban drag-drop / manual edit)
# ---------------------------------------------------------------------------

@app.patch("/api/leads/{lead_id}", response_model=LeadOut)
def patch_lead(lead_id: int, body: PatchLeadRequest) -> LeadOut:
    today = get_today()
    lead = get_lead(lead_id, DB_PATH)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    updates: dict[str, Any] = {k: v for k, v in body.model_dump().items() if v is not None}
    if body.status is not None:
        updates["status"] = body.status.value
    if body.funding_status is not None:
        updates["funding_status"] = body.funding_status.value

    updated = update_lead(lead_id, updates, DB_PATH)
    return _enrich_lead(updated, today)


# ---------------------------------------------------------------------------
# Snooze
# ---------------------------------------------------------------------------

@app.post("/api/leads/{lead_id}/snooze", response_model=LeadOut)
def snooze_lead(lead_id: int, body: SnoozeRequest) -> LeadOut:
    today = get_today()
    lead = get_lead(lead_id, DB_PATH)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    updated = update_lead(lead_id, {"next_followup_date": body.until}, DB_PATH)
    return _enrich_lead(updated, today)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@app.get("/api/stats", response_model=StatsResponse)
def stats_endpoint(rep: Optional[str] = None) -> StatsResponse:
    today = get_today()
    counts = count_leads_by_criteria(rep, today, DB_PATH)
    return StatsResponse(rep=rep, **counts)


# ---------------------------------------------------------------------------
# Static files (frontend)
# ---------------------------------------------------------------------------

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
