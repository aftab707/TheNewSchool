/**
 * Smart CRM — La Nouvelle École
 * app.js — Frontend application (vanilla JS, module pattern)
 * Fully bilingual (FR / EN toggle) with proper-name preservation.
 */


// API helpers

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


// State

const state = {
  lang: localStorage.getItem('crm_lang') || 'en', // Default to EN for ease of use, with one-click FR
  rep: '',
  reps: [],
  queueData: null,
  allLeads: [],
  stats: null,
  teamData: [],
  currentHeroLeadId: null,
  activeQueueFilter: 'overdue', // 'overdue' | 'today' | 'upcoming' | 'all'
  queueSearchQuery: '',
};


// i18n Dictionary (FR / EN)

const I18N = {
  fr: {
    today_tab: "📋 Aujourd'hui",
    pipeline_tab: '📊 Pipeline',
    team_tab: '👥 Équipe',
    rep_loading: 'Chargement…',
    all_reps: 'Tous les commerciaux',
    stat_overdue: 'En retard',
    stat_today: "Aujourd'hui",
    stat_upcoming: 'À venir',
    stat_forgotten_hot: 'Leads chauds oubliés',
    stat_fatigued: 'Fatigués',
    sidebar_title: '📁 File de travail',
    sidebar_desc: 'Filtrer par urgence de rappel',
    filter_overdue: 'En retard',
    filter_today: "Aujourd'hui",
    filter_upcoming: 'À venir',
    filter_all: 'Tous les leads',
    queue_search_ph: '🔍 Filtrer par nom ou e-mail…',
    sidebar_hint: 'Cliquez sur un prospect dans la liste pour charger ses détails directement dans la carte du haut.',
    panel_title_overdue: '🚨 En retard (Overdue)',
    panel_desc_overdue: 'Prospects dont la date de relance prévue est déjà dépassée.',
    panel_title_today: "⚡ À contacter aujourd'hui (Today)",
    panel_desc_today: 'Prospects prévus pour un contact dans la journée.',
    panel_title_upcoming: '📅 À venir (Upcoming)',
    panel_desc_upcoming: 'Prospects programmés dans les 7 prochains jours.',
    panel_title_all: '📋 Tous les leads de la file',
    panel_desc_all: 'Tous les prospects actifs triés par score de priorité.',
    lead_count: (n) => `${n} prospect${n > 1 ? 's' : ''}`,
    empty_overdue: '🎉 Bravo ! Aucun prospect en retard dans votre file.',
    empty_today: "☀️ Aucun appel planifié pour aujourd'hui.",
    empty_upcoming: '📅 Aucun rappel programmé pour les 7 prochains jours.',
    empty_search: (q) => `🔍 Aucun résultat trouvé pour "${q}".`,
    empty_cat: 'Aucun prospect dans cette catégorie.',
    btn_contact: 'Contacter',
    hero_title: '⭐ Prochain lead à contacter',
    hero_empty: "Bravo, plus rien à faire aujourd'hui !",
    heat: 'Chaleur',
    call_channel: '📞 Appeler',
    email_channel: '📧 Essayer un e-mail',
    last_contact: 'Dernier contact :',
    funding_label: 'Financement :',
    loading_hero: 'Chargement du prochain lead…',
    kanban_search_ph: '🔍 Rechercher un lead…',
    kanban_all_reps: 'Tous les commerciaux',
    kanban_empty: 'Aucun lead trouvé.',
    call_count_label: (n) => `${n} appel${n !== 1 ? 's' : ''}`,
    toast_moved: (col) => `Lead déplacé vers « ${col} »`,
    prompt_lost_reason: 'Raison de la perte (obligatoire) :',
    team_heading: 'Vue équipe',
    team_open_leads: 'Leads ouverts',
    team_overdue: 'En retard',
    team_forgotten_hot: 'Leads chauds oubliés',
    team_fatigued: 'Fatigués (3+ sans réponse)',
    team_today: "Aujourd'hui",
    team_insight: (forgotten, min, max) =>
      `⚡ ${forgotten} leads chauds (Chaleur ≥ 7) n'ont reçu qu'un seul appel. Répartition inégale : de ${min} à ${max} leads par commercial.`,
    modal_title: 'Enregistrer un contact',
    modal_outcome_lbl: "Résultat de l'appel",
    modal_note_lbl: 'Note (optionnel)',
    modal_note_ph: 'Remarques…',
    modal_cancel: 'Annuler',
    modal_submit: 'Enregistrer',
    modal_saving: 'Enregistrement…',
    modal_callback_lbl: 'Date/heure du rappel',
    modal_lost_lbl: 'Raison de la perte',
    modal_lost_ph: 'ex : Prix trop élevé',
    modal_funding_lbl: 'Type de financement',
    modal_funding_unknown: 'Inconnu',
    modal_funding_self: 'Auto-financement',
    modal_funding_employer: 'Employeur',
    outcomes: {
      no_answer: 'Pas de réponse',
      voicemail: 'Messagerie vocale',
      callback_requested: 'Rappel demandé',
      interested: 'Intéressé(e)',
      needs_funding_info: 'Besoin financement',
      not_interested: 'Pas intéressé(e)',
      enrolled: 'Inscrit(e) ✓',
    },
    statuses: {
      new: 'Nouveau',
      contacting: 'En contact',
      qualified: 'Qualifié',
      funding: 'Financement',
      nurture: 'À relancer plus tard',
      enrolled: 'Inscrit ✓',
      lost: 'Perdu',
    },
  },
  en: {
    today_tab: '📋 Today',
    pipeline_tab: '📊 Pipeline',
    team_tab: '👥 Team',
    rep_loading: 'Loading…',
    all_reps: 'All Sales Reps',
    stat_overdue: 'Overdue',
    stat_today: 'Today',
    stat_upcoming: 'Upcoming',
    stat_forgotten_hot: 'Forgotten hot leads',
    stat_fatigued: 'Tired (fatigued)',
    sidebar_title: '📁 Work Queue',
    sidebar_desc: 'Filter by follow-up urgency',
    filter_overdue: 'Overdue',
    filter_today: 'Today',
    filter_upcoming: 'Upcoming',
    filter_all: 'All Leads',
    queue_search_ph: '🔍 Filter by name or email…',
    sidebar_hint: 'Click any prospect in the list to load their details into the top card.',
    panel_title_overdue: '🚨 Overdue',
    panel_desc_overdue: 'Leads whose scheduled follow-up date has passed.',
    panel_title_today: '⚡ Due Today',
    panel_desc_today: 'Leads scheduled for contact today.',
    panel_title_upcoming: '📅 Upcoming',
    panel_desc_upcoming: 'Leads scheduled for follow-up in the next 7 days.',
    panel_title_all: '📋 All Queue Leads',
    panel_desc_all: 'All active prospects sorted by priority score.',
    lead_count: (n) => `${n} lead${n !== 1 ? 's' : ''}`,
    empty_overdue: '🎉 Great job! No overdue leads in your queue.',
    empty_today: '☀️ No calls scheduled for today.',
    empty_upcoming: '📅 No follow-ups scheduled for the next 7 days.',
    empty_search: (q) => `🔍 No results found for "${q}".`,
    empty_cat: 'No leads in this category.',
    btn_contact: 'Contact',
    hero_title: '⭐ Next lead to contact',
    hero_empty: 'Well done, all clear for today!',
    heat: 'Warmth',
    call_channel: '📞 Call',
    email_channel: '📧 Try an email',
    last_contact: 'Last contact:',
    funding_label: 'Funding:',
    loading_hero: 'Loading next lead…',
    kanban_search_ph: '🔍 Search a lead…',
    kanban_all_reps: 'All sales reps',
    kanban_empty: 'No leads found.',
    call_count_label: (n) => `${n} call${n !== 1 ? 's' : ''}`,
    toast_moved: (col) => `Lead moved to « ${col} »`,
    prompt_lost_reason: 'Reason for loss (required):',
    team_heading: 'Team Overview',
    team_open_leads: 'Open leads',
    team_overdue: 'Overdue',
    team_forgotten_hot: 'Forgotten hot leads',
    team_fatigued: 'Tired (3+ no answer)',
    team_today: 'Today',
    team_insight: (forgotten, min, max) =>
      `⚡ ${forgotten} hot leads (Warmth ≥ 7) received only one call. Uneven distribution: from ${min} to ${max} leads per salesperson.`,
    modal_title: 'Log a contact',
    modal_outcome_lbl: 'Call outcome',
    modal_note_lbl: 'Note (optional)',
    modal_note_ph: 'Comments, next steps…',
    modal_cancel: 'Cancel',
    modal_submit: 'Save',
    modal_saving: 'Saving…',
    modal_callback_lbl: 'Callback date/time',
    modal_lost_lbl: 'Reason for loss',
    modal_lost_ph: 'e.g., Budget too high',
    modal_funding_lbl: 'Funding type',
    modal_funding_unknown: 'Unknown',
    modal_funding_self: 'Self-funded',
    modal_funding_employer: 'Employer',
    outcomes: {
      no_answer: 'No answer',
      voicemail: 'Voicemail',
      callback_requested: 'Callback requested',
      interested: 'Interested',
      needs_funding_info: 'Funding requirement',
      not_interested: 'Not interested',
      enrolled: 'Registered ✓',
    },
    statuses: {
      new: 'New',
      contacting: 'In contact',
      qualified: 'Qualified',
      funding: 'Funding',
      nurture: 'Follow up later',
      enrolled: 'Registered ✓',
      lost: 'Lost',
    },
  },
};

