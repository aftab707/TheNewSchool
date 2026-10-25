/**
 * Smart CRM — La Nouvelle École
 * app.js — Frontend application (vanilla JS, module pattern)
 */

// ============================================================
// API helpers
// ============================================================
const API = {
  async get(path) {
    const r = await fetch(path);
    if (!r.ok) throw new Error(`API error ${r.status}: ${path}`);
    return r.json();
  },
  async post(path, body) {
    const r = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || `API error ${r.status}`);
    }
    return r.json();
  },
  async patch(path, body) {
    const r = await fetch(path, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || `API error ${r.status}`);
    }
    return r.json();
  },
};

// ============================================================
// State
// ============================================================
const state = {
  rep: '',
  reps: [],
  queueData: null,
  allLeads: [],
  stats: null,
  teamData: [],
  currentHeroLeadId: null,
};

// ============================================================
// i18n (French labels)
// ============================================================
const OUTCOMES = [
  { code: 'no_answer',          label: 'Pas de réponse',     cls: '' },
  { code: 'voicemail',          label: 'Messagerie vocale',  cls: '' },
  { code: 'callback_requested', label: 'Rappel demandé',     cls: 'primary' },
  { code: 'interested',         label: 'Intéressé(e)',       cls: 'success' },
  { code: 'needs_funding_info', label: 'Besoin financement', cls: 'purple' },
  { code: 'not_interested',     label: 'Pas intéressé(e)',   cls: 'danger' },
  { code: 'enrolled',           label: 'Inscrit(e) ✓',       cls: 'success' },
];

const STATUS_LABELS = {
  new:        'Nouveau',
  contacting: 'En contact',
  qualified:  'Qualifié',
  funding:    'Financement',
  enrolled:   'Inscrit',
  lost:       'Perdu',
  nurture:    'À relancer',
};

const CHIP_CLASSES = {
  HOT:            '',
  OVERDUE:        'chip-danger',
  DUE_TODAY:      'chip-warn',
  FORGOTTEN_HOT:  'chip-danger',
  CALLBACK:       'chip-purple',
  FUNDING_PENDING:'chip-purple',
  FATIGUE:        'chip-warn',
  STOP:           'chip-danger',
};

const KANBAN_COLUMNS = [
  { status: 'new',        label: 'Nouveau' },
  { status: 'contacting', label: 'En contact' },
  { status: 'qualified',  label: 'Qualifié' },
  { status: 'funding',    label: 'Financement' },
  { status: 'nurture',    label: 'À relancer' },
  { status: 'enrolled',   label: 'Inscrit ✓' },
  { status: 'lost',       label: 'Perdu' },
];

// ============================================================
// Utility
// ============================================================
function chaleurClass(c) {
  if (c >= 8) return 'c-hot';
  if (c >= 5) return 'c-warm';
  if (c >= 3) return 'c-mild';
  return 'c-cold';
}

function priorityClass(p) {
  if (p >= 75) return 'p1';
  if (p >= 50) return 'p2';
  if (p >= 25) return 'p3';
  return 'p4';
}

function priorityLabel(p) {
  if (p >= 75) return 'P1';
  if (p >= 50) return 'P2';
  if (p >= 25) return 'P3';
  return 'P4';
}

function renderChips(reasons) {
  return reasons.map(r => {
    const cls = CHIP_CLASSES[r.code] || '';
    return `<span class="chip ${cls}" title="${r.label_en}">${r.label_fr}</span>`;
  }).join('');
}

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 4000);
}

function setLoading(elId, msg = 'Chargement…') {
  const el = document.getElementById(elId);
  if (el) el.innerHTML = `<div class="loading">${msg}</div>`;
}

function formatDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso + 'T00:00:00');
  return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' });
}

// ============================================================
// Rep selector
// ============================================================
async function loadReps() {
  const reps = await API.get('/api/reps');
  state.reps = reps;
  const sel = document.getElementById('rep-select');
  sel.innerHTML = reps.map(r =>
    `<option value="${r.rep}">${r.rep} (${r.open_leads})</option>`
  ).join('');
  if (reps.length) {
    state.rep = reps[0].rep;
    sel.value = state.rep;
  }
  // Also fill kanban filter
  const kSel = document.getElementById('kanban-rep-filter');
  if (kSel) {
    kSel.innerHTML = '<option value="">Tous les commerciaux</option>' +
      reps.map(r => `<option value="${r.rep}">${r.rep}</option>`).join('');
  }
}

