"""
Data models and Pydantic schemas (Modèles de données et schémas Pydantic pour Smart CRM).
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, field_validator, model_validator


# ---------------------------------------------------------------------------
# Business Enums (Énumérations Métier)
# ---------------------------------------------------------------------------

class Status(str, Enum):
    """Pipeline stages (Étapes du pipeline de vente)"""
    new = "new"                # Newly arrived prospect (Nouveau prospect arrivé)
    contacting = "contacting"  # Contact attempts underway (Tentatives de contact en cours)
    qualified = "qualified"    # Spoke with lead, interest confirmed (Échange confirmé, intérêt validé)
    funding = "funding"        # Preparing CPF/OPCO funding (Dossier de financement en cours)
    enrolled = "enrolled"      # Won: enrolled in course (Gagné : inscrit à la formation)
    lost = "lost"              # Lost opportunity (Opportunité perdue)
    nurture = "nurture"        # Long-term recontact (À relancer ultérieurement)


class Outcome(str, Enum):
    """Result of a phone call or outreach (Résultat d'un appel ou d'une relance)"""
    no_answer = "no_answer"
    voicemail = "voicemail"
    callback_requested = "callback_requested"
    interested = "interested"
    needs_funding_info = "needs_funding_info"
    not_interested = "not_interested"
    wrong_number = "wrong_number"
    enrolled = "enrolled"


class FundingStatus(str, Enum):
    """Funding mechanisms in France (Dispositifs de financement en France)"""
    unknown = "unknown"
    cpf = "cpf"                        # Mon Compte Formation
    opco = "opco"                      # OPCO pour salariés
    france_travail = "france_travail"  # Aide Pôle Emploi / France Travail
    self_funded = "self"               # Financement personnel
    employer = "employer"              # Financement direct entreprise


class Channel(str, Enum):
    """Communication channel used (Canal de communication utilisé)"""
    call = "call"
    email = "email"
    sms = "sms"


# ---------------------------------------------------------------------------
# Request Schemas (Schémas de Requête pour l'API)
# ---------------------------------------------------------------------------

class LogContactRequest(BaseModel):
    """
    Payload for logging an outreach attempt (Données envoyées lors de la saisie d'un appel).
    """
    outcome: Outcome
    note: str = ""
    channel: Channel = Channel.call
    callback_at: Optional[str] = None       # Format ISO: 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM'
    funding_status: Optional[FundingStatus] = None
    lost_reason: Optional[str] = None

    @model_validator(mode="after")
    def validate_outcome_fields(self) -> "LogContactRequest":
        # Validate that callback has a scheduled time (Vérifie la présence d'une date en cas de rappel demandé)
        if self.outcome == Outcome.callback_requested and not self.callback_at:
            raise ValueError("callback_at is required when outcome is callback_requested")

        # Validate that lost leads provide a reason (Vérifie la présence d'un motif si le lead est perdu)
        if self.outcome == Outcome.not_interested and not self.lost_reason:
            raise ValueError("lost_reason is required when outcome is not_interested")

        return self


class SnoozeRequest(BaseModel):
    """Postpone follow-up to a future date (Reporter la relance à une date ultérieure)"""
    until: str  # ISO date 'YYYY-MM-DD'

    @field_validator("until")
    @classmethod
    def parse_date(cls, v: str) -> str:
        date.fromisoformat(v)  # Validates date format (Valide le format de date)
        return v


class PatchLeadRequest(BaseModel):
    """Update lead status or fields via drag-and-drop (Mise à jour rapide d'un lead)"""
    status: Optional[Status] = None
    notes: Optional[str] = None
    funding_status: Optional[FundingStatus] = None
    lost_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Response Schemas (Schémas de Réponse pour l'API)
# ---------------------------------------------------------------------------

class ReasonChip(BaseModel):
    """Explainable prioritisation chip (Badge explicatif de la priorité)"""
    code: str
    label_fr: str
    label_en: str
    weight: float


class InteractionOut(BaseModel):
    """Logged interaction record (Enregistrement d'une interaction passée)"""
    id: int
    lead_id: int
    at: str
    rep: str
    channel: str
    outcome: str
    note: str


class LeadOut(BaseModel):
    """Comprehensive lead representation (Représentation complète d'un prospect)"""
    id: int
    email: str
    last_name: Optional[str]
    first_name: Optional[str]
    rep: str
    chaleur: int
    arrived_on: str
    call_count: int
    status: str
    last_contact_date: Optional[str]
    next_followup_date: Optional[str]
    next_followup_time: Optional[str]
    last_outcome: Optional[str]
    consecutive_no_answer: int
    funding_status: str
    lost_reason: Optional[str]
    notes: str
    created_at: Optional[str]
    updated_at: Optional[str]

    # Dynamically calculated fields on read (Champs calculés à la lecture)
    priority: Optional[float] = None
    value_score: Optional[float] = None
    urgency_score: Optional[float] = None
    reasons: list[ReasonChip] = []
    suggested_channel: Optional[str] = None
    interactions: list[InteractionOut] = []


class RepSummary(BaseModel):
    """Workload summary per sales rep (Récapitulatif de charge par commercial)"""
    rep: str
    open_leads: int
    overdue: int
    due_today: int
    forgotten_hot: int
    fatigued: int


class QueueGroup(BaseModel):
    """Category in work queue: Overdue, Today, Upcoming (Groupe dans la file de travail)"""
    group: str
    label_fr: str
    leads: list[LeadOut]


class QueueResponse(BaseModel):
    """Full queue response for a sales rep (File de travail complète pour un commercial)"""
    rep: str
    today: str
    daily_capacity: int
    groups: list[QueueGroup]


class StatsResponse(BaseModel):
    """Global or rep-specific statistics (Statistiques globales ou par commercial)"""
    rep: Optional[str]
    open_leads: int
    overdue: int
    due_today: int
    upcoming: int
    forgotten_hot: int
    fatigued: int
    at_stop_rule: int
    enrolled: int
    lost: int


class LogContactResponse(BaseModel):
    """Response after call logging with next lead suggestion (Réponse après appel avec proposition du prospect suivant)"""
    lead: LeadOut
    next_lead: Optional[LeadOut]
    toast: str