function t(key, ...args) {
  const dict = I18N[state.lang] || I18N.en;
  const val = dict[key];
  if (typeof val === 'function') {
    return val(...args);
  }
  return val !== undefined ? val : key;
}

const OUTCOMES_CONFIG = [
  { code: 'no_answer',          cls: '' },
  { code: 'voicemail',          cls: '' },
  { code: 'callback_requested', cls: 'primary' },
  { code: 'interested',         cls: 'success' },
  { code: 'needs_funding_info', cls: 'purple' },
  { code: 'not_interested',     cls: 'danger' },
  { code: 'enrolled',           cls: 'success' },
];

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

const KANBAN_STATUSES = [
  'new',
  'contacting',
  'qualified',
  'funding',
  'nurture',
  'enrolled',
  'lost',
];


// Utility

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
    const label = state.lang === 'en' ? (r.label_en || r.label_fr) : (r.label_fr || r.label_en);
    const tooltip = state.lang === 'en' ? (r.label_fr || '') : (r.label_en || '');
    return `<span class="chip ${cls}" title="${tooltip}">${label}</span>`;
  }).join('');
}

function showToast(msg) {
  const tEl = document.getElementById('toast');
  tEl.textContent = msg;
  tEl.classList.add('show');
  setTimeout(() => tEl.classList.remove('show'), 4000);
}

