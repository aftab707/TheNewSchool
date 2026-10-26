# Smart CRM - La Nouvelle École

> **Assessment project** by Aftab - La Nouvelle École technical challenge.
> A focused, functional sales CRM prototype answering the rep's daily question: *"Who do I call right now, and why?"*

---

## 1. Overview

La Nouvelle École manages ~100+ leads for its training courses (3D printing, drone piloting, CAD modelling). Four sales reps handle all leads primarily by phone.

**The core insight from the data:** 38 leads have Chaleur ≥ 7 (hot), yet 27 of them had only 1 call - hot leads are being under-followed while cold leads accumulate excessive contact attempts.

This CRM replaces a static Airtable export with a prioritised, explainable call queue.

---

## 2. Problem & Goal

> Sales reps struggle to identify which leads to follow up with, when to contact them, and which ones to prioritise.

| Question | Answer |
|---|---|
| **WHO** to contact? | Ranked queue per rep, topped by a hero card |
| **WHEN** | Every lead has a computed `next_followup_date` (business days) - queue shows Overdue / Today / Upcoming |
| **WHY this lead?** | Reason chips on every card (e.g. "Chaleur 9/10 · 4 days overdue · only 1 call") |
| **HOW to stay updated** | Reps log outcome in 2 clicks; the system schedules the next contact automatically |

---

## 3. Quick Start

```bash
# 1. Clone & install (Cloner et installer le projet)
git clone https://github.com/aftab707/TheNewSchool.git
cd TheNewSchool
python -m venv .venv

# Activate virtualenv (Activer l'environnement virtuel)
# Windows (PowerShell): .venv\Scripts\Activate.ps1
# Linux / macOS:        source .venv/bin/activate

pip install -r requirements.txt

# 2. Configure demo date (data is Apr–Jul 2026)
cp .env.example .env          # CRM_TODAY=2026-07-20

# 3. Seed database
python -m app.seed --csv data/Grid_view.csv

# 4. Run
uvicorn app.main:app --reload

# 5. Open http://localhost:8000

# Tests
pytest -v

# Docker
docker build -t smart-crm .
docker run -p 8000:8000 smart-crm
```

---

## 4. How Prioritisation Works

All weights live in [`app/core/config.py`](app/core/config.py) - a manager can tune any number without touching logic.

### Value score (0–100) - *"How worth is this lead?"*

```
value = chaleur × 10
      + 10  if last_outcome == "interested"
      + 10  if last_outcome == "callback_requested"
      +  5  if funding_status in {cpf, opco, france_travail, employer}
value = min(value, 100)
```

### Urgency score (0–100) - *"How time-critical is contact right now?"*

Let `d = today − next_followup_date` (days; positive = overdue):

```
if d ≥ 0  (due today or overdue):  urgency = 60 + min(40, d × 5)
else (future, k = −d days):        urgency = max(0, 40 − k × 10)
```

### Priority formula

```
priority = 0.55 × value + 0.45 × urgency + bonuses
```

| Bonus / Penalty | Effect | Reason chip |
|---|---|---|
| Hot lead (Chaleur ≥ 7), 1 call, new/contacting | +15 | "Lead chaud : un seul appel" |
| Callback promised, due/overdue | +20 | "Rappel demandé" |
| 3+ consecutive no-answers | × 0.6 | "3 appels sans réponse - essayer un e-mail" |
| 5+ calls, no real conversation | Excluded from queue | "5 tentatives - passer en nurture" |

### Cadence (default follow-up interval)

| Chaleur | Interval (business days) |
|---|---|
| 8–10 | 1 |
| 5–7 | 3 |
| 3–4 | 7 |
| 0–2 | 14 |

### Worked example

> **Lead:** Chaleur 8, 1 call (no answer), follow-up was 4 days ago.
> - Value = 80 (8×10) - no outcome bonuses
> - Urgency = 60 + 4×5 = **80**
> - Priority = 0.55×80 + 0.45×80 = **80**
> - Forgotten-hot bonus: +15 → **95**
> - Reason chips: `HOT`, `OVERDUE`, `FORGOTTEN_HOT`

---

## 5. Product Decisions

