"""app/models.py — Pydantic schemas and enums for the Smart CRM."""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Status(str, Enum):
    new = "new"
    contacting = "contacting"
    qualified = "qualified"
    funding = "funding"
    enrolled = "enrolled"
    lost = "lost"
    nurture = "nurture"


class Outcome(str, Enum):
    no_answer = "no_answer"
    voicemail = "voicemail"
    callback_requested = "callback_requested"
    interested = "interested"
    needs_funding_info = "needs_funding_info"
    not_interested = "not_interested"
    wrong_number = "wrong_number"
    enrolled = "enrolled"


class FundingStatus(str, Enum):
    unknown = "unknown"
    cpf = "cpf"
    opco = "opco"
    france_travail = "france_travail"
    self_funded = "self"
    employer = "employer"


class Channel(str, Enum):
    call = "call"
    email = "email"
    sms = "sms"


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class LogContactRequest(BaseModel):
    outcome: Outcome
    note: str = ""
    channel: Channel = Channel.call
    callback_at: Optional[str] = None       # ISO date "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM"
    funding_status: Optional[FundingStatus] = None
    lost_reason: Optional[str] = None

    @model_validator(mode="after")
    def validate_outcome_fields(self) -> "LogContactRequest":
        if self.outcome == Outcome.callback_requested and not self.callback_at:
            raise ValueError("callback_at is required when outcome is callback_requested")
        if self.outcome == Outcome.not_interested and not self.lost_reason:
            raise ValueError("lost_reason is required when outcome is not_interested")
        return self


class SnoozeRequest(BaseModel):
    until: str  # ISO date YYYY-MM-DD

    @field_validator("until")
    @classmethod
    def parse_date(cls, v: str) -> str:
        date.fromisoformat(v)   # raises ValueError if invalid
        return v


class PatchLeadRequest(BaseModel):
    status: Optional[Status] = None
    notes: Optional[str] = None
    funding_status: Optional[FundingStatus] = None
    lost_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Read schemas
# ---------------------------------------------------------------------------

class ReasonChip(BaseModel):
    code: str
    label_fr: str
    label_en: str
    weight: float


class InteractionOut(BaseModel):
    id: int
    lead_id: int
    at: str
    rep: str
    channel: str
    outcome: str
    note: str


class LeadOut(BaseModel):
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
    # Computed on read
    priority: Optional[float] = None
    value_score: Optional[float] = None
    urgency_score: Optional[float] = None
    reasons: list[ReasonChip] = []
    suggested_channel: Optional[str] = None
    interactions: list[InteractionOut] = []


class RepSummary(BaseModel):
    rep: str
    open_leads: int
    overdue: int
    due_today: int
    forgotten_hot: int
    fatigued: int


class QueueGroup(BaseModel):
    group: str   # "overdue" | "today" | "upcoming"
    label_fr: str
    leads: list[LeadOut]


class QueueResponse(BaseModel):
    rep: str
    today: str
    daily_capacity: int
    groups: list[QueueGroup]


class StatsResponse(BaseModel):
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
    lead: LeadOut
    next_lead: Optional[LeadOut]
    toast: str
