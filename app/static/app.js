/**
 * DevTrack AI — Project Management SPA
 * Production-ready vanilla JS with async/await API integration
 */

/* ── Configuration ─────────────────────────────────────── */
const API = '/api/v1';
const PAGE_SIZE = 12;

/* ── State ─────────────────────────────────────────────── */
const state = {
  token: localStorage.getItem('dt_token'),
  user: JSON.parse(localStorage.getItem('dt_user') || 'null'),
  orgId: localStorage.getItem('dt_org_id') || null,
  currentProject: null,
  projects: [],
  templates: [],
  page: 1,
  total: 0,
  pages: 0,
  query: '',
  filterType: '',
  activeView: 'projects',
  selectedTemplate: 'KANBAN',
  // Kanban board state
  boardProjectId: null,
  boards: [],
  activeBoard: null,
  boardIssues: [],
  boardMembers: [],
  boardQuery: '',
  boardPriorityFilter: '',
  boardAssigneeFilter: '',
  boardLabelFilter: '',
  draggedIssueId: null,
  editingIssue: null,
};

/* ── Helpers ────────────────────────────────────────────── */
const qs = (sel, ctx = document) => ctx.querySelector(sel);
const qsa = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

function toast(msg, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  qs('#toast-container').appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

function debounce(fn, ms = 350) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

async function apiFetch(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (state.token) headers['Authorization'] = `Bearer ${state.token}`;
  const res = await fetch(`${API}${path}`, { ...opts, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

/* ── Template Meta ──────────────────────────────────────── */
const TEMPLATE_META = {
  KANBAN:       { icon: '◈', cls: 'badge-kanban',  label: 'Kanban'  },
  SCRUM:        { icon: '⊞', cls: 'badge-scrum',   label: 'Scrum'   },
  BUG_TRACKING: { icon: '⊗', cls: 'badge-bug',     label: 'Bugs'    },
  ROADMAP:      { icon: '◎', cls: 'badge-roadmap', label: 'Roadmap' },
  CUSTOM:       { icon: '⋯', cls: 'badge-custom',  label: 'Custom'  },
};

const TEMPLATE_COLORS = {
  KANBAN:       ['hsl(214,90%,64%)', 'hsl(214,70%,30%)'],
  SCRUM:        ['hsl(261,80%,68%)', 'hsl(261,60%,28%)'],
  BUG_TRACKING: ['hsl(0,80%,62%)',   'hsl(0,60%,26%)'],
  ROADMAP:      ['hsl(152,76%,55%)', 'hsl(152,56%,22%)'],
  CUSTOM:       ['hsl(38,95%,60%)',  'hsl(38,75%,24%)'],
};

/* ── Auth & Bootstrap ───────────────────────────────────── */
async function bootstrap() {
  if (!state.token) {
    await quickLogin();
  }
  renderUserSidebar();
  await loadOrganizations();
  await loadTemplates();
  if (state.orgId) {
    await fetchProjects();
  }
}

async function quickLogin() {
  /* In a full app, this redirects to a login page.
     For demo purposes we try to register+login a demo user. */
  const email = 'demo@devtrack.ai';
  const password = 'DemoPass123!';
  try {
    await fetch(`${API}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, full_name: 'Demo User' }),
    });
  } catch (_) { /* ignore if exists */ }

  const loginRes = await fetch(`${API}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!loginRes.ok) {
    toast('Please log in via /docs first.', 'error');
    return;
  }
  const data = await loginRes.json();
  state.token = data.access_token;
  state.user = data.user;
  localStorage.setItem('dt_token', state.token);
  localStorage.setItem('dt_user', JSON.stringify(state.user));
}

function renderUserSidebar() {
  if (!state.user) return;
  const name = state.user.full_name || state.user.email || 'User';
  qs('#user-name-sidebar').textContent = name;
  qs('#user-avatar-sidebar').textContent = name[0].toUpperCase();
}

async function loadOrganizations() {
  try {
    const orgs = await apiFetch('/organizations');
    const sel = qs('#org-select');
    sel.innerHTML = '<option value="">Select Organization…</option>';
    if (orgs && orgs.length) {
      orgs.forEach(org => {
        const opt = document.createElement('option');
        opt.value = org.id;
        opt.textContent = org.name;
        if (org.id === state.orgId) opt.selected = true;
        sel.appendChild(opt);
      });
      if (!state.orgId) {
        state.orgId = orgs[0].id;
        sel.value = state.orgId;
        localStorage.setItem('dt_org_id', state.orgId);
      }
      qs('#btn-new-project').disabled = false;
    }
  } catch (e) {
    console.warn('loadOrganizations:', e.message);
  }
}

async function createDefaultOrg() {
  try {
    const org = await apiFetch('/organizations', {
      method: 'POST',
      body: JSON.stringify({ name: 'My Organization' }),
    });
    state.orgId = org.id;
    localStorage.setItem('dt_org_id', org.id);
    await loadOrganizations();
  } catch (e) {
    toast(`Failed to create org: ${e.message}`, 'error');
  }
}

/* ── Projects ───────────────────────────────────────────── */
async function fetchProjects(archived = false) {
  if (!state.orgId) return;
  const params = new URLSearchParams({
    page: state.page,
    size: PAGE_SIZE,
    include_archived: archived ? 'true' : 'false',
  });
  if (state.query) params.set('q', state.query);
  if (state.filterType) params.set('template_type', state.filterType);

  try {
    const data = await apiFetch(`/organizations/${state.orgId}/projects?${params}`);
    state.projects = data.items;
    state.total = data.total;
    state.pages = data.pages;
    renderProjectGrid(archived);
    renderStats();
    renderPagination(archived);
    populateAnalyticsSelect();
  } catch (e) {
    toast(`Error loading projects: ${e.message}`, 'error');
  }
}

function renderProjectGrid(archived = false) {
  const gridId = archived ? 'archived-grid' : 'project-grid';
  const grid = qs(`#${gridId}`);
  if (!state.projects.length) {
    grid.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">${archived ? '⊛' : '◈'}</div>
        <h3>${archived ? 'No archived projects' : 'No projects yet'}</h3>
        <p>${archived ? 'Projects you archive will appear here.' : 'Create your first project using the button above.'}</p>
      </div>`;
    return;
  }

  grid.innerHTML = state.projects.map(p => projectCardHTML(p)).join('');

  qsa('.project-card', grid).forEach(card => {
    card.addEventListener('click', (e) => {
      if (e.target.closest('.project-card-actions')) return;
      openDrawer(card.dataset.id);
    });
  });

  qsa('.btn-archive-card', grid).forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const id = btn.dataset.id;
      await archiveProject(id);
    });
  });
}

function projectCardHTML(p) {
  const meta = TEMPLATE_META[p.template_type] || TEMPLATE_META.CUSTOM;
  const colors = TEMPLATE_COLORS[p.template_type] || TEMPLATE_COLORS.CUSTOM;
  const archivedBadge = p.is_archived
    ? '<span class="template-badge" style="background:hsla(38,95%,60%,0.15);color:hsl(38,95%,60%)">Archived</span>'
    : `<span class="template-badge ${meta.cls}">${meta.label}</span>`;

  return `
    <div class="project-card" data-id="${p.id}" id="pcard-${p.id}" tabindex="0" role="button" aria-label="Open project ${p.name}">
      <div class="project-card-header">
        <div class="project-icon" style="background:linear-gradient(135deg,${colors[0]},${colors[1]})">
          ${meta.icon}
        </div>
        <div class="project-card-actions">
          <button class="btn-icon btn-archive-card" data-id="${p.id}" title="${p.is_archived ? 'Restore' : 'Archive'}" aria-label="Archive ${p.name}">
            ${p.is_archived ? '↩' : '⊛'}
          </button>
        </div>
      </div>
      <div class="project-key" style="margin-bottom:0.3rem">${p.key}</div>
      <div class="project-name">${escHtml(p.name)}</div>
      <div class="project-desc">${escHtml(p.description || 'No description provided.')}</div>
      <div class="project-footer">
        ${archivedBadge}
        <div class="member-avatars" id="mavs-${p.id}"></div>
      </div>
    </div>`;
}

function escHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

function renderStats() {
  qs('#stat-total').textContent = state.total;
  qs('#stat-active').textContent = state.projects.filter(p => !p.is_archived).length;
  qs('#stat-members').textContent = '—';
  qs('#stat-health').textContent = '—%';
}

function renderPagination(archived) {
  if (state.pages <= 1) {
    qs('#pagination').style.display = 'none';
    return;
  }
  qs('#pagination').style.display = 'flex';
  qs('#pagination-info').textContent = `Page ${state.page} of ${state.pages} — ${state.total} projects`;
  qs('#btn-prev').disabled = state.page <= 1;
  qs('#btn-next').disabled = state.page >= state.pages;
}

/* ── Templates ──────────────────────────────────────────── */
async function loadTemplates() {
  try {
    const tpls = await apiFetch('/projects/templates');

    state.templates = tpls;
    renderTemplatesGrid();
    renderModalTemplateSelector();
  } catch (e) {
    console.warn('loadTemplates:', e.message);
  }
}

function renderTemplatesGrid() {
  const grid = qs('#templates-grid');
  if (!state.templates.length) return;
  grid.innerHTML = state.templates.map(t => {
    const meta = TEMPLATE_META[t.template_type] || TEMPLATE_META.CUSTOM;
    const colors = TEMPLATE_COLORS[t.template_type] || TEMPLATE_COLORS.CUSTOM;
    return `
      <div class="template-card" tabindex="0" data-type="${t.template_type}">
        <div class="template-card-icon" style="background:linear-gradient(135deg,${colors[0]},${colors[1]});color:#fff">
          ${meta.icon}
        </div>
        <div class="template-card-name">${escHtml(t.name)}</div>
        <div class="template-card-desc">${escHtml(t.description)}</div>
        <div class="columns-preview">
          ${t.default_columns.map(c => `<span class="col-chip">${escHtml(c)}</span>`).join('')}
        </div>
        <button class="use-template-btn" data-type="${t.template_type}">Use Template →</button>
      </div>`;
  }).join('');

  qsa('.use-template-btn', grid).forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      if (!state.orgId) { toast('Select an organization first.', 'error'); return; }
      openCreateModal(btn.dataset.type);
    });
  });
}

function renderModalTemplateSelector() {
  const container = qs('#modal-template-selector');
  if (!state.templates.length) return;
  container.innerHTML = state.templates.map(t => {
    const meta = TEMPLATE_META[t.template_type] || TEMPLATE_META.CUSTOM;
    return `
      <button class="tmpl-opt${t.template_type === state.selectedTemplate ? ' selected' : ''}"
              data-type="${t.template_type}" type="button" aria-pressed="${t.template_type === state.selectedTemplate}">
        <span class="tmpl-opt-icon">${meta.icon}</span>
        <span class="tmpl-opt-name">${meta.label}</span>
        <span class="tmpl-opt-type">${t.template_type}</span>
      </button>`;
  }).join('');

  qsa('.tmpl-opt', container).forEach(btn => {
    btn.addEventListener('click', () => {
      state.selectedTemplate = btn.dataset.type;
      qsa('.tmpl-opt', container).forEach(b => {
        b.classList.toggle('selected', b.dataset.type === state.selectedTemplate);
        b.setAttribute('aria-pressed', b.dataset.type === state.selectedTemplate);
      });
    });
  });
}

/* ── Create Project ─────────────────────────────────────── */
function openCreateModal(preselect = null) {
  if (preselect) {
    state.selectedTemplate = preselect;
    renderModalTemplateSelector();
  }
  qs('#create-modal-overlay').classList.add('active');
  qs('#proj-name').focus();
}

function closeCreateModal() {
  qs('#create-modal-overlay').classList.remove('active');
  qs('#create-project-form').reset();
}

async function handleCreateProject(e) {
  e.preventDefault();
  if (!state.orgId) { toast('Select an organization first.', 'error'); return; }

  const name = qs('#proj-name').value.trim();
  const key = qs('#proj-key').value.trim() || undefined;
  const description = qs('#proj-desc').value.trim() || undefined;

  if (!name) { toast('Project name is required.', 'error'); return; }

  const btn = qs('#btn-submit-project');
  btn.disabled = true;
  btn.textContent = 'Creating…';

  try {
    await apiFetch(`/organizations/${state.orgId}/projects`, {
      method: 'POST',
      body: JSON.stringify({ name, key, description, template_type: state.selectedTemplate }),
    });
    toast('Project created successfully!', 'success');
    closeCreateModal();
    state.page = 1;
    await fetchProjects();
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Create Project';
  }
}

/* ── Archive / Restore ──────────────────────────────────── */
async function archiveProject(projectId) {
  try {
    await apiFetch(`/organizations/${state.orgId}/projects/${projectId}/archive`, { method: 'POST' });
    toast('Project archived.', 'info');
    await fetchProjects();
  } catch (e) {
    toast(`Archive failed: ${e.message}`, 'error');
  }
}

async function restoreProject(projectId) {
  try {
    await apiFetch(`/organizations/${state.orgId}/projects/${projectId}/restore`, { method: 'POST' });
    toast('Project restored.', 'success');
    if (state.activeView === 'archived') {
      await fetchProjects(true);
    } else {
      await fetchProjects();
    }
    closeDrawer();
  } catch (e) {
    toast(`Restore failed: ${e.message}`, 'error');
  }
}

async function deleteProject(projectId) {
  if (!confirm('Permanently delete this project? This cannot be undone.')) return;
  try {
    await apiFetch(`/organizations/${state.orgId}/projects/${projectId}`, { method: 'DELETE' });
    toast('Project deleted.', 'info');
    closeDrawer();
    await fetchProjects();
  } catch (e) {
    toast(`Delete failed: ${e.message}`, 'error');
  }
}

/* ── Project Drawer ─────────────────────────────────────── */
async function openDrawer(projectId) {
  state.currentProject = null;
  try {
    const project = await apiFetch(`/organizations/${state.orgId}/projects/${projectId}`);
    state.currentProject = project;

    qs('#drawer-key').textContent = project.key;
    qs('#drawer-title').textContent = project.name;
    qs('#drawer-description').textContent = project.description || '';

    // Settings form pre-fill
    qs('#settings-name').value = project.name;
    qs('#settings-desc').value = project.description || '';

    // Archive / restore button
    const archBtn = qs('#btn-archive-project');
    if (project.is_archived) {
      archBtn.textContent = 'Restore Project';
      archBtn.className = 'btn btn-primary';
      archBtn.onclick = () => restoreProject(project.id);
    } else {
      archBtn.textContent = 'Archive Project';
      archBtn.className = 'btn btn-danger';
      archBtn.onclick = () => {
        closeDrawer();
        archiveProject(project.id);
      };
    }

    qs('#btn-delete-project').onclick = () => deleteProject(project.id);

    // Activate dashboard tab
    activateDrawerTab('dashboard');
    loadDashboard(projectId);

    qs('#drawer-overlay').classList.add('active');
    qs('#project-drawer').classList.add('active');
  } catch (e) {
    toast(`Could not open project: ${e.message}`, 'error');
  }
}

function closeDrawer() {
  qs('#drawer-overlay').classList.remove('active');
  qs('#project-drawer').classList.remove('active');
  state.currentProject = null;
}

function activateDrawerTab(tabName) {
  qsa('.drawer-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tabName));
  qsa('.drawer-tab-content').forEach(c => c.classList.remove('active'));
  qs(`#tab-${tabName}`).classList.add('active');
}

async function loadDashboard(projectId) {
  qs('#dashboard-metrics').innerHTML = `<div class="skeleton-loader" style="height:80px;grid-column:1/-1"></div>`;
  qs('#workflow-columns').innerHTML = '';
  try {
    const data = await apiFetch(`/organizations/${state.orgId}/projects/${projectId}/dashboard`);
    renderDashboard(data);
    // Update stats panel with real numbers
    qs('#stat-health').textContent = `${data.health_score}%`;
  } catch (e) {
    qs('#dashboard-metrics').innerHTML = `<p style="color:var(--accent-red);font-size:.85rem">Failed to load dashboard.</p>`;
  }
}

function renderDashboard(data) {
  qs('#dashboard-metrics').innerHTML = `
    <div class="metric-card">
      <div class="num">${data.open_issues_count}</div>
      <div class="lbl">Open Issues</div>
    </div>
    <div class="metric-card">
      <div class="num">${data.completed_issues_count}</div>
      <div class="lbl">Completed</div>
    </div>
    <div class="metric-card">
      <div class="num">${data.health_score}%</div>
      <div class="lbl">Health Score</div>
    </div>
    <div class="metric-card">
      <div class="num">${Math.round(data.completion_percentage)}%</div>
      <div class="lbl">Completion</div>
    </div>
  `;
  qs('#workflow-columns').innerHTML = data.workflow_columns
    .map(c => `<span class="wf-col">${escHtml(c)}</span>`)
    .join('');
}

async function loadMembers(projectId) {
  const list = qs('#members-list');
  list.innerHTML = `<div class="skeleton-loader" style="height:60px"></div><div class="skeleton-loader" style="height:60px;margin-top:8px"></div>`;
  try {
    const members = await apiFetch(`/organizations/${state.orgId}/projects/${projectId}/members`);
    qs('#stat-members').textContent = members.length;
    if (!members.length) {
      list.innerHTML = `<p style="color:var(--text-muted);font-size:.85rem;text-align:center;padding:1rem">No members yet.</p>`;
      return;
    }
    list.innerHTML = members.map(m => `
      <div class="member-row">
        <div class="member-row-avatar">${(m.user.full_name || m.user.email || 'U')[0].toUpperCase()}</div>
        <div class="member-row-info">
          <div class="member-row-name">${escHtml(m.user.full_name || m.user.email)}</div>
          <div class="member-row-email">${escHtml(m.user.email)}</div>
        </div>
        <span class="role-pill role-${m.role}">${m.role}</span>
      </div>`).join('');
    // Also render mini avatars on the card
    renderMemberAvatars(projectId, members);
  } catch (e) {
    list.innerHTML = `<p style="color:var(--accent-red);font-size:.85rem">Failed to load members.</p>`;
  }
}

function renderMemberAvatars(projectId, members) {
  const el = qs(`#mavs-${projectId}`);
  if (!el) return;
  const shown = members.slice(0, 4);
  el.innerHTML = shown.map(m =>
    `<div class="member-chip" title="${escHtml(m.user.full_name || m.user.email)}">${(m.user.full_name || m.user.email || 'U')[0].toUpperCase()}</div>`
  ).join('');
  if (members.length > 4) {
    el.innerHTML += `<div class="member-chip">+${members.length - 4}</div>`;
  }
}

/* ── Analytics ──────────────────────────────────────────── */
function populateAnalyticsSelect() {
  const sel = qs('#analytics-project-select');
  sel.innerHTML = '<option value="">Choose a project…</option>';
  state.projects.forEach(p => {
    const opt = document.createElement('option');
    opt.value = p.id;
    opt.textContent = p.name;
    sel.appendChild(opt);
  });
}

async function loadAnalytics(projectId) {
  qs('#analytics-select-prompt').style.display = 'none';
  qs('#analytics-content').style.display = 'block';
  qs('#velocity-chart').innerHTML = '<div class="skeleton-loader" style="height:100%;min-height:90px"></div>';
  qs('#workload-bars').innerHTML = '';
  qs('#donut-legend').innerHTML = '';
  qs('#created-vs-resolved').innerHTML = '';

  try {
    const data = await apiFetch(`/organizations/${state.orgId}/projects/${projectId}/analytics`);
    renderVelocityChart(data.velocity_trend);
    renderStatusDonut(data.issue_status_distribution);
    renderWorkloadBars(data.member_workload);
    renderCreatedVsResolved(data.created_vs_resolved);
  } catch (e) {
    toast(`Analytics error: ${e.message}`, 'error');
  }
}

function renderVelocityChart(trend) {
  const maxVal = Math.max(...trend.flatMap(s => [s.completed, s.committed]), 1);
  const chartEl = qs('#velocity-chart');
  chartEl.innerHTML = trend.map(s => {
    const compH = Math.round((s.completed / maxVal) * 80);
    const commH = Math.round((s.committed / maxVal) * 80);
    return `
      <div class="velocity-sprint">
        <div class="velocity-bars">
          <div class="bar bar-committed" style="height:${commH}px" title="Committed: ${s.committed}"></div>
          <div class="bar bar-completed" style="height:${compH}px" title="Completed: ${s.completed}"></div>
        </div>
        <div class="velocity-label">${escHtml(s.sprint)}</div>
      </div>`;
  }).join('');
}

const DONUT_COLORS = [
  'hsl(261,80%,68%)',
  'hsl(214,90%,64%)',
  'hsl(152,76%,55%)',
  'hsl(38,95%,60%)',
  'hsl(186,90%,56%)',
  'hsl(0,80%,62%)',
];

function renderStatusDonut(dist) {
  const canvas = qs('#status-donut');
  const ctx = canvas.getContext('2d');
  const entries = Object.entries(dist);
  const total = entries.reduce((s, [, v]) => s + v, 0) || 1;
  let start = -Math.PI / 2;
  const cx = 90, cy = 90, r = 70, innerR = 42;

  ctx.clearRect(0, 0, 180, 180);
  entries.forEach(([key, val], i) => {
    const angle = (val / total) * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, r, start, start + angle);
    ctx.closePath();
    ctx.fillStyle = DONUT_COLORS[i % DONUT_COLORS.length];
    ctx.fill();
    start += angle;
  });

  // Inner hole
  ctx.beginPath();
  ctx.arc(cx, cy, innerR, 0, Math.PI * 2);
  ctx.fillStyle = 'hsl(222,24%,11%)';
  ctx.fill();

  // Center text
  ctx.fillStyle = 'hsl(220,20%,95%)';
  ctx.font = 'bold 22px Inter, sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(total, cx, cy);

  // Legend
  const legend = qs('#donut-legend');
  legend.innerHTML = entries.map(([key, val], i) => `
    <div class="legend-item">
      <div class="legend-dot" style="background:${DONUT_COLORS[i % DONUT_COLORS.length]}"></div>
      <span>${escHtml(key)}: <strong>${val}</strong></span>
    </div>`).join('');
}

function renderWorkloadBars(workload) {
  const el = qs('#workload-bars');
  const max = Math.max(...workload.map(w => w.assigned_issues), 1);
  el.innerHTML = workload.map(w => `
    <div class="workload-bar-row">
      <span class="workload-name">${escHtml(w.user_name)}</span>
      <div class="workload-bar-track">
        <div class="workload-bar-fill" style="width:${Math.round((w.assigned_issues / max) * 100)}%"></div>
      </div>
      <span class="workload-count">${w.assigned_issues}</span>
    </div>`).join('');
}

function renderCreatedVsResolved(data) {
  qs('#created-vs-resolved').innerHTML = `
    <div class="metric-circle">
      <div class="num created-num">${data.created}</div>
      <div class="lbl">Created</div>
    </div>
    <div style="font-size:1.5rem;color:var(--text-muted)">vs</div>
    <div class="metric-circle">
      <div class="num resolved-num">${data.resolved}</div>
      <div class="lbl">Resolved</div>
    </div>`;
}

/* ── Kanban Board Module ──────────────────────────────────── */

function populateBoardProjectSelect() {
  const sel = qs('#board-project-select');
  if (!sel) return;
  sel.innerHTML = '<option value="">Select Project…</option>';
  state.projects.forEach(p => {
    const opt = document.createElement('option');
    opt.value = p.id;
    opt.textContent = `${p.key} - ${p.name}`;
    if (p.id === state.boardProjectId) opt.selected = true;
    sel.appendChild(opt);
  });
}

async function loadBoardView(projectId = null) {
  if (!state.orgId) return;
  if (!projectId) {
    if (state.projects.length && !state.boardProjectId) {
      state.boardProjectId = state.projects[0].id;
    }
  } else {
    state.boardProjectId = projectId;
  }

  populateBoardProjectSelect();
  const projSel = qs('#board-project-select');
  if (projSel) projSel.value = state.boardProjectId || '';

  const container = qs('#kanban-board-container');
  if (!state.boardProjectId) {
    if (container) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">📊</div>
          <h3>No project selected</h3>
          <p>Select a project from the dropdown above to load its Kanban board.</p>
        </div>`;
    }
    qs('#btn-create-issue').disabled = true;
    qs('#btn-add-column').disabled = true;
    return;
  }

  qs('#btn-create-issue').disabled = false;
  qs('#btn-add-column').disabled = false;

  loadBoardMembers(state.boardProjectId);
  if (typeof wsClient !== 'undefined') {
    wsClient.connect(state.boardProjectId);
  }

  try {
    const boards = await apiFetch(`/organizations/${state.orgId}/projects/${state.boardProjectId}/boards`);
    state.boards = boards || [];
    
    const boardSel = qs('#board-select');
    if (boardSel) {
      boardSel.innerHTML = state.boards.map(b => `<option value="${b.id}">${escHtml(b.name)}${b.is_default ? ' (Default)' : ''}</option>`).join('');
    }

    let targetBoardId = state.boards.length ? state.boards[0].id : null;
    if (targetBoardId) {
      await loadBoardDetails(targetBoardId);
    } else {
      const newBoard = await apiFetch(`/organizations/${state.orgId}/projects/${state.boardProjectId}/boards`, {
        method: 'POST',
        body: JSON.stringify({ name: 'Default Board', is_default: true }),
      });
      state.boards = [newBoard];
      await loadBoardDetails(newBoard.id);
    }
  } catch (e) {
    toast(`Failed to load board: ${e.message}`, 'error');
  }
}

async function loadBoardMembers(projectId) {
  try {
    const members = await apiFetch(`/organizations/${state.orgId}/projects/${projectId}/members`);
    state.boardMembers = members || [];
    populateAssigneeDropdowns();
  } catch (_) {
    state.boardMembers = [];
  }
}

function populateAssigneeDropdowns() {
  const filterSel = qs('#filter-board-assignee');
  const modalSel = qs('#issue-assignee');
  
  if (filterSel) {
    filterSel.innerHTML = '<option value="">All Assignees</option>' +
      state.boardMembers.map(m => `<option value="${m.user.id}">${escHtml(m.user.full_name || m.user.email)}</option>`).join('');
  }
  if (modalSel) {
    modalSel.innerHTML = '<option value="">Unassigned</option>' +
      state.boardMembers.map(m => `<option value="${m.user.id}">${escHtml(m.user.full_name || m.user.email)}</option>`).join('');
  }
}

async function loadBoardDetails(boardId) {
  try {
    const board = await apiFetch(`/organizations/${state.orgId}/projects/${state.boardProjectId}/boards/${boardId}`);
    state.activeBoard = board;

    if (!board.columns || !board.columns.length) {
      const defaultCols = [
        { name: 'To Do', mapped_status: 'TODO' },
        { name: 'In Progress', mapped_status: 'IN_PROGRESS' },
        { name: 'In Review', mapped_status: 'IN_REVIEW' },
        { name: 'Done', mapped_status: 'DONE' },
      ];
      for (const c of defaultCols) {
        try {
          await apiFetch(`/organizations/${state.orgId}/projects/${state.boardProjectId}/boards/${boardId}/columns`, {
            method: 'POST',
            body: JSON.stringify(c),
          });
        } catch (_) {}
      }
      state.activeBoard = await apiFetch(`/organizations/${state.orgId}/projects/${state.boardProjectId}/boards/${boardId}`);
    }

    await fetchBoardIssues();
  } catch (e) {
    toast(`Error loading board details: ${e.message}`, 'error');
  }
}

async function fetchBoardIssues() {
  if (!state.boardProjectId) return;
  const params = new URLSearchParams({ page: 1, size: 100 });
  if (state.boardQuery) params.set('q', state.boardQuery);
  if (state.boardPriorityFilter) params.set('priority', state.boardPriorityFilter);
  if (state.boardAssigneeFilter) params.set('assignee_id', state.boardAssigneeFilter);

  try {
    const data = await apiFetch(`/organizations/${state.orgId}/projects/${state.boardProjectId}/issues?${params}`);
    state.boardIssues = data.items || [];
    renderBoardUI();
  } catch (e) {
    toast(`Error loading issues: ${e.message}`, 'error');
  }
}

function renderBoardUI() {
  const container = qs('#kanban-board-container');
  if (!container || !state.activeBoard) return;

  const cols = state.activeBoard.columns || [];
  if (!cols.length) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📊</div>
        <h3>No columns in board</h3>
        <p>Click "+ Column" above to add your first column.</p>
      </div>`;
    return;
  }

  container.innerHTML = cols.map(col => {
    const colIssues = state.boardIssues.filter(i => i.status === col.mapped_status);
    return `
      <div class="kanban-column" data-col-id="${col.id}" data-status="${col.mapped_status}">
        <div class="kanban-column-header">
          <div class="column-title-group">
            <span class="column-title">${escHtml(col.name)}</span>
            <span class="column-count">${colIssues.length}</span>
          </div>
          <button class="btn-icon btn-add-col-issue" data-status="${col.mapped_status}" title="Add issue to ${escHtml(col.name)}">+</button>
        </div>
        <div class="kanban-cards-list" data-status="${col.mapped_status}">
          ${colIssues.map(issue => renderIssueCardHTML(issue)).join('')}
        </div>
      </div>`;
  }).join('');

  wireDragAndDropEvents();
}

function renderIssueCardHTML(issue) {
  const assigneeName = issue.assignee_id ? getAssigneeName(issue.assignee_id) : 'Unassigned';
  const initial = assigneeName !== 'Unassigned' ? assigneeName[0].toUpperCase() : '?';

  return `
    <div class="kanban-card" draggable="true" data-issue-id="${issue.id}" id="card-${issue.id}">
      <div class="card-header">
        <span class="card-key">${issue.identifier}</span>
        <span class="priority-pill priority-${issue.priority}">${issue.priority.replace('_', ' ')}</span>
      </div>
      <div class="card-title">${escHtml(issue.title)}</div>
      <div class="card-footer">
        <div class="member-chip" title="Assignee: ${escHtml(assigneeName)}">${initial}</div>
        <span style="font-size:0.72rem;color:var(--text-muted)">${new Date(issue.created_at).toLocaleDateString()}</span>
      </div>
    </div>`;
}

function getAssigneeName(userId) {
  const m = state.boardMembers.find(mem => mem.user.id === userId);
  return m ? (m.user.full_name || m.user.email) : 'Member';
}

function wireDragAndDropEvents() {
  const cards = qsa('.kanban-card');
  const cols = qsa('.kanban-column');

  cards.forEach(card => {
    card.addEventListener('dragstart', (e) => {
      state.draggedIssueId = card.dataset.issueId;
      card.classList.add('dragging');
      e.dataTransfer.setData('text/plain', card.dataset.issueId);
      e.dataTransfer.effectAllowed = 'move';
    });

    card.addEventListener('dragend', () => {
      card.classList.remove('dragging');
      state.draggedIssueId = null;
      cols.forEach(c => c.classList.remove('drag-over'));
    });

    card.addEventListener('click', (e) => {
      const issueId = card.dataset.issueId;
      const issue = state.boardIssues.find(i => i.id === issueId);
      if (issue) openIssueModal(issue);
    });
  });

  cols.forEach(col => {
    col.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      col.classList.add('drag-over');
    });

    col.addEventListener('dragleave', (e) => {
      if (!col.contains(e.relatedTarget)) {
        col.classList.remove('drag-over');
      }
    });

    col.addEventListener('drop', async (e) => {
      e.preventDefault();
      col.classList.remove('drag-over');
      const issueId = e.dataTransfer.getData('text/plain') || state.draggedIssueId;
      if (!issueId) return;

      const colId = col.dataset.colId;
      const targetStatus = col.dataset.status;

      const issueIndex = state.boardIssues.findIndex(i => i.id === issueId);
      if (issueIndex === -1) return;
      const originalStatus = state.boardIssues[issueIndex].status;

      if (originalStatus === targetStatus) return;

      // Optimistic local state update
      state.boardIssues[issueIndex].status = targetStatus;
      renderBoardUI();

      try {
        await apiFetch(`/organizations/${state.orgId}/projects/${state.boardProjectId}/boards/${state.activeBoard.id}/issues/${issueId}/move`, {
          method: 'POST',
          body: JSON.stringify({ column_id: colId }),
        });
        toast('Issue moved.', 'info');
      } catch (err) {
        // Rollback state on failure
        state.boardIssues[issueIndex].status = originalStatus;
        renderBoardUI();
        toast(`Move failed: ${err.message}`, 'error');
      }
    });
  });

  qsa('.btn-add-col-issue').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      openIssueModal(null, btn.dataset.status);
    });
  });
}

