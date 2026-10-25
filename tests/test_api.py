"""tests/test_api.py — Integration tests for the FastAPI endpoints."""
import os
import tempfile
import pytest

os.environ.setdefault("CRM_TODAY", "2026-07-20")

from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def seeded_db(tmp_path_factory):
    """Create a fresh seeded database for API tests."""
    import app.config as cfg
    db_path = str(tmp_path_factory.mktemp("db") / "test_api.db")
    os.environ["CRM_DB_PATH"] = db_path

    # Re-import config to pick up the new DB_PATH
    import importlib
    import app.db
    importlib.reload(app.db)
    import app.repository
    importlib.reload(app.repository)

    from app.db import init_db
    init_db(db_path)

    from app.repository import upsert_lead
    # Insert a few test leads
    leads_data = [
        {
            "email": "alice@test.com", "last_name": "Martin", "first_name": "Alice",
            "rep": "Guillaume", "chaleur": 8, "arrived_on": "2026-04-21",
            "call_count": 1, "status": "contacting",
            "last_contact_date": "2026-07-10", "next_followup_date": "2026-07-15",
            "next_followup_time": None, "last_outcome": "no_answer",
            "consecutive_no_answer": 1, "funding_status": "unknown",
            "lost_reason": None, "notes": "",
        },
        {
            "email": "bob@test.com", "last_name": "Dupont", "first_name": "Bob",
            "rep": "Adrien", "chaleur": 5, "arrived_on": "2026-05-01",
            "call_count": 2, "status": "qualified",
            "last_contact_date": "2026-07-18", "next_followup_date": "2026-07-22",
            "next_followup_time": None, "last_outcome": "interested",
            "consecutive_no_answer": 0, "funding_status": "unknown",
            "lost_reason": None, "notes": "",
        },
        {
            "email": "carol@test.com", "last_name": "Thomas", "first_name": "Carol",
            "rep": "Guillaume", "chaleur": 3, "arrived_on": "2026-06-01",
            "call_count": 5, "status": "contacting",
            "last_contact_date": "2026-07-01", "next_followup_date": "2026-07-20",
            "next_followup_time": None, "last_outcome": "no_answer",
            "consecutive_no_answer": 5, "funding_status": "unknown",
            "lost_reason": None, "notes": "",
        },
    ]
    for d in leads_data:
        upsert_lead(d, db_path=db_path)
    return db_path


@pytest.fixture(scope="module")
def client(seeded_db):
    import app.config as cfg
    import importlib
    import app.main
    importlib.reload(app.main)
    from app.main import app as fastapi_app
    return TestClient(fastapi_app)


class TestHealthEndpoint:
    def test_health_ok(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestQueueEndpoint:
    def test_queue_grouped(self, client):
        r = client.get("/api/queue?rep=Guillaume")
        assert r.status_code == 200
        data = r.json()
        assert "groups" in data
        group_names = [g["group"] for g in data["groups"]]
        assert "overdue" in group_names
        assert "today" in group_names
        assert "upcoming" in group_names

    def test_queue_sorted_by_priority(self, client):
        r = client.get("/api/queue?rep=Guillaume")
        data = r.json()
        for group in data["groups"]:
            priorities = [lead["priority"] for lead in group["leads"]]
            assert priorities == sorted(priorities, reverse=True)

    def test_stop_rule_lead_excluded(self, client):
        """Lead with 5+ calls and no real conversation should NOT be in queue."""
        r = client.get("/api/queue?rep=Guillaume")
        data = r.json()
        all_emails = [
            lead["email"]
            for g in data["groups"]
            for lead in g["leads"]
        ]
        assert "carol@test.com" not in all_emails


class TestLeadsEndpoint:
    def test_list_all_leads(self, client):
        r = client.get("/api/leads")
        assert r.status_code == 200
        assert len(r.json()) >= 3

    def test_filter_by_rep(self, client):
        r = client.get("/api/leads?rep=Adrien")
        assert r.status_code == 200
        leads = r.json()
        assert all(l["rep"] == "Adrien" for l in leads)

    def test_404_on_unknown_lead(self, client):
        r = client.get("/api/leads/99999")
        assert r.status_code == 404

    def test_lead_has_priority_and_reasons(self, client):
        r = client.get("/api/leads")
        lead = r.json()[0]
        assert "priority" in lead
        assert "reasons" in lead


class TestLogContactEndpoint:
    def test_log_no_answer_updates_lead(self, client):
        r = client.get("/api/leads?rep=Guillaume")
        leads = r.json()
        # Pick a non-stop-rule lead
        target = next((l for l in leads if l["call_count"] < 5), None)
        if not target:
            pytest.skip("No suitable lead")
        old_calls = target["call_count"]
        r2 = client.post(f"/api/leads/{target['id']}/log-contact", json={
            "outcome": "no_answer",
            "note": "Répondeur",
        })
        assert r2.status_code == 200
        resp = r2.json()
        assert resp["lead"]["call_count"] == old_calls + 1
        assert "toast" in resp

    def test_callback_requires_callback_at(self, client):
        r = client.get("/api/leads")
        lead_id = r.json()[0]["id"]
        r2 = client.post(f"/api/leads/{lead_id}/log-contact", json={
            "outcome": "callback_requested",
            # no callback_at
        })
        assert r2.status_code == 422

    def test_not_interested_requires_lost_reason(self, client):
        r = client.get("/api/leads")
        lead_id = r.json()[0]["id"]
        r2 = client.post(f"/api/leads/{lead_id}/log-contact", json={
            "outcome": "not_interested",
            # no lost_reason
        })
        assert r2.status_code == 422

    def test_log_contact_returns_next_lead(self, client):
        r = client.get("/api/leads?rep=Adrien")
        leads = r.json()
        if not leads:
            pytest.skip("No Adrien leads")
        lead_id = leads[0]["id"]
        r2 = client.post(f"/api/leads/{lead_id}/log-contact", json={
            "outcome": "no_answer",
        })
        assert r2.status_code == 200
        # next_lead may be None if only 1 lead in queue; just check it's present in response
        assert "next_lead" in r2.json()


class TestStatsEndpoint:
    def test_stats_returns_counts(self, client):
        r = client.get("/api/stats")
        assert r.status_code == 200
        data = r.json()
        assert "open_leads" in data
        assert "overdue" in data
        assert "forgotten_hot" in data

    def test_stats_per_rep(self, client):
        r = client.get("/api/stats?rep=Guillaume")
        assert r.status_code == 200
        assert r.json()["rep"] == "Guillaume"


class TestPatchEndpoint:
    def test_patch_notes(self, client):
        r = client.get("/api/leads")
        lead_id = r.json()[0]["id"]
        r2 = client.patch(f"/api/leads/{lead_id}", json={"notes": "Important client"})
        assert r2.status_code == 200
        assert r2.json()["notes"] == "Important client"


class TestSnoozeEndpoint:
    def test_snooze_pushes_followup(self, client):
        r = client.get("/api/leads")
        lead_id = r.json()[0]["id"]
        r2 = client.post(f"/api/leads/{lead_id}/snooze", json={"until": "2026-08-01"})
        assert r2.status_code == 200
        assert r2.json()["next_followup_date"] == "2026-08-01"
