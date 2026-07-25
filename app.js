// ============================================================
// MediOps — frontend (talks to the Python backend)
// Flow: load events -> live tiles -> drill-down (gated)
//       -> toggle de-identified wall mode -> HMIS report -> access audit
// ============================================================

const state = {
  roleKey: null,
  role: null,        // capabilities from server
  reveal: false,     // false = de-identified wall mode (default)
  view: 'dashboard',
  kpis: null,
  drill: { metric: 'active', ward: 'ALL' },
  report: null,
};

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

async function api(path, opts = {}) {
  const join = path.includes('?') ? '&' : '?';
  const res = await fetch(`${path}${join}role=${state.roleKey || 'superintendent'}`, {
    headers: { 'Content-Type': 'application/json' }, ...opts,
  });
  return { ok: res.ok, status: res.status, data: await res.json().catch(() => ({})) };
}
function logAction(action, target, detail) {
  api('/api/log', { method: 'POST', body: JSON.stringify({ action, target, detail }) });
}
function toast(msg, cls = '') {
  const t = document.createElement('div');
  t.className = `toast ${cls}`; t.textContent = msg;
  $('#toast-host').appendChild(t);
  setTimeout(() => t.remove(), 2400);
}
function fmtWhen(iso) {
  const d = new Date(iso);
  return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false });
}

const ICON = {
  dashboard: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg>',
  report: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h6"/></svg>',
  audit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z"/><path d="M9 12l2 2 4-4"/></svg>',
};

// ============================================================
// LOGIN
// ============================================================
async function initLogin() {
  const { data } = await api('/api/roles');
  const initials = (n) => n.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase();
  $('#role-list').innerHTML = data.roles.map(r => `
    <button class="role-opt" data-role="${r.key}">
      <span class="role-av">${initials(r.user)}</span>
      <span>
        <div class="r-name">${esc(r.user)}</div>
        <div class="r-title">${esc(r.title)}</div>
      </span>
      <span class="r-arrow">→</span>
    </button>`).join('');
  $$('.role-opt').forEach(b => b.addEventListener('click', () => login(b.dataset.role)));
}

function login(roleKey) {
  state.roleKey = roleKey;
  state.reveal = false;
  $('#login').classList.add('hidden');
  $('#app').classList.remove('hidden');
  loadDashboard();
}
function logout() {
  state.roleKey = null; state.role = null; state.reveal = false;
  $('#app').classList.add('hidden');
  $('#login').classList.remove('hidden');
}

// ============================================================
// SHELL
// ============================================================
function buildNav() {
  const items = [{ id: 'dashboard', label: 'Dashboard', icon: 'dashboard' }];
  if (state.role.canReport) items.push({ id: 'report', label: 'HMIS Report', icon: 'report' });
  if (state.role.canAudit) items.push({ id: 'audit', label: 'Access Audit', icon: 'audit' });
  const navHtml = items.map(i =>
    `<button data-view="${i.id}">${ICON[i.icon]}<span>${i.label}</span></button>`).join('');
  $('#nav').innerHTML = navHtml;
  $('#mnav').innerHTML = navHtml + `<button data-nav="signout" class="mnav-out">Sign out</button>`;
  $$('#nav button, #mnav button').forEach(b => b.addEventListener('click', () => {
    if (b.dataset.nav === 'signout') return logout();
    go(b.dataset.view);
  }));
  $('#u-name').textContent = state.role.user;
  $('#u-title').textContent = state.role.title;
}
function go(view) {
  state.view = view;
  $$('#nav button, #mnav button').forEach(b => b.classList.toggle('active', b.dataset.view === view));
  if (view === 'dashboard') renderDashboard();
  else if (view === 'report') renderReport();
  else if (view === 'audit') renderAudit();
}
function setTitle(t, sub) { $('#view-title').textContent = t; $('#view-sub').textContent = sub || ''; }

// ---- de-identified wall-mode toggle ----
function syncDeid() {
  const on = state.reveal;
  $('#deid').classList.toggle('on', on);
  $('#deid-toggle').setAttribute('aria-checked', String(on));
  $('#deid-state').textContent = on ? 'Identified (authorised)' : 'De-identified';
}
function toggleReveal() {
  state.reveal = !state.reveal;
  syncDeid();
  logAction('TOGGLE_WALL_MODE', 'display mode',
    state.reveal ? 'requested identified reveal' : 'restored de-identified');
  if (!state.role.canReveal && state.reveal) {
    toast('Reveal will be denied for your role — attempt is audited', 'warn');
  }
  if (state.view === 'dashboard' && $('#drill-panel')) loadDrill();
}

// ============================================================
// DASHBOARD  (KPIs + occupancy + case mix + drill-down)
// ============================================================
async function loadDashboard() {
  const { data } = await api('/api/kpis');
  state.kpis = data;
  state.role = data.role;
  buildNav();
  syncDeid();
  go('dashboard');
}

