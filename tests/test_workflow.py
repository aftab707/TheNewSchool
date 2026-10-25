"""tests/test_workflow.py — Unit tests for the workflow engine."""
import os
import pytest
from datetime import date

os.environ.setdefault("CRM_TODAY", "2026-07-20")

from app.workflow import apply_outcome, compute_next_followup, new_status_after_outcome


TODAY = date(2026, 7, 20)


def make_lead(**kwargs):
    defaults = {
        "id": 1,
        "email": "test@example.com",
        "rep": "Adrien",
        "chaleur": 5,
        "call_count": 1,
        "status": "new",
        "consecutive_no_answer": 0,
        "funding_status": "unknown",
    }
    defaults.update(kwargs)
    return defaults


def make_request(**kwargs):
    defaults = {
        "outcome": "no_answer",
        "note": "",
        "channel": "call",
        "callback_at": None,
        "funding_status": None,
        "lost_reason": None,
    }
    defaults.update(kwargs)
    return defaults


class TestNewStatus:
    def test_no_answer_from_new_goes_to_contacting(self):
        assert new_status_after_outcome("new", "no_answer") == "contacting"

    def test_no_answer_from_contacting_stays(self):
        assert new_status_after_outcome("contacting", "no_answer") == "contacting"

    def test_interested_promotes_to_qualified(self):
        assert new_status_after_outcome("new", "interested") == "qualified"
        assert new_status_after_outcome("contacting", "interested") == "qualified"

    def test_interested_does_not_demote_qualified(self):
        assert new_status_after_outcome("qualified", "interested") == "qualified"

    def test_callback_requested_promotes(self):
        assert new_status_after_outcome("new", "callback_requested") == "qualified"

    def test_needs_funding_goes_to_funding(self):
        assert new_status_after_outcome("new", "needs_funding_info") == "funding"

    def test_not_interested_goes_to_lost(self):
        assert new_status_after_outcome("new", "not_interested") == "lost"

    def test_wrong_number_goes_to_lost(self):
        assert new_status_after_outcome("contacting", "wrong_number") == "lost"

    def test_enrolled_goes_to_enrolled(self):
        assert new_status_after_outcome("qualified", "enrolled") == "enrolled"


class TestNextFollowup:
    def test_no_answer_hot_lead_1_day(self):
        nfd = compute_next_followup(chaleur=9, outcome="no_answer", callback_at=None, today=TODAY)
        from app.calendar_utils import next_business_day
        assert nfd == next_business_day(TODAY, 1)

    def test_no_answer_warm_lead_cadence(self):
        from app.config import cadence_days
        from app.calendar_utils import next_business_day
        nfd = compute_next_followup(chaleur=5, outcome="no_answer", callback_at=None, today=TODAY)
        assert nfd == next_business_day(TODAY, cadence_days(5))

    def test_interested_2_days(self):
        from app.calendar_utils import next_business_day
        nfd = compute_next_followup(chaleur=5, outcome="interested", callback_at=None, today=TODAY)
        assert nfd == next_business_day(TODAY, 2)

    def test_needs_funding_3_days(self):
        from app.calendar_utils import next_business_day
        nfd = compute_next_followup(chaleur=5, outcome="needs_funding_info", callback_at=None, today=TODAY)
        assert nfd == next_business_day(TODAY, 3)

    def test_callback_requested_uses_given_date(self):
        nfd = compute_next_followup(chaleur=5, outcome="callback_requested", callback_at="2026-07-25", today=TODAY)
        assert nfd == date(2026, 7, 25)

    def test_not_interested_returns_none(self):
        nfd = compute_next_followup(chaleur=5, outcome="not_interested", callback_at=None, today=TODAY)
        assert nfd is None

    def test_enrolled_returns_none(self):
        nfd = compute_next_followup(chaleur=5, outcome="enrolled", callback_at=None, today=TODAY)
        assert nfd is None


class TestApplyOutcome:
    def test_no_answer_increments_counters(self):
        lead = make_lead(call_count=2, consecutive_no_answer=1)
        req = make_request(outcome="no_answer")
        updates = apply_outcome(lead, req, TODAY)
        assert updates["call_count"] == 3
        assert updates["consecutive_no_answer"] == 2
        assert updates["status"] == "contacting"
        assert updates["last_contact_date"] == TODAY.isoformat()

    def test_interested_resets_consecutive_na(self):
        lead = make_lead(call_count=2, consecutive_no_answer=2)
        req = make_request(outcome="interested")
        updates = apply_outcome(lead, req, TODAY)
        assert updates["consecutive_no_answer"] == 0
        assert updates["status"] == "qualified"

    def test_callback_stores_time(self):
        lead = make_lead(call_count=1)
        req = make_request(outcome="callback_requested", callback_at="2026-07-25T14:30")
        updates = apply_outcome(lead, req, TODAY)
        assert updates["next_followup_time"] == "14:30"
        assert updates["next_followup_date"] == "2026-07-25"

    def test_not_interested_stores_lost_reason(self):
        lead = make_lead(call_count=3)
        req = make_request(outcome="not_interested", lost_reason="Prix trop élevé")
        updates = apply_outcome(lead, req, TODAY)
        assert updates["status"] == "lost"
        assert updates["lost_reason"] == "Prix trop élevé"
        assert updates["next_followup_date"] is None

    def test_funding_status_stored(self):
        lead = make_lead()
        req = make_request(outcome="needs_funding_info", funding_status="cpf")
        updates = apply_outcome(lead, req, TODAY)
        assert updates["funding_status"] == "cpf"
        assert updates["status"] == "funding"