async function onRepChange() {
  state.rep = document.getElementById('rep-select').value;
  await refreshTodayView();
}

// ============================================================
// TODAY VIEW
// ============================================================
async function refreshTodayView() {
  if (!state.rep) return;
  setLoading('quick-stats', '');
  setLoading('hero-card', 'Chargement du prochain lead…');
  setLoading('queue-list', '');

  try {
    const [queue, stats] = await Promise.all([
      API.get(`/api/queue?rep=${encodeURIComponent(state.rep)}`),
      API.get(`/api/stats?rep=${encodeURIComponent(state.rep)}`),
    ]);
    state.queueData = queue;
    state.stats = stats;

    // Update date badge
    document.getElementById('today-badge').textContent =
      `📅 ${formatDate(queue.today)}`;

    renderQuickStats(stats);
    renderHeroCard(queue);
    renderQueueList(queue);
  } catch (e) {
    document.getElementById('hero-card').innerHTML =
      `<div class="empty-state"><span class="emoji">⚠️</span>${e.message}</div>`;
  }
}

function renderQuickStats(stats) {
  const el = document.getElementById('quick-stats');
  el.innerHTML = [
    { label: 'En retard',    val: stats.overdue,       cls: 'danger' },
    { label: 'Aujourd\'hui', val: stats.due_today,     cls: 'warning' },
    { label: 'À venir',      val: stats.upcoming,      cls: 'info' },
    { label: 'Leads chauds oubliés', val: stats.forgotten_hot, cls: 'danger' },
    { label: 'Fatigués',     val: stats.fatigued,      cls: 'warning' },
  ].map(s => `
    <div class="stat-chip ${s.cls}">
      <span class="num">${s.val}</span>
      <span>${s.label}</span>
    </div>
  `).join('');
}

function renderHeroCard(queue) {
  const el = document.getElementById('hero-card');

  // Find the top lead (first of overdue, then today, then upcoming)
  let lead = null;
  for (const group of queue.groups) {
    if (group.leads.length) { lead = group.leads[0]; break; }
  }
  state.currentHeroLeadId = lead ? lead.id : null;

  if (!lead) {
    el.innerHTML = `
      <div class="hero-empty">
        <span style="font-size:2.5rem">🎉</span><br/>
        Bravo, plus rien à faire aujourd'hui !
      </div>`;
    return;
  }

  const cClass = chaleurClass(lead.chaleur);
  const chipsHtml = renderChips(lead.reasons);
  const channel = lead.suggested_channel === 'email'
    ? '📧 Essayer un e-mail'
    : '📞 Appeler';

  el.innerHTML = `
    <div class="hero-label">⭐ Prochain lead à contacter</div>
    <div class="hero-name">${lead.first_name || ''} ${lead.last_name || ''}</div>
    <div class="hero-meta">
      <span class="chaleur-badge ${cClass}">🔥 Chaleur ${lead.chaleur}/10</span>
      <span class="chip">${STATUS_LABELS[lead.status] || lead.status}</span>
      <span class="chip">${channel}</span>
    </div>
    <div class="hero-email">✉️ ${lead.email}</div>
    ${lead.last_contact_date ? `<div class="hero-email">Dernier contact : ${formatDate(lead.last_contact_date)}</div>` : ''}
    ${lead.funding_status !== 'unknown' ? `<div class="hero-email">Financement : ${lead.funding_status.toUpperCase()}</div>` : ''}
    <div class="hero-chips">${chipsHtml}</div>
    <div class="outcome-buttons">
      ${OUTCOMES.map(o =>
        `<button class="btn-outcome ${o.cls}" data-outcome="${o.code}" data-lead-id="${lead.id}">${o.label}</button>`
      ).join('')}
    </div>
  `;

  // Bind outcome buttons
  el.querySelectorAll('.btn-outcome').forEach(btn => {
    btn.addEventListener('click', () => openLogModal(lead, btn.dataset.outcome));
  });
}