function renderDashboard() {
  const d = state.kpis;
  const scope = state.role.scope ? `${state.role.scope} (unit scope)` : 'All wards';
  setTitle('Dashboard', `${scope} · as of ${fmtWhen(d.asOf)}`);

  $('#view').innerHTML = `
    <div class="kpi-grid">
      ${d.kpis.map(k => `
        <div class="kpi tone-${k.tone}" data-metric="${k.key}">
          <div class="kpi-label">${esc(k.label)}</div>
          <div class="kpi-value num">${k.value}<span class="kpi-unit">${esc(k.unit)}</span></div>
          <div class="kpi-sub">${esc(k.sub)}</div>
          <div class="kpi-drill">drill ↗</div>
        </div>`).join('')}
    </div>

    <div class="grid-2" style="margin-bottom:22px">
      <div class="card">
        <div class="card-head"><h3>Bed occupancy by ward</h3><span class="pill muted">live</span></div>
        <div class="card-pad" style="padding-top:6px">
          ${d.wardOccupancy.map(w => {
            const cls = w.pct >= 95 ? 'crit' : w.pct >= 85 ? 'hot' : '';
            return `<div class="ward-row">
              <span class="ward-name">${esc(w.ward)}</span>
              <div class="ward-bar"><span class="${cls}" style="width:${Math.min(w.pct, 100)}%"></span></div>
              <span class="ward-meta">${w.occ}/${w.cap} · ${w.pct}%</span>
            </div>`;
          }).join('')}
        </div>
      </div>

      <div class="card">
        <div class="card-head"><h3>Case mix — discharges (30d)</h3><span class="pill info">FR-10 suppression</span></div>
        <table class="matrix">
          <thead><tr><th>Ward</th>${d.caseMix.payers.map(p => `<th style="text-align:right">${esc(p)}</th>`).join('')}</tr></thead>
          <tbody>
            ${d.caseMix.rows.map(r => `<tr><td>${esc(r.ward)}</td>${r.cells.map(c =>
              c === '—' ? `<td class="sup">—</td>` : `<td class="n">${c}</td>`).join('')}</tr>`).join('')}
          </tbody>
        </table>
        <div class="suppress-note">Cells with fewer than 5 records are suppressed (—) to prevent re-identification.</div>
      </div>
    </div>

    <div id="drill-panel"></div>
  `;
  $$('.kpi').forEach(k => k.addEventListener('click', () => {
    state.drill = { metric: k.dataset.metric, ward: 'ALL' };
    loadDrill(true);
  }));
}