function setLoading(elId, msg = '') {
  const el = document.getElementById(elId);
  const text = msg || t('rep_loading');
  if (el) el.innerHTML = `<div class="loading">${text}</div>`;
}

function formatDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso + 'T00:00:00');
  const locale = state.lang === 'en' ? 'en-US' : 'fr-FR';
  return d.toLocaleDateString(locale, { day: 'numeric', month: 'short', year: 'numeric' });
}


// Language Switcher

function setLanguage(lang) {
  if (lang !== 'fr' && lang !== 'en') return;
  state.lang = lang;
  localStorage.setItem('crm_lang', lang);

  // Update HTML lang attribute
  const htmlRoot = document.getElementById('html-root');
  if (htmlRoot) htmlRoot.setAttribute('lang', lang);

  // Update button active state
  document.getElementById('btn-lang-fr')?.classList.toggle('active', lang === 'fr');
  document.getElementById('btn-lang-en')?.classList.toggle('active', lang === 'en');

  // Update static DOM labels
  updateStaticLabels();

  // Re-render currently active view
  if (state.rep && state.queueData) {
    document.getElementById('today-badge').textContent = `📅 ${formatDate(state.queueData.today)}`;
    if (state.stats) renderQuickStats(state.stats);
    renderQueueSidebar(state.queueData);
    const currentLead = state.currentHeroLeadId
      ? findLeadInQueue(state.queueData, state.currentHeroLeadId)
      : null;
    renderHeroCard(state.queueData, currentLead);
    renderQueueList(state.queueData);
  }

  const activeTab = document.querySelector('.tab-btn.active')?.dataset.tab;
  if (activeTab === 'kanban') {
    refreshKanban();
  } else if (activeTab === 'team') {
    refreshTeamView();
  }
}