- **7 pipeline statuses** (new → contacting → qualified → funding → enrolled/lost/nurture) reflect the actual sales flow including CPF/OPCO funding, the most common blocker.
- **New fields added** (approved by team lead(Masy)): `status`, `last_contact_date`, `next_followup_date`, `last_outcome`, `funding_status`, `consecutive_no_answer`, `lost_reason`, `notes`, plus an `interactions` table for full history.
- **Outcome-driven automation**: logging a call *is* scheduling the next contact. Reps never edit dates by hand.
- **French UI** labels; code identifiers stay in English.
- **Daily capacity** (15 leads) caps the visible work queue so reps see a realistic list, not 80 items.

---

## 6. Technical Decisions

| Decision | Reason |
|---|---|
| **FastAPI + SQLite** | Zero-ops, appropriate for 100-lead prototype; repository layer makes swapping to Postgres/Airtable straightforward |
| **Vanilla JS** | No framework dependency; organised as modular functions; loads instantly |
| **Pure functions** (`scoring_service.py`, `workflow_service.py`) | Take data + today, return data. No side effects → trivially testable |
| **Config-driven** (`config.py`) | All weights, thresholds, cadences in one place - business-tunable without touching logic |
| **Repository layer** (`lead_repository.py`) | Single swap point for future Airtable/Postgres backend |
| **Deterministic "today"** | `CRM_TODAY` env var overrides `date.today()` → demo and tests are reproducible |

---

## 7. Data Notes & Assumptions

- **Chaleur 0–10 assumed** - Isolated in `config.py`; one-line change if the scale differs.
- **CSV quirks handled**: UTF-8 BOM (`utf-8-sig`), `M/D/YYYY` date format, accented characters in email local-parts (light `@`-check only, no ASCII-only validation).
- **Mock fields generated** deterministically (`random.Random(42)`): `status`, `last_contact_date`, `next_followup_date`, `last_outcome`, `funding_status`, `interactions`. The seed uses the same cadence function as the live app - no separate fake logic. State this clearly: the history is illustrative, not real.
- **Reference date**: `CRM_TODAY=2026-07-20` (day after the last lead arrival). Without this, every lead looks overdue since the data is from Apr–Jul 2026.
- **Leads per rep** (original data): Guillaume 34, Adrien 28, Antoine 24, Matthieu 14 - workload imbalance visible in the Team view.

---

## 8. Testing

Run with `pytest -v`. 81 automated tests across:

| File | Coverage |
|---|---|
| `test_scoring.py` | Value score (chaleur, bonuses, cap), urgency (due/overdue/future), priority (bonuses, fatigue, stop rule, clamping), reason chips |
| `test_workflow.py` | Every outcome → status, next date, counters; callback requires `callback_at`; lost requires `lost_reason`; counter reset |
| `test_calendar.py` | Friday+1=Monday, Saturday start, month boundary, holiday flag, zero-days raises |
| `test_seed.py` | BOM, accents, 100 rows, idempotent re-run, invalid row reported |
| `test_api.py` | Queue grouped + sorted, stop-rule exclusion, 404/422 validation, log-contact updates DB + returns next lead, patch, snooze, stats |

---

## 9. Limitations

- No authentication or per-rep login (single-tenant prototype)
- No Airtable two-way sync (CSV import only)
- Mock interaction history (not real historical data)
- Single timezone assumed (Europe/Paris)
- No real email/SMS sending
- French public holidays in `next_business_day()` are listed but disabled by default (stretch goal)

---

## 10. Next Steps

1. **Airtable two-way sync** via `pyairtable` behind the repository interface
2. **Auth per rep** (simple token or OAuth)
3. **Email/SMS templates** triggered on outcome logging
4. **Calendar integration** (Google Calendar / Outlook) for callback scheduling
5. **Conversion analytics** once real outcome data accumulates
6. **ML-assisted scoring** - the rules generate the labelled data needed to train a model

---

## Assumptions

| Assumption | Documentation |
|---|---|
| `Chaleur` scale is 0–10 (integer) | Client asked, not confirmed. Isolated in `config.py`. |
| `status`, `last_contact_date`, `next_followup_date`, etc. not in original data | Added with hiring lead approval. Generated as mock data. |
| Reference date is `2026-07-20` for demo | Data is Apr–Jul 2026; naive `date.today()` makes everything look overdue. Configurable via `CRM_TODAY` env var. |
| Business days = Mon–Fri (no holiday skipping by default) | French holidays listed in `app/services/calendar_service.py`, disabled pending confirmation. |