/* ── Issue Modal ─────────────────────────────────────────── */
function openIssueModal(issue = null, preselectStatus = 'TODO') {
  state.editingIssue = issue;
  const overlay = qs('#issue-modal-overlay');
  const title = qs('#issue-modal-title');
  const keyBadge = qs('#issue-modal-key');
  const form = qs('#issue-form');

  form.reset();
  populateAssigneeDropdowns();

  if (issue) {
    title.textContent = `Edit Issue ${issue.identifier}`;
    keyBadge.textContent = issue.identifier;
    qs('#issue-title').value = issue.title;
    qs('#issue-description').value = issue.description || '';
    qs('#issue-status').value = issue.status;
    qs('#issue-priority').value = issue.priority;
    qs('#issue-assignee').value = issue.assignee_id || '';
    qs('#btn-archive-issue').style.display = 'inline-flex';
    qs('#issue-modal-extended').style.display = 'block';

    // Hook extended sections for later phases
    if (typeof loadCommentsAndActivity === 'function') loadCommentsAndActivity(issue.id);
    if (typeof loadIssueLabels === 'function') loadIssueLabels(issue.id);
    if (typeof loadIssueSubtasks === 'function') loadIssueSubtasks(issue.id);
    if (typeof loadIssueDependencies === 'function') loadIssueDependencies(issue.id);
  } else {
    title.textContent = 'Create Issue';
    keyBadge.textContent = 'NEW';
    qs('#issue-status').value = preselectStatus;
    qs('#issue-priority').value = 'MEDIUM';
    qs('#issue-assignee').value = '';
    qs('#btn-archive-issue').style.display = 'none';
    qs('#issue-modal-extended').style.display = 'none';
  }

  overlay.classList.add('active');
  qs('#issue-title').focus();
}