function updateStaticLabels() {
  const el = (id) => document.getElementById(id);

  if (el('tab-btn-today')) el('tab-btn-today').textContent = t('today_tab');
  if (el('tab-btn-kanban')) el('tab-btn-kanban').textContent = t('pipeline_tab');
  if (el('tab-btn-team')) el('tab-btn-team').textContent = t('team_tab');

  if (el('sidebar-title-text')) el('sidebar-title-text').textContent = t('sidebar_title');
  if (el('sidebar-desc-text')) el('sidebar-desc-text').textContent = t('sidebar_desc');

  if (el('label-filter-overdue')) el('label-filter-overdue').textContent = t('filter_overdue');
  if (el('label-filter-today')) el('label-filter-today').textContent = t('filter_today');
  if (el('label-filter-upcoming')) el('label-filter-upcoming').textContent = t('filter_upcoming');
  if (el('label-filter-all')) el('label-filter-all').textContent = t('filter_all');

  if (el('queue-search')) el('queue-search').placeholder = t('queue_search_ph');
  if (el('sidebar-hint-text')) el('sidebar-hint-text').textContent = t('sidebar_hint');

  if (el('kanban-search')) el('kanban-search').placeholder = t('kanban_search_ph');
  if (el('team-heading-text')) el('team-heading-text').textContent = t('team_heading');

  if (el('modal-title')) el('modal-title').textContent = t('modal_title');
  if (el('modal-cancel')) el('modal-cancel').textContent = t('modal_cancel');
  if (el('modal-submit')) el('modal-submit').textContent = t('modal_submit');

  // Update Kanban rep filter first option
  const kSel = el('kanban-rep-filter');
  if (kSel && kSel.options.length > 0) {
    kSel.options[0].textContent = t('all_reps');
  }
}


// Rep selector

async function loadReps() {
  const reps = await API.get('/api/reps');
  state.reps = reps;
  const sel = document.getElementById('rep-select');
  sel.innerHTML = reps.map(r =>
    `<option value="${r.rep}" class="notranslate" translate="no">${r.rep} (${r.open_leads})</option>`
  ).join('');
  if (reps.length) {
    state.rep = reps[0].rep;
    sel.value = state.rep;
  }
  // Also fill kanban filter
  const kSel = document.getElementById('kanban-rep-filter');
  if (kSel) {
    kSel.innerHTML = `<option value="">${t('all_reps')}</option>` +
      reps.map(r => `<option value="${r.rep}" class="notranslate" translate="no">${r.rep}</option>`).join('');
  }
}

async function onRepChange() {
  state.rep = document.getElementById('rep-select').value;
  await refreshTodayView();
}


// TODAY VIEW

async function refreshTodayView() {
  if (!state.rep) return;
  setLoading('quick-stats', '');
  setLoading('hero-card', t('loading_hero'));
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
    renderQueueSidebar(queue);
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
    { label: t('stat_overdue'),        val: stats.overdue,       cls: 'danger' },
    { label: t('stat_today'),          val: stats.due_today,     cls: 'warning' },
    { label: t('stat_upcoming'),       val: stats.upcoming,      cls: 'info' },
    { label: t('stat_forgotten_hot'),  val: stats.forgotten_hot, cls: 'danger' },
    { label: t('stat_fatigued'),       val: stats.fatigued,      cls: 'warning' },
  ].map(s => `
    <div class="stat-chip ${s.cls}">
      <span class="num">${s.val}</span>
      <span>${s.label}</span>
    </div>
  `).join('');
}

function renderQueueSidebar(queue) {
  const overdueCount = queue.groups.find(g => g.group === 'overdue')?.leads.length || 0;
  const todayCount = queue.groups.find(g => g.group === 'today')?.leads.length || 0;
  const upcomingCount = queue.groups.find(g => g.group === 'upcoming')?.leads.length || 0;
  const totalCount = overdueCount + todayCount + upcomingCount;

  // Update badges
  const bOverdue = document.getElementById('badge-overdue');
  const bToday = document.getElementById('badge-today');
  const bUpcoming = document.getElementById('badge-upcoming');
  const bAll = document.getElementById('badge-all');

  if (bOverdue) bOverdue.textContent = overdueCount;
  if (bToday) bToday.textContent = todayCount;
  if (bUpcoming) bUpcoming.textContent = upcomingCount;
  if (bAll) bAll.textContent = totalCount;

  // Intelligent filter fallback
  if (state.activeQueueFilter === 'today' && todayCount === 0 && overdueCount > 0) {
    state.activeQueueFilter = 'overdue';
  } else if (state.activeQueueFilter === 'overdue' && overdueCount === 0 && todayCount > 0) {
    state.activeQueueFilter = 'today';
  }

  // Update active class on buttons
  document.querySelectorAll('.queue-nav-btn').forEach(btn => {
    const isActive = btn.dataset.filter === state.activeQueueFilter;
    btn.classList.toggle('active', isActive);
    btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
  });
}

