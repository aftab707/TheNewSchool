"""
API route definitions for Smart CRM (Définition des routes API pour Smart CRM).
Provides endpoints for work queue, call logging, Kanban, and team statistics (Fournit les points d'entrée pour la file d'appels, le journal d'appels, le Kanban et les statistiques d'équipe).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.config import get_today, UPCOMING_WINDOW_DAYS, DAILY_CALL_CAPACITY, DB_PATH
from app.models.schemas import (
    LeadOut,
    LogContactRequest,
    LogContactResponse,
    PatchLeadRequest,
    QueueGroup,
    QueueResponse,
    RepSummary,
    SnoozeRequest,
    StatsResponse,
    InteractionOut,
)
from app.repositories.lead_repository import (
    get_lead,
    list_leads,
    list_leads_for_queue,
    update_lead,
    add_interaction,
    get_interactions,
    list_reps,
    count_leads_by_criteria,
)
from app.services.scoring_service import compute_priority, should_exclude_from_queue
from app.services.workflow_service import apply_outcome, suggested_channel

# APIRouter instance for all CRM endpoints (Routeur API pour tous les points d'accès CRM)
router = APIRouter(prefix="/api", tags=["CRM"])


# ---------------------------------------------------------------------------
# Internal Endpoint Helpers (Fonctions d'aide pour les routes)
# ---------------------------------------------------------------------------

def _enrich_lead(lead: dict[str, Any], today: date) -> LeadOut:
    """
    Enrich raw database row with calculated priority, reasons, and suggested channel (Enrichir les données brutes avec la priorité calculée, les badges explicatifs et le canal conseillé).
    """
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
    """
    Create friendly French toast message with next contact date (Générer un message toast clair en français avec la date de relance).
    """
    nfd = lead.get("next_followup_date")
    if nfd:
        try:
            d = date.fromisoformat(nfd)
            days_fr = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
            months_fr = ["jan", "fév", "mar", "avr", "mai", "juin",
                         "juil", "août", "sep", "oct", "nov", "déc"]
            return f"Prochain suivi : {days_fr[d.weekday()]} {d.day} {months_fr[d.month - 1]} {d.year}"
        except Exception:
            return f"Prochain suivi : {nfd}"
    return "Lead fermé."


# ---------------------------------------------------------------------------
# API Endpoints (Points de terminaison API)
# ---------------------------------------------------------------------------

@router.get("/health")
def health() -> dict[str, str]:
    """
    Healthcheck endpoint verifying system status and active reference date (Vérification de l'état de l'application et de la date de référence active).
    """
    return {"status": "ok", "today": get_today().isoformat()}


@router.get("/reps", response_model=list[RepSummary])
def reps_endpoint() -> list[RepSummary]:
    """
    List all sales reps with active lead counts and overdue totals (Lister les commerciaux avec leurs totaux de leads et de retards).
    """
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


@router.get("/queue", response_model=QueueResponse)
def queue_endpoint(rep: str = Query(..., description="Sales rep name (Nom du commercial)")) -> QueueResponse:
    """
    Work queue endpoint: returns ranked leads grouped into Overdue, Today, and Upcoming (File d'appels priorisée : classée par retard, aujourd'hui et à venir).
    """
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

    # Sort each group by priority score descending (Trier chaque groupe par priorité décroissante)
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


@router.get("/leads", response_model=list[LeadOut])
def leads_list(
    rep: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
) -> list[LeadOut]:
    """
    Search and filter leads for the Kanban pipeline (Rechercher et filtrer les leads pour le pipeline Kanban).
    """
    today = get_today()
    leads = list_leads(rep=rep, status=status, q=q, db_path=DB_PATH)
    return [_enrich_lead(lead, today) for lead in leads]


@router.get("/leads/{lead_id}", response_model=LeadOut)
def lead_detail(lead_id: int) -> LeadOut:
    """
    Retrieve full details and interaction history for a single lead (Détail complet et historique d'un prospect).
    """
    today = get_today()
    lead = get_lead(lead_id, DB_PATH)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found (Lead non trouvé)")
    return _enrich_lead(lead, today)


@router.post("/leads/{lead_id}/log-contact", response_model=LogContactResponse)
def log_contact(lead_id: int, body: LogContactRequest) -> LogContactResponse:
    """
    Log an outreach call outcome, update pipeline, and fetch the next lead (Enregistrer le résultat d'un appel, mettre à jour le pipeline et proposer le lead suivant).
    """
    today = get_today()
    lead = get_lead(lead_id, DB_PATH)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found (Lead non trouvé)")

    # Compute workflow updates and persist (Calculer et enregistrer les modifications du workflow)
    updates = apply_outcome(lead, body.model_dump(), today)
    updated_lead_data = update_lead(lead_id, updates, DB_PATH)

    # Append to interaction timeline (Ajouter à l'historique des interactions)
    add_interaction({
        "lead_id": lead_id,
        "at": today.isoformat() + "T00:00:00",
        "rep": lead["rep"],
        "channel": body.channel.value,
        "outcome": body.outcome.value,
        "note": body.note or "",
    }, DB_PATH)

    updated_enriched = _enrich_lead(updated_lead_data, today)

    # Automatically identify next best lead in queue (Identifier automatiquement le prochain meilleur lead dans la file)
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


@router.patch("/leads/{lead_id}", response_model=LeadOut)
def patch_lead(lead_id: int, body: PatchLeadRequest) -> LeadOut:
    """
    Update lead status via Kanban drag-and-drop or edit notes (Mise à jour rapide du statut ou des notes d'un lead).
    """
    today = get_today()
    lead = get_lead(lead_id, DB_PATH)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found (Lead non trouvé)")

    updates: dict[str, Any] = {k: v for k, v in body.model_dump().items() if v is not None}
    if body.status is not None:
        updates["status"] = body.status.value
    if body.funding_status is not None:
        updates["funding_status"] = body.funding_status.value

    updated = update_lead(lead_id, updates, DB_PATH)
    return _enrich_lead(updated, today)


@router.post("/leads/{lead_id}/snooze", response_model=LeadOut)
def snooze_lead(lead_id: int, body: SnoozeRequest) -> LeadOut:
    """
    Postpone a lead's follow-up date manually (Reporter manuellement la date de relance d'un prospect).
    """
    today = get_today()
    lead = get_lead(lead_id, DB_PATH)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found (Lead non trouvé)")

    updated = update_lead(lead_id, {"next_followup_date": body.until}, DB_PATH)
    return _enrich_lead(updated, today)


@router.get("/stats", response_model=StatsResponse)
def stats_endpoint(rep: Optional[str] = None) -> StatsResponse:
    """
    Aggregate pipeline indicators and team workload stats (Indicateurs clés du pipeline et statistiques d'équipe).
    """
    today = get_today()
    counts = count_leads_by_criteria(rep, today, DB_PATH)
    return StatsResponse(rep=rep, **counts)
