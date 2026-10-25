"""tests/test_scoring.py — Unit tests for the scoring engine."""
import os
import pytest
from datetime import date

os.environ.setdefault("CRM_TODAY", "2026-07-20")

from app.scoring import compute_value, compute_urgency, compute_priority, should_exclude_from_queue


def make_lead(**kwargs):
    defaults = {
        "id": 1,
        "email": "test@example.com",
        "last_name": "Dupont",
        "first_name": "Jean",
        "rep": "Adrien",
        "chaleur": 5,
        "arrived_on": "2026-05-01",
        "call_count": 1,
        "status": "contacting",
        "last_contact_date": "2026-07-10",
        "next_followup_date": "2026-07-20",
        "last_outcome": None,
        "consecutive_no_answer": 0,
        "funding_status": "unknown",
        "lost_reason": None,
        "notes": "",
    }
    defaults.update(kwargs)
    return defaults


TODAY = date(2026, 7, 20)


# ---------------------------------------------------------------------------
# Value score tests
# ---------------------------------------------------------------------------

class TestValueScore:
    def test_chaleur_0_gives_0(self):
        lead = make_lead(chaleur=0)
        assert compute_value(lead) == 0.0

    def test_chaleur_10_gives_100(self):
        lead = make_lead(chaleur=10)
        assert compute_value(lead) == 100.0

    def test_chaleur_5_gives_50(self):
        lead = make_lead(chaleur=5)
        assert compute_value(lead) == 50.0

    def test_bonus_interested(self):
        lead = make_lead(chaleur=5, last_outcome="interested")
        assert compute_value(lead) == 60.0   # 50 + 10

    def test_bonus_callback_requested(self):
        lead = make_lead(chaleur=5, last_outcome="callback_requested")
        assert compute_value(lead) == 60.0   # 50 + 10

    def test_bonus_funding_cpf(self):
        lead = make_lead(chaleur=5, funding_status="cpf")
        assert compute_value(lead) == 55.0   # 50 + 5

    def test_value_capped_at_100(self):
        lead = make_lead(chaleur=10, last_outcome="interested", funding_status="cpf")
        assert compute_value(lead) == 100.0  # would be 115 without cap


# ---------------------------------------------------------------------------
# Urgency score tests
# ---------------------------------------------------------------------------

class TestUrgencyScore:
    def test_due_today(self):
        lead = make_lead(next_followup_date="2026-07-20")
        assert compute_urgency(lead, TODAY) == 60.0

    def test_overdue_1_day(self):
        lead = make_lead(next_followup_date="2026-07-19")
        assert compute_urgency(lead, TODAY) == 65.0   # 60 + 5

    def test_overdue_8_days_capped(self):
        lead = make_lead(next_followup_date="2026-07-12")
        assert compute_urgency(lead, TODAY) == 100.0  # 60 + 8*5 = 100, capped

    def test_due_tomorrow(self):
        lead = make_lead(next_followup_date="2026-07-21")
        assert compute_urgency(lead, TODAY) == 30.0   # 40 - 1*10

    def test_due_in_4_days(self):
        lead = make_lead(next_followup_date="2026-07-24")
        assert compute_urgency(lead, TODAY) == 0.0    # 40 - 4*10 = 0

    def test_no_followup_date(self):
        lead = make_lead(next_followup_date=None)
        assert compute_urgency(lead, TODAY) == 0.0


# ---------------------------------------------------------------------------
# Priority and bonus/penalty tests
# ---------------------------------------------------------------------------

class TestPriority:
    def test_forgotten_hot_bonus(self):
        """Hot lead with 1 call in new/contacting gets the FORGOTTEN_HOT bonus."""
        hot = make_lead(chaleur=8, call_count=1, status="contacting", next_followup_date="2026-07-20")
        cold = make_lead(chaleur=8, call_count=2, status="contacting", next_followup_date="2026-07-20")
        p_hot, *_ = compute_priority(hot, TODAY)
        p_cold, *_ = compute_priority(cold, TODAY)
        assert p_hot > p_cold

    def test_forgotten_hot_only_when_conditions_met(self):
        """FORGOTTEN_HOT should NOT apply if chaleur < 7."""
        lead = make_lead(chaleur=6, call_count=1, status="contacting", next_followup_date="2026-07-20")
        _, _, _, reasons = compute_priority(lead, TODAY)
        codes = [r.code for r in reasons]
        assert "FORGOTTEN_HOT" not in codes

    def test_fatigue_multiplier(self):
        """3+ consecutive no-answers should reduce priority."""
        fatigued = make_lead(chaleur=7, consecutive_no_answer=3, next_followup_date="2026-07-20")
        fresh = make_lead(chaleur=7, consecutive_no_answer=0, next_followup_date="2026-07-20")
        p_fatigued, *_ = compute_priority(fatigued, TODAY)
        p_fresh, *_ = compute_priority(fresh, TODAY)
        assert p_fatigued < p_fresh

    def test_hot_overdue_beats_hot_upcoming(self):
        overdue = make_lead(chaleur=8, next_followup_date="2026-07-15")
        upcoming = make_lead(chaleur=8, next_followup_date="2026-07-22")
        p_over, *_ = compute_priority(overdue, TODAY)
        p_up, *_ = compute_priority(upcoming, TODAY)
        assert p_over > p_up

    def test_hot_overdue_beats_cold_overdue(self):
        hot = make_lead(chaleur=9, next_followup_date="2026-07-19")
        cold = make_lead(chaleur=2, next_followup_date="2026-07-19")
        p_hot, *_ = compute_priority(hot, TODAY)
        p_cold, *_ = compute_priority(cold, TODAY)
        assert p_hot > p_cold

    def test_priority_clamped_0_100(self):
        lead = make_lead(chaleur=10, next_followup_date="2026-07-01")
        p, *_ = compute_priority(lead, TODAY)
        assert 0 <= p <= 100

    def test_reasons_produced_for_overdue(self):
        lead = make_lead(next_followup_date="2026-07-15")
        _, _, _, reasons = compute_priority(lead, TODAY)
        codes = [r.code for r in reasons]
        assert "OVERDUE" in codes

    def test_reasons_produced_for_hot(self):
        lead = make_lead(chaleur=9)
        _, _, _, reasons = compute_priority(lead, TODAY)
        codes = [r.code for r in reasons]
        assert "HOT" in codes

    def test_fatigue_reason_chip(self):
        lead = make_lead(consecutive_no_answer=3, next_followup_date="2026-07-20")
        _, _, _, reasons = compute_priority(lead, TODAY)
        codes = [r.code for r in reasons]
        assert "FATIGUE" in codes


# ---------------------------------------------------------------------------
# Stop rule
# ---------------------------------------------------------------------------

class TestStopRule:
    def test_stop_rule_excludes_lead(self):
        lead = make_lead(call_count=5, last_outcome="no_answer", status="contacting")
        assert should_exclude_from_queue(lead) is True

    def test_stop_rule_does_not_apply_with_real_conversation(self):
        lead = make_lead(call_count=5, last_outcome="interested", status="qualified")
        assert should_exclude_from_queue(lead) is False

    def test_enrolled_excluded(self):
        lead = make_lead(status="enrolled")
        assert should_exclude_from_queue(lead) is True

    def test_lost_excluded(self):
        lead = make_lead(status="lost")
        assert should_exclude_from_queue(lead) is True