function renderQueueList(queue) {
  const el = document.getElementById('queue-list');
  if (!queue.groups.every(g => g.leads.length === 0)) {
    const groupClasses = { overdue: 'overdue', today: 'today', upcoming: 'upcoming' };
    el.innerHTML = queue.groups.map(group => {
      if (!group.leads.length) return '';
      return `
        <div class="queue-group">
          <div class="queue-group-title ${groupClasses[group.group]}">
            ${group.label_fr}
            <span class="group-count">${group.leads.length}</span>
          </div>
          ${group.leads.map((lead, i) => renderLeadRow(lead, i, queue.daily_capacity)).join('')}
        </div>`;
    }).join('');

    // Bind row buttons
    el.querySelectorAll('.btn-log-row').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const leadId = parseInt(btn.dataset.leadId);
        const lead = findLeadInQueue(queue, leadId);
        if (lead) openLogModal(lead, 'no_answer');
      });
    });
  } else {
    el.innerHTML = '';
  }
}

function findLeadInQueue(queue, leadId) {
  for (const g of queue.groups) {
    const found = g.leads.find(l => l.id === leadId);
    if (found) return found;
  }
  return null;
}

function renderLeadRow(lead, index, capacity) {
  const pClass = priorityClass(lead.priority);
  const pLabel = priorityLabel(lead.priority);
  const chipsHtml = renderChips(lead.reasons.slice(0, 3));
  const marker = index === capacity ? 'capacity-marker' : '';
  return `
    <div class="lead-row ${marker}" title="Priorité : ${lead.priority}">
      <div class="priority-badge ${pClass}" title="${pLabel}">${pLabel}</div>
      <div class="lead-name">${lead.first_name || ''} ${lead.last_name || ''}</div>
      <div class="lead-chips">${chipsHtml}</div>
      <div class="lead-actions">
        <button class="btn-log-row" data-lead-id="${lead.id}" aria-label="Enregistrer contact pour ${lead.first_name || ''} ${lead.last_name || ''}">
          Contacter
        </button>
      </div>
    </div>`;
}

// ============================================================
// LOG CONTACT MODAL
// ============================================================
let _modalLead = null;
let _modalOutcome = null;

function openLogModal(lead, defaultOutcome) {
  _modalLead = lead;
  _modalOutcome = defaultOutcome;

  const container = document.getElementById('log-form-container');
  container.innerHTML = renderLogForm(lead, defaultOutcome);

  // Update outcome select listener
  container.querySelector('#modal-outcome').addEventListener('change', (e) => {
    _modalOutcome = e.target.value;
    updateModalExtraFields(container, _modalOutcome, lead);
  });
  updateModalExtraFields(container, defaultOutcome, lead);

  document.getElementById('log-modal').classList.remove('hidden');
  document.getElementById('modal-outcome').focus();
}

function renderLogForm(lead, defaultOutcome) {
  return `
    <div class="form-group">
      <label for="modal-outcome">Résultat de l'appel</label>
      <select id="modal-outcome" class="form-control">
        ${OUTCOMES.map(o =>
          `<option value="${o.code}" ${o.code === defaultOutcome ? 'selected' : ''}>${o.label}</option>`
        ).join('')}
      </select>
    </div>
    <div id="extra-fields"></div>
    <div class="form-group">
      <label for="modal-note">Note (optionnel)</label>
      <textarea id="modal-note" class="form-control" rows="2" placeholder="Remarques…"></textarea>
    </div>
  `;
}

function updateModalExtraFields(container, outcome, lead) {
  const extra = container.querySelector('#extra-fields');
  let html = '';
  if (outcome === 'callback_requested') {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const iso = tomorrow.toISOString().split('T')[0];
    html = `
      <div class="form-group">
        <label for="modal-callback-at">Date/heure du rappel <span style="color:red">*</span></label>
        <input type="datetime-local" id="modal-callback-at" class="form-control" value="${iso}T09:00" required />
      </div>`;
  } else if (outcome === 'not_interested') {
    html = `
      <div class="form-group">
        <label for="modal-lost-reason">Raison de la perte <span style="color:red">*</span></label>
        <input type="text" id="modal-lost-reason" class="form-control" placeholder="ex : Prix trop élevé" required />
      </div>`;
  } else if (outcome === 'needs_funding_info') {
    html = `
      <div class="form-group">
        <label for="modal-funding">Type de financement</label>
        <select id="modal-funding" class="form-control">
          <option value="">Inconnu</option>
          <option value="cpf">CPF</option>
          <option value="opco">OPCO</option>
          <option value="france_travail">France Travail</option>
          <option value="self">Auto-financement</option>
          <option value="employer">Employeur</option>
        </select>
      </div>`;
  }
  extra.innerHTML = html;
}

function closeLogModal() {
  document.getElementById('log-modal').classList.add('hidden');
  _modalLead = null;
  _modalOutcome = null;
}