function renderHeroCard(queue, specificLead = null) {
  const el = document.getElementById('hero-card');

  // Use specific lead if clicked by user, otherwise find top lead
  let lead = specificLead;
  if (!lead) {
    for (const group of queue.groups) {
      if (group.leads.length) { lead = group.leads[0]; break; }
    }
  }
  state.currentHeroLeadId = lead ? lead.id : null;

  if (!lead) {
    el.innerHTML = `
      <div class="hero-empty">
        <span style="font-size:2.5rem">🎉</span><br/>
        ${t('hero_empty')}
      </div>`;
    return;
  }

  const cClass = chaleurClass(lead.chaleur);
  const chipsHtml = renderChips(lead.reasons);
  const channel = lead.suggested_channel === 'email'
    ? t('email_channel')
    : t('call_channel');

  const statusLabel = I18N[state.lang]?.statuses[lead.status] || lead.status;

  el.innerHTML = `
    <div class="hero-label">${t('hero_title')}</div>
    <div class="hero-name notranslate" translate="no">${lead.first_name || ''} ${lead.last_name || ''}</div>
    <div class="hero-meta">
      <span class="chaleur-badge ${cClass}">🔥 ${t('heat')} ${lead.chaleur}/10</span>
      <span class="chip">${statusLabel}</span>
      <span class="chip">${channel}</span>
    </div>
    <div class="hero-email">✉️ ${lead.email}</div>
    ${lead.last_contact_date ? `<div class="hero-email">${t('last_contact')} ${formatDate(lead.last_contact_date)}</div>` : ''}
    ${lead.funding_status !== 'unknown' ? `<div class="hero-email">${t('funding_label')} ${lead.funding_status.toUpperCase()}</div>` : ''}
    <div class="hero-chips">${chipsHtml}</div>
    <div class="outcome-buttons">
      ${OUTCOMES_CONFIG.map(o => {
        const label = I18N[state.lang]?.outcomes[o.code] || o.code;
        return `<button class="btn-outcome ${o.cls}" data-outcome="${o.code}" data-lead-id="${lead.id}">${label}</button>`;
      }).join('')}
    </div>
  `;

  // Bind outcome buttons
  el.querySelectorAll('.btn-outcome').forEach(btn => {
    btn.addEventListener('click', () => openLogModal(lead, btn.dataset.outcome));
  });
}