function closeIssueModal() {
  qs('#issue-modal-overlay').classList.remove('active');
  state.editingIssue = null;
}

async function handleIssueFormSubmit(e) {
  e.preventDefault();
  const titleVal = qs('#issue-title').value.trim();
  if (!titleVal) { toast('Issue title is required.', 'error'); return; }

  const dto = {
    title: titleVal,
    description: qs('#issue-description').value.trim() || undefined,
    status: qs('#issue-status').value,
    priority: qs('#issue-priority').value,
    assignee_id: qs('#issue-assignee').value || undefined,
  };

  const btn = qs('#btn-submit-issue');
  btn.disabled = true;

  try {
    if (state.editingIssue) {
      await apiFetch(`/organizations/${state.orgId}/projects/${state.boardProjectId}/issues/${state.editingIssue.id}`, {
        method: 'PATCH',
        body: JSON.stringify(dto),
      });
      toast('Issue updated.', 'success');
    } else {
      await apiFetch(`/organizations/${state.orgId}/projects/${state.boardProjectId}/issues`, {
        method: 'POST',
        body: JSON.stringify(dto),
      });
      toast('Issue created.', 'success');
    }
    closeIssueModal();
    await fetchBoardIssues();
  } catch (err) {
    toast(`Save issue failed: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
  }
}

async function archiveCurrentEditingIssue() {
  if (!state.editingIssue) return;
  try {
    await apiFetch(`/organizations/${state.orgId}/projects/${state.boardProjectId}/issues/${state.editingIssue.id}/archive`, {
      method: 'POST',
    });
    toast('Issue archived.', 'info');
    closeIssueModal();
    await fetchBoardIssues();
  } catch (err) {
    toast(`Archive failed: ${err.message}`, 'error');
  }
}

/* ── Comments & Activity Timeline Module (Phase 6F) ───────── */
async function loadCommentsAndActivity(issueId) {
  const container = qs('#activity-timeline');
  const section = qs('#issue-activity-section');
  if (!container || !section) return;

  section.style.display = 'block';
  container.innerHTML = '<div class="skeleton-loader" style="height:60px"></div>';

  try {
    const activity = await apiFetch(
      `/organizations/${state.orgId}/projects/${state.boardProjectId}/issues/${issueId}/activity`
    );
    renderActivityTimeline(activity || [], issueId);
  } catch (err) {
    container.innerHTML = `<p style="color:var(--accent-red);font-size:0.82rem">Failed to load activity: ${err.message}</p>`;
  }

  // Wire new comment submit
  const btnSubmit = qs('#btn-submit-comment');
  if (btnSubmit) {
    btnSubmit.onclick = async () => {
      const input = qs('#comment-text-input');
      const text = input ? input.value.trim() : '';
      if (!text) { toast('Comment content cannot be empty.', 'error'); return; }

      btnSubmit.disabled = true;
      try {
        await apiFetch(
          `/organizations/${state.orgId}/projects/${state.boardProjectId}/issues/${issueId}/comments`,
          {
            method: 'POST',
            body: JSON.stringify({ content: text }),
          }
        );
        if (input) input.value = '';
        toast('Comment added.', 'success');
        await loadCommentsAndActivity(issueId);
      } catch (e) {
        toast(`Comment failed: ${e.message}`, 'error');
      } finally {
        btnSubmit.disabled = false;
      }
    };
  }
}

function renderActivityTimeline(items, issueId) {
  const container = qs('#activity-timeline');
  if (!container) return;

  if (!items.length) {
    container.innerHTML = '<p style="color:var(--text-muted);font-size:0.82rem">No comments or activity history yet.</p>';
    return;
  }

  container.innerHTML = items
    .map((item) => {
      const isComment = item.type === 'comment';
      const initial = item.actor_name ? item.actor_name[0].toUpperCase() : 'U';
      const timeStr = new Date(item.timestamp).toLocaleString();
      const isAuthor = state.user && item.actor_id === state.user.id;

      if (isComment) {
        return `
          <div class="activity-item comment-item" data-comment-id="${item.id}" style="margin-bottom:0.85rem;padding:0.75rem;background:var(--bg-primary);border:1px solid var(--border-subtle);border-radius:var(--radius-md)">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.4rem">
              <div style="display:flex;align-items:center;gap:0.4rem">
                <div class="member-chip" style="margin:0">${initial}</div>
                <strong style="font-size:0.82rem">${escHtml(item.actor_name)}</strong>
                <span style="font-size:0.72rem;color:var(--text-muted)">${timeStr}</span>
              </div>
              ${
                isAuthor
                  ? `<div class="comment-actions" style="display:flex;gap:0.3rem">
                      <button class="btn-xs btn-ghost btn-edit-comment" data-id="${item.id}">Edit</button>
                      <button class="btn-xs btn-ghost btn-danger btn-delete-comment" data-id="${item.id}">Delete</button>
                    </div>`
                  : ''
              }
            </div>
            <div class="comment-body" id="cbody-${item.id}" style="font-size:0.85rem;color:var(--text-primary);white-space:pre-wrap">${escHtml(item.content || '')}</div>
          </div>`;
      } else {
        return `
          <div class="activity-item audit-item" style="margin-bottom:0.6rem;font-size:0.78rem;color:var(--text-secondary);display:flex;align-items:center;gap:0.4rem">
            <span style="color:var(--accent-purple)">●</span>
            <strong>${escHtml(item.actor_name)}</strong>
            <span>${item.action.replace('_', ' ').toLowerCase()}</span>
            <span style="color:var(--text-muted);margin-left:auto">${timeStr}</span>
          </div>`;
      }
    })
    .join('');

/* ── Labels Module (Phase 6G) ─────────────────────────────── */
async function loadProjectLabels(projectId) {
  if (!state.orgId || !projectId) return [];
  try {
    const labels = await apiFetch(`/organizations/${state.orgId}/projects/${projectId}/labels`);
    state.projectLabels = labels || [];
    populateLabelFilterDropdown();
    return state.projectLabels;
  } catch (_) {
    state.projectLabels = [];
    return [];
  }
}

function populateLabelFilterDropdown() {
  const sel = qs('#filter-board-label');
  if (!sel) return;
  if (!state.projectLabels || !state.projectLabels.length) {
    sel.style.display = 'none';
    return;
  }
  sel.style.display = 'inline-block';
  sel.innerHTML = '<option value="">All Labels</option>' +
    state.projectLabels.map(l => `<option value="${l.id}">${escHtml(l.name)}</option>`).join('');
}

async function loadIssueLabels(issueId) {
  const section = qs('#issue-labels-section');
  const container = qs('#issue-labels-list');
  if (!section || !container) return;

  section.style.display = 'block';
  container.innerHTML = '<div class="skeleton-loader" style="height:24px;width:120px"></div>';

  await loadProjectLabels(state.boardProjectId);

  try {
    const assignedLabels = await apiFetch(
      `/organizations/${state.orgId}/projects/${state.boardProjectId}/issues/${issueId}/labels`
    );
    renderIssueLabels(assignedLabels || [], issueId);
  } catch (err) {
    container.innerHTML = `<p style="color:var(--accent-red);font-size:0.8rem">${err.message}</p>`;
  }
}

function renderIssueLabels(assignedLabels, issueId) {
  const container = qs('#issue-labels-list');
  if (!container) return;

  const assignedIds = new Set(assignedLabels.map(l => l.id));

  if (!state.projectLabels || !state.projectLabels.length) {
    container.innerHTML = `
      <span style="font-size:0.78rem;color:var(--text-muted)">No project labels created.</span>
      <button type="button" class="btn-xs btn-ghost" id="btn-create-proj-label">+ Create Label</button>`;
    const btnCreate = qs('#btn-create-proj-label');
    if (btnCreate) {
      btnCreate.onclick = async () => {
        const name = prompt('Enter label name:');
        if (!name || !name.trim()) return;
        try {
          await apiFetch(`/organizations/${state.orgId}/projects/${state.boardProjectId}/labels`, {
            method: 'POST',
            body: JSON.stringify({ name: name.trim(), color: '#6366f1' }),
          });
          toast('Label created.', 'success');
          await loadIssueLabels(issueId);
        } catch (e) {
          toast(`Create label failed: ${e.message}`, 'error');
        }
      };
    }
    return;
  }

  container.innerHTML = state.projectLabels.map(label => {
    const isAssigned = assignedIds.has(label.id);
    return `
      <span class="label-chip${isAssigned ? ' assigned' : ''}" data-label-id="${label.id}" style="font-size:0.75rem;padding:3px 8px;border-radius:999px;cursor:pointer;border:1px solid ${label.color};background:${isAssigned ? label.color : 'transparent'};color:${isAssigned ? '#fff' : label.color}">
        ${isAssigned ? '✓ ' : '+ '}${escHtml(label.name)}
      </span>`;
  }).join('') + ` <button type="button" class="btn-xs btn-ghost" id="btn-create-proj-label" style="margin-left:0.4rem">+ Label</button>`;

  qsa('.label-chip', container).forEach(chip => {
    chip.onclick = async () => {
      const labelId = chip.dataset.labelId;
      const isAssigned = chip.classList.contains('assigned');
      try {
        if (isAssigned) {
          await apiFetch(`/organizations/${state.orgId}/projects/${state.boardProjectId}/issues/${issueId}/labels/${labelId}`, {
            method: 'DELETE',
          });
        } else {
          await apiFetch(`/organizations/${state.orgId}/projects/${state.boardProjectId}/issues/${issueId}/labels`, {
            method: 'POST',
            body: JSON.stringify({ label_id: labelId }),
          });
        }
        await loadIssueLabels(issueId);
      } catch (e) {
        toast(`Toggle label failed: ${e.message}`, 'error');
      }
    };
  });

/* ── Subtasks & Dependencies Module (Phase 6H) ───────────── */
async function loadIssueSubtasks(issueId) {
  const section = qs('#issue-subtasks-section');
  const container = qs('#subtasks-list');
  const progContainer = qs('#subtasks-progress-wrapper');
  if (!section || !container) return;

  section.style.display = 'block';
  container.innerHTML = '<div class="skeleton-loader" style="height:40px"></div>';

  try {
    const subtasks = await apiFetch(
      `/organizations/${state.orgId}/projects/${state.boardProjectId}/issues/${issueId}/subtasks`
    );
    const progress = await apiFetch(
      `/organizations/${state.orgId}/projects/${state.boardProjectId}/issues/${issueId}/subtasks/progress`
    );

    if (progContainer && progress) {
      progContainer.innerHTML = `
        <div style="display:flex;justify-content:space-between;font-size:0.75rem;margin-bottom:3px;color:var(--text-secondary)">
          <span>Progress: ${progress.completed_subtasks}/${progress.total_subtasks} completed</span>
          <span>${progress.completion_percentage}%</span>
        </div>
        <div style="height:6px;background:var(--bg-tertiary);border-radius:999px;overflow:hidden">
          <div style="height:100%;background:var(--accent-green);width:${progress.completion_percentage}%"></div>
        </div>`;
    }

    renderSubtasksList(subtasks || [], issueId);
  } catch (err) {
    container.innerHTML = `<p style="color:var(--accent-red);font-size:0.8rem">${err.message}</p>`;
  }

  const btnAdd = qs('#btn-add-subtask');
  if (btnAdd) {
    btnAdd.onclick = async () => {
      const title = prompt('Enter subtask title:');
      if (!title || !title.trim()) return;
      try {
        await apiFetch(
          `/organizations/${state.orgId}/projects/${state.boardProjectId}/issues/${issueId}/subtasks`,
          {
            method: 'POST',
            body: JSON.stringify({ title: title.trim() }),
          }
        );
        toast('Subtask created.', 'success');
        await loadIssueSubtasks(issueId);
      } catch (e) {
        toast(`Subtask failed: ${e.message}`, 'error');
      }
    };
  }
}

function renderSubtasksList(subtasks, parentIssueId) {
  const container = qs('#subtasks-list');
  if (!container) return;

  if (!subtasks.length) {
    container.innerHTML = '<p style="color:var(--text-muted);font-size:0.78rem">No subtasks created yet.</p>';
    return;
  }

  container.innerHTML = subtasks.map(s => {
    const isDone = s.status === 'DONE';
    return `
      <div style="display:flex;align-items:center;justify-content:space-between;padding:0.4rem 0.6rem;background:var(--bg-primary);border:1px solid var(--border-subtle);border-radius:var(--radius-sm);margin-bottom:0.35rem">
        <label style="display:flex;align-items:center;gap:0.5rem;font-size:0.82rem;cursor:pointer;${isDone ? 'text-decoration:line-through;color:var(--text-muted)' : ''}">
          <input type="checkbox" class="subtask-chk" data-id="${s.id}" ${isDone ? 'checked' : ''} />
          <span>${s.identifier}: ${escHtml(s.title)}</span>
        </label>
        <span class="priority-pill priority-${s.priority}" style="font-size:0.62rem">${s.priority}</span>
      </div>`;
  }).join('');

  qsa('.subtask-chk', container).forEach(chk => {
    chk.onchange = async () => {
      const sid = chk.dataset.id;
      const newStatus = chk.checked ? 'DONE' : 'TODO';
      try {
        await apiFetch(
          `/organizations/${state.orgId}/projects/${state.boardProjectId}/issues/${sid}`,
          {
            method: 'PATCH',
            body: JSON.stringify({ status: newStatus }),
          }
        );
        await loadIssueSubtasks(parentIssueId);
      } catch (e) {
        toast(`Update subtask status failed: ${e.message}`, 'error');
      }
    };
  });
}

async function loadIssueDependencies(issueId) {
  const section = qs('#issue-dependencies-section');
  const container = qs('#dependencies-list');
  if (!section || !container) return;

  section.style.display = 'block';
  container.innerHTML = '<div class="skeleton-loader" style="height:40px"></div>';

  try {
    const deps = await apiFetch(
      `/organizations/${state.orgId}/projects/${state.boardProjectId}/issues/${issueId}/dependencies`
    );
    renderDependenciesList(deps || [], issueId);
  } catch (err) {
    container.innerHTML = `<p style="color:var(--accent-red);font-size:0.8rem">${err.message}</p>`;
  }

  const btnAdd = qs('#btn-add-dependency');
  if (btnAdd) {
    btnAdd.onclick = async () => {
      const targetId = prompt('Enter target Issue UUID to link:');
      if (!targetId || !targetId.trim()) return;
      const type = prompt('Enter dependency type (BLOCKS, BLOCKED_BY, RELATES_TO):', 'BLOCKS');
      if (!type || !type.trim()) return;

      try {
        await apiFetch(
          `/organizations/${state.orgId}/projects/${state.boardProjectId}/issues/${issueId}/dependencies`,
          {
            method: 'POST',
            body: JSON.stringify({
              target_issue_id: targetId.trim(),
              dependency_type: type.trim().toUpperCase(),
            }),
          }
        );
        toast('Dependency linked.', 'success');
        await loadIssueDependencies(issueId);
      } catch (e) {
        toast(`Dependency link failed: ${e.message}`, 'error');
      }
    };
  }
}

function renderDependenciesList(deps, issueId) {
  const container = qs('#dependencies-list');
  if (!container) return;

  if (!deps.length) {
    container.innerHTML = '<p style="color:var(--text-muted);font-size:0.78rem">No linked dependencies.</p>';
    return;
  }

  container.innerHTML = deps.map(d => {
    const target = d.target_issue || {};
    return `
      <div style="display:flex;align-items:center;justify-content:space-between;padding:0.4rem 0.6rem;background:var(--bg-primary);border:1px solid var(--border-subtle);border-radius:var(--radius-sm);margin-bottom:0.35rem;font-size:0.8rem">
        <div>
          <span style="font-weight:700;color:var(--accent-purple);margin-right:0.4rem">${d.dependency_type}</span>
          <span>${target.identifier || 'ISSUE'}: ${escHtml(target.title || '')}</span>
        </div>
        <button class="btn-xs btn-ghost btn-danger btn-del-dep" data-id="${d.id}">✕</button>
      </div>`;
  }).join('');

  qsa('.btn-del-dep', container).forEach(btn => {
    btn.onclick = async () => {
      try {
        await apiFetch(
          `/organizations/${state.orgId}/projects/${state.boardProjectId}/issues/${issueId}/dependencies/${btn.dataset.id}`,
          { method: 'DELETE' }
        );
        toast('Dependency removed.', 'info');
        await loadIssueDependencies(issueId);
      } catch (e) {
        toast(`Remove dependency failed: ${e.message}`, 'error');
      }
    };
  });
}

/* ── Navigation ─────────────────────────────────────────── */
function switchView(name) {
  state.activeView = name;

  qsa('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.view === name);
  });

  qsa('.view').forEach(v => v.classList.remove('active'));
  qs(`#view-${name}`).classList.add('active');

  const labels = { projects: 'Projects', board: 'Kanban Board', templates: 'Templates', analytics: 'Analytics', archived: 'Archived' };
  qs('#breadcrumb').textContent = labels[name] || name;

  if (name === 'archived') fetchProjects(true);
  if (name === 'analytics') {
    if (!state.projects.length && state.orgId) fetchProjects();
  }
  if (name === 'board') {
    if (!state.projects.length && state.orgId) {
      fetchProjects().then(() => loadBoardView());
    } else {
      loadBoardView();
    }
  }
}

/* ── Settings Save ──────────────────────────────────────── */
async function saveProjectSettings(e) {
  e.preventDefault();
  if (!state.currentProject) return;
  const dto = {
    name: qs('#settings-name').value.trim(),
    description: qs('#settings-desc').value.trim() || null,
  };
  try {
    await apiFetch(`/organizations/${state.orgId}/projects/${state.currentProject.id}`, {
      method: 'PATCH',
      body: JSON.stringify(dto),
    });
    toast('Project settings saved.', 'success');
    await fetchProjects();
    closeDrawer();
  } catch (e) {
    toast(`Save failed: ${e.message}`, 'error');
  }
}

/* ── Event Wiring ───────────────────────────────────────── */
function wireEvents() {
  // Navigation
  qsa('.nav-item').forEach(el => {
    el.addEventListener('click', (e) => { e.preventDefault(); switchView(el.dataset.view); });
  });

  // Org selector
  qs('#org-select').addEventListener('change', async (e) => {
    state.orgId = e.target.value || null;
    localStorage.setItem('dt_org_id', state.orgId || '');
    qs('#btn-new-project').disabled = !state.orgId;
    if (state.orgId) {
      state.page = 1;
      await fetchProjects();
      if (state.activeView === 'board') loadBoardView();
    } else {
      qs('#project-grid').innerHTML = '<div class="empty-state"><div class="empty-icon">◈</div><h3>Select an organization</h3></div>';
    }
  });

  // New Project
  qs('#btn-new-project').addEventListener('click', () => {
    if (!state.orgId) { toast('Select an organization first.', 'error'); return; }
    openCreateModal();
  });

  // Modal close
  qs('#btn-close-modal').addEventListener('click', closeCreateModal);
  qs('#btn-cancel-modal').addEventListener('click', closeCreateModal);
  qs('#create-modal-overlay').addEventListener('click', (e) => {
    if (e.target === qs('#create-modal-overlay')) closeCreateModal();
  });

  // Create project form
  qs('#create-project-form').addEventListener('submit', handleCreateProject);

  // Drawer
  qs('#drawer-overlay').addEventListener('click', closeDrawer);
  qs('#btn-close-drawer').addEventListener('click', closeDrawer);

  // Drawer tabs
  qsa('.drawer-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      activateDrawerTab(tab.dataset.tab);
      if (tab.dataset.tab === 'members' && state.currentProject) {
        loadMembers(state.currentProject.id);
      }
    });
  });

  // Settings form
  qs('#project-settings-form').addEventListener('submit', saveProjectSettings);

  // Search
  qs('#search-input').addEventListener('input', debounce(async (e) => {
    state.query = e.target.value.trim();
    state.page = 1;
    await fetchProjects();
  }, 400));

  // Filter pills
  qsa('.filter-pill').forEach(pill => {
    pill.addEventListener('click', async () => {
      qsa('.filter-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      state.filterType = pill.dataset.filter;
      state.page = 1;
      await fetchProjects();
    });
  });

  // Pagination
  qs('#btn-prev').addEventListener('click', async () => {
    if (state.page > 1) { state.page--; await fetchProjects(); }
  });
  qs('#btn-next').addEventListener('click', async () => {
    if (state.page < state.pages) { state.page++; await fetchProjects(); }
  });

  // Analytics project select
  qs('#analytics-project-select').addEventListener('change', (e) => {
    if (e.target.value) loadAnalytics(e.target.value);
    else {
      qs('#analytics-select-prompt').style.display = 'flex';
      qs('#analytics-content').style.display = 'none';
    }
  });

  // ── Board Event Wire ──
  const boardProjSel = qs('#board-project-select');
  if (boardProjSel) {
    boardProjSel.addEventListener('change', (e) => {
      if (e.target.value) loadBoardView(e.target.value);
    });
  }

  const boardSel = qs('#board-select');
  if (boardSel) {
    boardSel.addEventListener('change', (e) => {
      if (e.target.value) loadBoardDetails(e.target.value);
    });
  }

  const btnCreateIssue = qs('#btn-create-issue');
  if (btnCreateIssue) {
    btnCreateIssue.addEventListener('click', () => openIssueModal());
  }

  const btnAddCol = qs('#btn-add-column');
  if (btnAddCol) {
    btnAddCol.addEventListener('click', () => openColumnModal());
  }

  // Issue modal events
  qs('#btn-close-issue-modal').addEventListener('click', closeIssueModal);
  qs('#btn-cancel-issue-modal').addEventListener('click', closeIssueModal);
  qs('#issue-modal-overlay').addEventListener('click', (e) => {
    if (e.target === qs('#issue-modal-overlay')) closeIssueModal();
  });
  qs('#issue-form').addEventListener('submit', handleIssueFormSubmit);
  qs('#btn-archive-issue').addEventListener('click', archiveCurrentEditingIssue);

  // Column modal events
  qs('#btn-close-column-modal').addEventListener('click', closeColumnModal);
  qs('#btn-cancel-column-modal').addEventListener('click', closeColumnModal);
  qs('#column-modal-overlay').addEventListener('click', (e) => {
    if (e.target === qs('#column-modal-overlay')) closeColumnModal();
  });
  qs('#column-form').addEventListener('submit', handleColumnFormSubmit);

  // Board Filter Events
  qs('#board-search-input').addEventListener('input', debounce(async (e) => {
    state.boardQuery = e.target.value.trim();
    await fetchBoardIssues();
  }, 350));

  qs('#filter-board-priority').addEventListener('change', async (e) => {
    state.boardPriorityFilter = e.target.value;
    await fetchBoardIssues();
  });

  qs('#filter-board-assignee').addEventListener('change', async (e) => {
    state.boardAssigneeFilter = e.target.value;
    await fetchBoardIssues();
  });

  // Keyboard: Escape to close
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeDrawer();
      closeCreateModal();
      closeIssueModal();
      closeColumnModal();
    }
  });

  // Real-time Comment Typing Listener
  const commentInput = qs('#comment-text-input');
  if (commentInput) {
    let typeTimer = null;
    commentInput.addEventListener('input', () => {
      if (state.editingIssue) {
        wsClient.send('TYPING_START', { issue_id: state.editingIssue.id });
        if (typeTimer) clearTimeout(typeTimer);
        typeTimer = setTimeout(() => {
          wsClient.send('TYPING_STOP', { issue_id: state.editingIssue.id });
        }, 2000);
      }
    });
  }
}