async function submitLogContact() {
  if (!_modalLead || !_modalOutcome) return;
  const btn = document.getElementById('modal-submit');
  btn.disabled = true;
  btn.textContent = 'Enregistrement…';

  const body = {
    outcome: _modalOutcome,
    note: document.getElementById('modal-note')?.value || '',
  };

  const callbackEl = document.getElementById('modal-callback-at');
  if (callbackEl) {
    body.callback_at = callbackEl.value;
  }
  const lostEl = document.getElementById('modal-lost-reason');
  if (lostEl) {
    body.lost_reason = lostEl.value;
  }
  const fundingEl = document.getElementById('modal-funding');
  if (fundingEl && fundingEl.value) {
    body.funding_status = fundingEl.value;
  }

  try {
    const resp = await API.post(`/api/leads/${_modalLead.id}/log-contact`, body);
    closeLogModal();
    showToast(resp.toast);
    await refreshTodayView();
    if (resp.next_lead) {
      showToast(`${resp.toast} · Prochain : ${resp.next_lead.first_name || ''} ${resp.next_lead.last_name || ''}`);
    }
  } catch (e) {
    showToast(`⚠️ Erreur : ${e.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Enregistrer';
  }
}

// ============================================================
// KANBAN VIEW
// ============================================================
let _dragLeadId = null;
let _dragLeadStatus = null;
let _kanbanRep = '';
let _kanbanSearch = '';

async function refreshKanban() {
  const el = document.getElementById('kanban-board');
  el.innerHTML = '<div class="loading">Chargement du pipeline…</div>';
  try {
    const params = new URLSearchParams();
    if (_kanbanRep) params.set('rep', _kanbanRep);
    if (_kanbanSearch) params.set('q', _kanbanSearch);
    const leads = await API.get(`/api/leads?${params}`);
    state.allLeads = leads;
    renderKanban(leads);
  } catch (e) {
    el.innerHTML = `<div class="loading">⚠️ ${e.message}</div>`;
  }
}

function renderKanban(leads) {
  const board = document.getElementById('kanban-board');
  board.innerHTML = '';

  const grouped = {};
  KANBAN_COLUMNS.forEach(c => { grouped[c.status] = []; });
  leads.forEach(l => { if (grouped[l.status]) grouped[l.status].push(l); });

  KANBAN_COLUMNS.forEach(col => {
    const colLeads = grouped[col.status] || [];
    const colEl = document.createElement('div');
    colEl.className = 'kanban-col';
    colEl.dataset.status = col.status;
    colEl.innerHTML = `
      <div class="kanban-col-header">
        ${col.label}
        <span class="kanban-count">${colLeads.length}</span>
      </div>
    `;

    colLeads.forEach(lead => {
      const card = document.createElement('div');
      card.className = 'kanban-card';
      card.draggable = true;
      card.dataset.leadId = lead.id;
      const pClass = priorityClass(lead.priority || 0);
      card.innerHTML = `
        <div class="k-name">
          <span class="priority-badge ${pClass}" style="display:inline-flex;width:1.5rem;height:1.5rem;font-size:.7rem">
            ${priorityLabel(lead.priority || 0)}
          </span>
          ${lead.first_name || ''} ${lead.last_name || ''}
        </div>
        <div class="k-meta">
          <span class="chaleur-badge ${chaleurClass(lead.chaleur)}" style="font-size:.72rem;padding:.1rem .4rem">🔥${lead.chaleur}</span>
          ${lead.rep} · ${lead.call_count} appel${lead.call_count !== 1 ? 's' : ''}
        </div>
        <div class="k-chips">${renderChips((lead.reasons || []).slice(0, 2))}</div>
      `;

      card.addEventListener('dragstart', (e) => {
        _dragLeadId = lead.id;
        _dragLeadStatus = lead.status;
        e.dataTransfer.effectAllowed = 'move';
      });
      card.addEventListener('dragend', () => {
        _dragLeadId = null;
        _dragLeadStatus = null;
      });
      colEl.appendChild(card);
    });

    // Drop zone events
    colEl.addEventListener('dragover', (e) => { e.preventDefault(); colEl.classList.add('drag-over'); });
    colEl.addEventListener('dragleave', () => colEl.classList.remove('drag-over'));
    colEl.addEventListener('drop', async (e) => {
      e.preventDefault();
      colEl.classList.remove('drag-over');
      if (!_dragLeadId || col.status === _dragLeadStatus) return;

      // Require lost_reason for lost, require note for enrolled
      if (col.status === 'lost') {
        const reason = prompt('Raison de la perte (obligatoire) :');
        if (!reason) return;
        await API.patch(`/api/leads/${_dragLeadId}`, { status: col.status, lost_reason: reason });
      } else {
        await API.patch(`/api/leads/${_dragLeadId}`, { status: col.status });
      }
      showToast(`Lead déplacé vers « ${col.label} »`);
      refreshKanban();
    });

    board.appendChild(colEl);
  });

  if (!leads.length) {
    board.innerHTML = `<div class="empty-state"><span class="emoji">✨</span>Aucun lead trouvé.</div>`;
  }
}

// ============================================================
// TEAM VIEW
// ============================================================
async function refreshTeamView() {
  const el = document.getElementById('team-grid');
  el.innerHTML = '<div class="loading">Chargement de l\'équipe…</div>';
  try {
    const reps = await API.get('/api/reps');
    const statsAll = await API.get('/api/stats');
    renderTeamView(reps, statsAll);
  } catch (e) {
    el.innerHTML = `<div class="loading">⚠️ ${e.message}</div>`;
  }
}

function renderTeamView(reps, statsAll) {
  const insight = document.getElementById('team-insight');
  insight.textContent =
    `⚡ ${statsAll.forgotten_hot} leads chauds (Chaleur ≥ 7) n'ont reçu qu'un seul appel. ` +
    `Répartition inégale : de ${Math.min(...reps.map(r=>r.open_leads))} à ${Math.max(...reps.map(r=>r.open_leads))} leads par commercial.`;

  const grid = document.getElementById('team-grid');
  grid.innerHTML = reps.map(r => `
    <div class="team-card">
      <div class="rep-name">👤 ${r.rep}</div>
      <div class="team-stat-row">
        <span class="label">Leads ouverts</span>
        <span class="val">${r.open_leads}</span>
      </div>
      <div class="team-stat-row">
        <span class="label">En retard</span>
        <span class="val ${r.overdue > 0 ? 'danger' : ''}">${r.overdue}</span>
      </div>
      <div class="team-stat-row">
        <span class="label">Leads chauds oubliés</span>
        <span class="val ${r.forgotten_hot > 0 ? 'warn' : ''}">${r.forgotten_hot}</span>
      </div>
      <div class="team-stat-row">
        <span class="label">Fatigués (3+ sans réponse)</span>
        <span class="val ${r.fatigued > 0 ? 'warn' : ''}">${r.fatigued}</span>
      </div>
      <div class="team-stat-row">
        <span class="label">Aujourd'hui</span>
        <span class="val">${r.due_today}</span>
      </div>
    </div>
  `).join('');
}

// ============================================================
// TAB NAVIGATION
// ============================================================
function setupTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => {
        b.classList.remove('active');
        b.setAttribute('aria-selected', 'false');
      });
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      btn.setAttribute('aria-selected', 'true');
      const panelId = `tab-${btn.dataset.tab}`;
      document.getElementById(panelId).classList.add('active');

      if (btn.dataset.tab === 'kanban') refreshKanban();
      if (btn.dataset.tab === 'team') refreshTeamView();
    });
  });
}

// ============================================================
// MODAL & FORM EVENTS
// ============================================================
function setupModalEvents() {
  document.getElementById('modal-cancel').addEventListener('click', closeLogModal);
  document.getElementById('modal-submit').addEventListener('click', submitLogContact);
  document.getElementById('log-modal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) closeLogModal();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeLogModal();
  });
}

// ============================================================
// KANBAN FILTER EVENTS
// ============================================================
function setupKanbanFilters() {
  document.getElementById('kanban-search').addEventListener('input', (e) => {
    _kanbanSearch = e.target.value.trim();
    refreshKanban();
  });
  document.getElementById('kanban-rep-filter').addEventListener('change', (e) => {
    _kanbanRep = e.target.value;
    refreshKanban();
  });
}

// ============================================================
// INIT
// ============================================================
async function init() {
  setupTabs();
  setupModalEvents();
  setupKanbanFilters();

  document.getElementById('rep-select').addEventListener('change', onRepChange);

  try {
    await loadReps();
    await refreshTodayView();
  } catch (e) {
    document.getElementById('hero-card').innerHTML =
      `<div class="empty-state"><span class="emoji">⚠️</span>Impossible de charger les données.<br/>${e.message}</div>`;
  }
}

init();