function renderQueueList(queue) {
  const el = document.getElementById('queue-list');
  const titleEl = document.getElementById('queue-active-title');
  const descEl = document.getElementById('queue-active-desc');
  const countEl = document.getElementById('queue-showing-count');

  if (!queue || !queue.groups) {
    if (el) el.innerHTML = '';
    return;
  }

  // 1. Filter leads by selected sidebar tab
  let currentGroupLeads = [];
  let title = '';
  let desc = '';

  if (state.activeQueueFilter === 'overdue') {
    currentGroupLeads = queue.groups.find(g => g.group === 'overdue')?.leads || [];
    title = t('panel_title_overdue');
    desc = t('panel_desc_overdue');
  } else if (state.activeQueueFilter === 'today') {
    currentGroupLeads = queue.groups.find(g => g.group === 'today')?.leads || [];
    title = t('panel_title_today');
    desc = t('panel_desc_today');
  } else if (state.activeQueueFilter === 'upcoming') {
    currentGroupLeads = queue.groups.find(g => g.group === 'upcoming')?.leads || [];
    title = t('panel_title_upcoming');
    desc = t('panel_desc_upcoming');
  } else {
    // 'all'
    currentGroupLeads = queue.groups.flatMap(g => g.leads);
    title = t('panel_title_all');
    desc = t('panel_desc_all');
  }

  // 2. Filter by search query if user typed something in queue search
  let displayLeads = currentGroupLeads;
  if (state.queueSearchQuery) {
    const q = state.queueSearchQuery.toLowerCase();
    displayLeads = currentGroupLeads.filter(l =>
      (l.first_name && l.first_name.toLowerCase().includes(q)) ||
      (l.last_name && l.last_name.toLowerCase().includes(q)) ||
      (l.email && l.email.toLowerCase().includes(q))
    );
  }

  // 3. Update titles and counts in UI header
  if (titleEl) titleEl.textContent = title;
  if (descEl) descEl.textContent = desc;
  if (countEl) countEl.textContent = t('lead_count', displayLeads.length);

  // 4. Render empty state if no leads
  if (!displayLeads.length) {
    let emptyMsg = t('empty_cat');
    if (state.activeQueueFilter === 'overdue') {
      emptyMsg = t('empty_overdue');
    } else if (state.activeQueueFilter === 'today') {
      emptyMsg = t('empty_today');
    } else if (state.activeQueueFilter === 'upcoming') {
      emptyMsg = t('empty_upcoming');
    } else if (state.queueSearchQuery) {
      emptyMsg = t('empty_search', state.queueSearchQuery);
    }

    el.innerHTML = `
      <div class="empty-state" style="padding: 2rem 1rem;">
        <span class="emoji">✨</span>
        <p>${emptyMsg}</p>
      </div>`;
    return;
  }

  // 5. Render lead rows
  el.innerHTML = displayLeads.map((lead, i) =>
    renderLeadRow(lead, i, queue.daily_capacity, lead.id === state.currentHeroLeadId)
  ).join('');

  // 6. Bind click events on rows to preview/focus on Hero Card
  el.querySelectorAll('.lead-row').forEach(row => {
    row.addEventListener('click', (e) => {
      if (e.target.closest('.btn-log-row')) return;
      const leadId = parseInt(row.dataset.leadId);
      const lead = findLeadInQueue(queue, leadId);
      if (lead) {
        el.querySelectorAll('.lead-row').forEach(r => r.classList.remove('selected-lead'));
        row.classList.add('selected-lead');
        renderHeroCard(queue, lead);
        if (window.innerWidth <= 860) {
          document.getElementById('hero-section').scrollIntoView({ behavior: 'smooth' });
        }
      }
    });
  });

  // 7. Bind Contacter button to open modal
  el.querySelectorAll('.btn-log-row').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const leadId = parseInt(btn.dataset.leadId);
      const lead = findLeadInQueue(queue, leadId);
      if (lead) openLogModal(lead, 'no_answer');
    });
  });
}

function findLeadInQueue(queue, leadId) {
  for (const g of queue.groups) {
    const found = g.leads.find(l => l.id === leadId);
    if (found) return found;
  }
  return null;
}

function renderLeadRow(lead, index, capacity, isSelected = false) {
  const pClass = priorityClass(lead.priority);
  const pLabel = priorityLabel(lead.priority);
  const chipsHtml = renderChips(lead.reasons.slice(0, 3));
  const marker = index === capacity ? 'capacity-marker' : '';
  const selectedClass = isSelected ? 'selected-lead' : '';

  return `
    <div class="lead-row ${marker} ${selectedClass}" data-lead-id="${lead.id}" title="Priorité : ${lead.priority}">
      <div class="priority-badge ${pClass}" title="${pLabel}">${pLabel}</div>
      <div class="lead-name notranslate" translate="no">${lead.first_name || ''} ${lead.last_name || ''}</div>
      <div class="lead-chips">${chipsHtml}</div>
      <div class="lead-actions">
        <button class="btn-log-row" data-lead-id="${lead.id}" aria-label="Action lead">
          ${t('btn_contact')}
        </button>
      </div>
    </div>`;
}


// LOG CONTACT MODAL

let _modalLead = null;
let _modalOutcome = null;

