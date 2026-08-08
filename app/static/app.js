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

/* ── Navigation ─────────────────────────────────────────── */
function switchView(name) {
  state.activeView = name;

  qsa('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.view === name);
  });

  qsa('.view').forEach(v => v.classList.remove('active'));
  qs(`#view-${name}`).classList.add('active');

  const labels = { projects: 'Projects', templates: 'Templates', analytics: 'Analytics', archived: 'Archived' };
  qs('#breadcrumb').textContent = labels[name] || name;

  if (name === 'archived') fetchProjects(true);
  if (name === 'analytics') {
    if (!state.projects.length && state.orgId) fetchProjects();
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

  // Keyboard: Escape to close
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeDrawer();
      closeCreateModal();
    }
  });
}

/* ── Init ───────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', async () => {
  wireEvents();
  await bootstrap();
});