async function loadDrill(scrollTo) {
  const { metric, ward } = state.drill;
  const { data } = await api(`/api/drilldown?metric=${metric}&ward=${encodeURIComponent(ward)}&reveal=${state.reveal ? 1 : 0}`);
  const kLabel = (state.kpis.kpis.find(k => k.key === metric) || {}).label || metric;
  const wardOpts = ['ALL', ...state.kpis.wardOccupancy.map(w => w.ward)];

  let banner = '';
  if (data.denied) {
    banner = `<div class="banner crit">⚠ Identified reveal denied — your role may only view de-identified data. This attempt has been recorded in the access audit (FR-14).</div>`;
  } else if (data.identified) {
    banner = `<div class="banner warn">● Identified patient data is visible. This access is logged. Toggle the display mode back to de-identified when finished.</div>`;
  } else {
    banner = `<div class="banner ok">🔒 De-identified view — patients shown as pseudonymous tokens (FR-10 default).</div>`;
  }

  $('#drill-panel').innerHTML = `
    <div class="sec-title">Drill-down · row-level detail</div>
    <div class="drill-bar">
      <strong style="font-size:14px">${esc(kLabel)}</strong>
      <span class="pill muted">${data.count} records</span>
      <label style="margin-left:auto;font-size:12.5px;color:var(--muted)">Ward
        <select id="drill-ward" ${state.role.scope ? 'disabled' : ''}>
          ${wardOpts.map(w => `<option value="${esc(w)}" ${w === ward ? 'selected' : ''}>${w === 'ALL' ? 'All wards' : esc(w)}</option>`).join('')}
        </select>
      </label>
    </div>
    ${banner}
    <div class="card" style="overflow:hidden">
      <table class="data">
        <thead><tr>
          <th>Episode</th>
          ${data.identified ? '<th>Patient</th><th>UHID</th>' : '<th>Patient (token)</th>'}
          <th>Event</th><th>Ward</th><th>Payer</th><th>Timestamp</th>
        </tr></thead>
        <tbody>
          ${data.rows.map(r => `<tr>
            <td class="mono">${esc(r.episode)}</td>
            ${data.identified
              ? `<td style="font-weight:550">${esc(r.name)}</td><td class="mono">${esc(r.uhid)}</td>`
              : `<td><span class="token">${esc(r.token)}</span></td>`}
            <td>${esc(r.type)}</td>
            <td>${esc(r.ward)}</td>
            <td>${esc(r.payer)}</td>
            <td class="mono">${fmtWhen(r.when)}</td>
          </tr>`).join('') || `<tr><td colspan="6" class="empty">No records.</td></tr>`}
        </tbody>
      </table>
      ${data.shown < data.count ? `<div class="suppress-note">Showing first ${data.shown} of ${data.count}.</div>` : ''}
    </div>
  `;
  const sel = $('#drill-ward');
  if (sel) sel.addEventListener('change', () => { state.drill.ward = sel.value; loadDrill(); });
  if (scrollTo) $('#drill-panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ============================================================
// HMIS REPORT
// ============================================================
function renderReport() {
  setTitle('HMIS Report', 'Statutory monthly report · review and submit');
  if (!state.report) {
    $('#view').innerHTML = `
      <div class="card"><div class="empty">
        <h3>No report generated yet</h3>
        <p>Compile this month's events into the HMIS monthly format, then review and submit.</p>
        <button class="btn btn-primary" id="gen-report">Generate monthly report</button>
      </div></div>`;
    $('#gen-report').addEventListener('click', generateReport);
    return;
  }
  const r = state.report;
  const submitted = r.status === 'submitted';
  $('#view').innerHTML = `
    <div class="report-doc card" style="padding:0">
      <div class="report-header">
        <div>
          <div class="rh-title">HMIS Monthly Report</div>
          <div class="rh-meta">${esc(r.format)} · Period: ${esc(r.period)} · Report #${r.reportId}</div>
        </div>
        <span class="pill ${submitted ? 'ok' : 'warn'}">${submitted ? 'Submitted' : 'Draft'}</span>
      </div>
      <table class="data">
        <thead><tr>${r.columns.map(c => `<th>${esc(c)}</th>`).join('')}</tr></thead>
        <tbody>
          ${r.rows.map(row => `<tr>
            <td class="code">${esc(row[0])}</td>
            <td>${esc(row[1])}</td>
            <td class="val">${esc(row[2])}</td>
          </tr>`).join('')}
        </tbody>
      </table>
      <div class="report-foot">
        <span class="suppress-note" style="padding:0">${submitted
          ? `Submitted by ${esc(state.role.user)} — a human owns this statutory submission (FR-5).`
          : 'Review the figures. Submission is a deliberate human action, not automatic.'}</span>
        <div style="display:flex;gap:8px">
          <button class="btn btn-sm" id="regen">Regenerate</button>
          <button class="btn btn-primary btn-sm" id="submit-report" ${submitted ? 'disabled' : ''}>${submitted ? 'Submitted ✓' : 'Review & Submit'}</button>
        </div>
      </div>
    </div>`;
  $('#regen').addEventListener('click', generateReport);
  if (!submitted) $('#submit-report').addEventListener('click', submitReport);
}
async function generateReport() {
  const { ok, data } = await api('/api/report/generate', { method: 'POST', body: '{}' });
  if (!ok) { toast('Not permitted to generate reports', 'warn'); return; }
  state.report = data;
  renderReport();
  toast(`Draft report #${data.reportId} generated`);
}
async function submitReport() {
  const { ok, data } = await api('/api/report/submit', { method: 'POST', body: JSON.stringify({ reportId: state.report.reportId }) });
  if (!ok) { toast('Submission not permitted', 'warn'); return; }
  state.report.status = 'submitted';
  renderReport();
  toast(`Report #${data.reportId} submitted`);
}

// ============================================================
// ACCESS AUDIT
// ============================================================
async function renderAudit() {
  setTitle('Access Audit', 'Who viewed or exported what (FR-14)');
  const { ok, data } = await api('/api/audit');
  if (!ok) {
    $('#view').innerHTML = `<div class="card"><div class="empty"><h3>Access denied</h3><p>Your role cannot view the audit log. This attempt was recorded.</p></div></div>`;
    return;
  }
  const tone = (a) => a.includes('DENIED') ? 'crit' : a.startsWith('GENERATE') || a.startsWith('SUBMIT') ? 'info'
    : a.includes('REVEAL') || a.includes('TOGGLE') ? 'warn' : 'muted';
  $('#view').innerHTML = `
    <div class="card" style="overflow:hidden">
      <div class="card-head"><h3>Access log</h3><span class="pill muted">${data.rows.length} entries · newest first</span></div>
      <table class="data">
        <thead><tr><th>Time</th><th>User</th><th>Role</th><th>Action</th><th>Target</th><th>Detail</th></tr></thead>
        <tbody>
          ${data.rows.map(r => `<tr>
            <td class="mono">${fmtWhen(r.ts)}</td>
            <td style="font-weight:550">${esc(r.user)}</td>
            <td><span class="pill muted">${esc(r.role)}</span></td>
            <td><span class="pill ${tone(r.action)} audit-action">${esc(r.action)}</span></td>
            <td>${esc(r.target)}</td>
            <td style="color:var(--muted)">${esc(r.detail)}</td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>`;
}

// ============================================================
// WIRE UP
// ============================================================
$('#logout').addEventListener('click', logout);
$('#deid-toggle').addEventListener('click', toggleReveal);
initLogin();