function openLogModal(lead, defaultOutcome) {
  _modalLead = lead;
  _modalOutcome = defaultOutcome;

  const container = document.getElementById('log-form-container');
  container.innerHTML = renderLogForm(lead, defaultOutcome);

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
      <label for="modal-outcome">${t('modal_outcome_lbl')}</label>
      <select id="modal-outcome" class="form-control">
        ${OUTCOMES_CONFIG.map(o => {
          const lbl = I18N[state.lang]?.outcomes[o.code] || o.code;
          return `<option value="${o.code}" ${o.code === defaultOutcome ? 'selected' : ''}>${lbl}</option>`;
        }).join('')}
      </select>
    </div>
    <div id="extra-fields"></div>
    <div class="form-group">
      <label for="modal-note">${t('modal_note_lbl')}</label>
      <textarea id="modal-note" class="form-control" rows="2" placeholder="${t('modal_note_ph')}"></textarea>
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
        <label for="modal-callback-at">${t('modal_callback_lbl')} <span style="color:red">*</span></label>
        <input type="datetime-local" id="modal-callback-at" class="form-control" value="${iso}T09:00" required />
      </div>`;
  } else if (outcome === 'not_interested') {
    html = `
      <div class="form-group">
        <label for="modal-lost-reason">${t('modal_lost_lbl')} <span style="color:red">*</span></label>
        <input type="text" id="modal-lost-reason" class="form-control" placeholder="${t('modal_lost_ph')}" required />
      </div>`;
  } else if (outcome === 'needs_funding_info') {
    html = `
      <div class="form-group">
        <label for="modal-funding">${t('modal_funding_lbl')}</label>
        <select id="modal-funding" class="form-control">
          <option value="">${t('modal_funding_unknown')}</option>
          <option value="cpf">CPF</option>
          <option value="opco">OPCO</option>
          <option value="france_travail">France Travail</option>
          <option value="self">${t('modal_funding_self')}</option>
          <option value="employer">${t('modal_funding_employer')}</option>
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
  btn.textContent = t('modal_saving');

  const body = {
    outcome: _modalOutcome,
    note: document.getElementById('modal-note')?.value || '',
  };

  const callbackEl = document.getElementById('modal-callback-at');
  if (callbackEl) {
    if (_modalOutcome === 'callback_requested' && !callbackEl.value) {
      callbackEl.focus();
      showToast(state.lang === 'en' ? '⚠️ Please select a callback date and time.' : '⚠️ Veuillez choisir la date et l\'heure du rappel.');
      btn.disabled = false;
      btn.textContent = t('modal_submit');
      return;
    }
    body.callback_at = callbackEl.value;
  }
  const lostEl = document.getElementById('modal-lost-reason');
  if (lostEl) {
    if (_modalOutcome === 'not_interested' && !lostEl.value.trim()) {
      lostEl.focus();
      showToast(state.lang === 'en' ? '⚠️ Please specify a reason for loss.' : '⚠️ Veuillez indiquer la raison de la perte.');
      btn.disabled = false;
      btn.textContent = t('modal_submit');
      return;
    }
    body.lost_reason = lostEl.value.trim();
  }
  const fundingEl = document.getElementById('modal-funding');
  if (fundingEl && fundingEl.value) {
    body.funding_status = fundingEl.value;
  }

  try {
    const resp = await API.post(`/api/leads/${_modalLead.id}/log-contact`, body);
    closeLogModal();
    const nextDate = resp.lead?.next_followup_date;
    const baseToast = state.lang === 'en'
      ? (nextDate ? `Next follow-up: ${formatDate(nextDate)}` : 'Lead closed.')
      : resp.toast;

    if (resp.next_lead) {
      const nextName = `${resp.next_lead.first_name || ''} ${resp.next_lead.last_name || ''}`.trim();
      const prefix = state.lang === 'en' ? 'Next' : 'Prochain';
      showToast(`${baseToast} · ${prefix} : ${nextName}`);
    } else {
      showToast(baseToast);
    }
    await refreshTodayView();
  } catch (e) {
    showToast(`⚠️ Error : ${e.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = t('modal_submit');
  }
}


// KANBAN VIEW

let _dragLeadId = null;
let _dragLeadStatus = null;
let _kanbanRep = '';
let _kanbanSearch = '';

async function refreshKanban() {
  const el = document.getElementById('kanban-board');
  el.innerHTML = `<div class="loading">${t('rep_loading')}</div>`;
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
  KANBAN_STATUSES.forEach(status => { grouped[status] = []; });
  leads.forEach(l => { if (grouped[l.status]) grouped[l.status].push(l); });

  KANBAN_STATUSES.forEach(status => {
    const colLeads = grouped[status] || [];
    const colLabel = I18N[state.lang]?.statuses[status] || status;
    const colEl = document.createElement('div');
    colEl.className = 'kanban-col';
    colEl.dataset.status = status;
    colEl.innerHTML = `
      <div class="kanban-col-header">
        ${colLabel}
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
        <div class="k-name notranslate" translate="no">
          <span class="priority-badge ${pClass}" style="display:inline-flex;width:1.5rem;height:1.5rem;font-size:.7rem">
            ${priorityLabel(lead.priority || 0)}
          </span>
          ${lead.first_name || ''} ${lead.last_name || ''}
        </div>
        <div class="k-meta">
          <span class="chaleur-badge ${chaleurClass(lead.chaleur)}" style="font-size:.72rem;padding:.1rem .4rem">🔥${lead.chaleur}</span>
          <span class="notranslate" translate="no">${lead.rep}</span> · ${t('call_count_label', lead.call_count)}
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
      if (!_dragLeadId || status === _dragLeadStatus) return;

      try {
        if (status === 'lost') {
          const reason = prompt(t('prompt_lost_reason'));
          if (!reason) return;
          await API.patch(`/api/leads/${_dragLeadId}`, { status, lost_reason: reason });
        } else {
          await API.patch(`/api/leads/${_dragLeadId}`, { status });
        }
        showToast(t('toast_moved', colLabel));
        await refreshKanban();
      } catch (err) {
        showToast(`⚠️ ${err.message}`);
      }
    });

    board.appendChild(colEl);
  });

  if (!leads.length) {
    board.innerHTML = `<div class="empty-state"><span class="emoji">✨</span>${t('kanban_empty')}</div>`;
  }
}