/* ── Real-Time WebSockets Engine (Phase 7) ───────────────── */
class DevTrackWS {
  constructor() {
    this.ws = null;
    this.projectId = null;
    this.reconnectTimer = null;
    this.pingInterval = null;
  }

  connect(projectId) {
    if (!state.token || !state.orgId || !projectId) return;
    if (this.ws && this.projectId === projectId && this.ws.readyState === WebSocket.OPEN) return;

    this.disconnect();
    this.projectId = projectId;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${protocol}//${host}/api/v1/organizations/${state.orgId}/projects/${projectId}/ws?token=${encodeURIComponent(state.token)}`;

    try {
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        console.log('[DevTrack WS] Connected to project room:', projectId);
        this.startHeartbeat();
      };

      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          this.handleEvent(msg);
        } catch (e) {
          console.error('[DevTrack WS] Frame parse error:', e);
        }
      };

      this.ws.onclose = () => {
        console.log('[DevTrack WS] Disconnected');
        this.stopHeartbeat();
        this.scheduleReconnect();
      };

      this.ws.onerror = (err) => {
        console.warn('[DevTrack WS] Error:', err);
      };
    } catch (err) {
      console.error('[DevTrack WS] Connection error:', err);
    }
  }

  disconnect() {
    this.stopHeartbeat();
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.close();
      this.ws = null;
    }
  }

  startHeartbeat() {
    this.stopHeartbeat();
    this.pingInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ event_type: 'ping' }));
      }
    }, 25000);
  }

  stopHeartbeat() {
    if (this.pingInterval) clearInterval(this.pingInterval);
  }

  scheduleReconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => {
      if (this.projectId) this.connect(this.projectId);
    }, 5000);
  }

  send(eventType, payload = {}) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ event_type: eventType, ...payload }));
    }
  }

  handleEvent(msg) {
    const { event_type, sender_id, sender_name, payload } = msg;
    const isSelf = state.user && String(sender_id) === String(state.user.id);

    switch (event_type) {
      case 'PRESENCE_UPDATE':
        renderPresenceAvatars(payload.users || []);
        break;

      case 'TYPING_START':
        if (!isSelf && state.editingIssue && String(msg.issue_id) === String(state.editingIssue.id)) {
          showTypingIndicator(`${sender_name || 'Someone'} is typing...`);
        }
        break;

      case 'TYPING_STOP':
        if (!isSelf && state.editingIssue && String(msg.issue_id) === String(state.editingIssue.id)) {
          hideTypingIndicator();
        }
        break;

      case 'ISSUE_MOVED':
      case 'BOARD_UPDATE':
        if (!isSelf && state.activeBoard) {
          toast(`Board updated by ${sender_name || 'teammate'}`, 'info');
          fetchBoardIssues();
        }
        break;

      case 'COMMENT_CREATED':
        if (!isSelf && state.editingIssue && String(msg.issue_id) === String(state.editingIssue.id)) {
          toast(`New comment from ${sender_name || 'a teammate'}`, 'info');
          loadCommentsAndActivity(state.editingIssue.id);
        }
        break;

      case 'NOTIFICATION':
        toast(payload.message || 'New notification', 'info');
        break;
    }
  }
}

const wsClient = new DevTrackWS();

function renderPresenceAvatars(users) {
  const container = qs('#presence-avatars');
  if (!container) return;
  if (!users || users.length === 0) {
    container.innerHTML = '';
    return;
  }
  container.innerHTML = users.map(u => {
    const initials = (u.name || 'U').split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
    return `<div class="presence-avatar" title="${escHtml(u.name)}">${initials}</div>`;
  }).join('');
}

let typingTimer = null;
function showTypingIndicator(msg) {
  const el = qs('#typing-indicator');
  if (!el) return;
  el.style.display = 'flex';
  el.innerHTML = `<span>${escHtml(msg)}</span><span class="typing-dots"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></span>`;
  if (typingTimer) clearTimeout(typingTimer);
  typingTimer = setTimeout(hideTypingIndicator, 4000);
}

function hideTypingIndicator() {
  const el = qs('#typing-indicator');
  if (el) el.style.display = 'none';
}

/* ── Init ───────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', async () => {
  wireEvents();
  await bootstrap();
});