// TEAM VIEW

async function refreshTeamView() {
  const el = document.getElementById('team-grid');
  el.innerHTML = `<div class="loading">${t('rep_loading')}</div>`;
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
  const minLeads = Math.min(...reps.map(r => r.open_leads));
  const maxLeads = Math.max(...reps.map(r => r.open_leads));
  insight.textContent = t('team_insight', statsAll.forgotten_hot, minLeads, maxLeads);

  const grid = document.getElementById('team-grid');
  grid.innerHTML = reps.map(r => `
    <div class="team-card">
      <div class="rep-name notranslate" translate="no">👤 ${r.rep}</div>
      <div class="team-stat-row">
        <span class="label">${t('team_open_leads')}</span>
        <span class="val">${r.open_leads}</span>
      </div>
      <div class="team-stat-row">
        <span class="label">${t('team_overdue')}</span>
        <span class="val ${r.overdue > 0 ? 'danger' : ''}">${r.overdue}</span>
      </div>
      <div class="team-stat-row">
        <span class="label">${t('team_forgotten_hot')}</span>
        <span class="val ${r.forgotten_hot > 0 ? 'warn' : ''}">${r.forgotten_hot}</span>
      </div>
      <div class="team-stat-row">
        <span class="label">${t('team_fatigued')}</span>
        <span class="val ${r.fatigued > 0 ? 'warn' : ''}">${r.fatigued}</span>
      </div>
      <div class="team-stat-row">
        <span class="label">${t('team_today')}</span>
        <span class="val">${r.due_today}</span>
      </div>
    </div>
  `).join('');
}


// TAB NAVIGATION

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


// MODAL & FORM EVENTS

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


// KANBAN FILTER EVENTS

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


// QUEUE SIDEBAR & SEARCH EVENTS

function setupQueueEvents() {
  // Sidebar category buttons
  document.querySelectorAll('.queue-nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      state.activeQueueFilter = btn.dataset.filter;
      document.querySelectorAll('.queue-nav-btn').forEach(b => {
        const isSelected = b === btn;
        b.classList.toggle('active', isSelected);
        b.setAttribute('aria-selected', isSelected ? 'true' : 'false');
      });
      if (state.queueData) {
        renderQueueList(state.queueData);
      }
    });
  });

  // Search filter inside queue
  const queueSearchInput = document.getElementById('queue-search');
  if (queueSearchInput) {
    queueSearchInput.addEventListener('input', (e) => {
      state.queueSearchQuery = e.target.value.trim();
      if (state.queueData) {
        renderQueueList(state.queueData);
      }
    });
  }
}


// INIT

async function init() {
  setupTabs();
  setupQueueEvents();
  setupModalEvents();
  setupKanbanFilters();

  // Language buttons
  document.getElementById('btn-lang-fr')?.addEventListener('click', () => setLanguage('fr'));
  document.getElementById('btn-lang-en')?.addEventListener('click', () => setLanguage('en'));

  // Initialize language active button
  document.getElementById('btn-lang-fr')?.classList.toggle('active', state.lang === 'fr');
  document.getElementById('btn-lang-en')?.classList.toggle('active', state.lang === 'en');
  updateStaticLabels();

  document.getElementById('rep-select').addEventListener('change', onRepChange);

  try {
    await loadReps();
    await refreshTodayView();
  } catch (e) {
    document.getElementById('hero-card').innerHTML =
      `<div class="empty-state"><span class="emoji">⚠️</span>${e.message}</div>`;
  }
}

init();