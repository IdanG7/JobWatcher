// Router, global state, theme, live status. Every view module exports
// render(root, ctx) -> optional {update(params), onKey(e), cleanup()}.
import {get, post} from './api.js';
import {buildHash, compact, esc, parseHash} from './lib.js';
import {closeDrawer, drawerJob, drawerOpen, openDrawer, quickAction, reloadDrawer} from './detail.js';
import {initPalette, openHelp, openPalette, paletteOpen} from './palette.js';
import {errorState, hideTooltip, icon, modalOpen, toast} from './ui.js';
import {mountView} from './view-loader.js';
import {collectionMarkup} from './collection-status.js';
import * as overview from './views/overview.js';
import * as opportunities from './views/opportunities.js';
import * as applications from './views/applications.js';
import * as companies from './views/companies.js';
import * as calendar from './views/calendar.js';
import * as analytics from './views/analytics.js';
import * as sources from './views/sources.js';
import * as settings from './views/settings.js';

const VIEWS = {overview, opportunities, applications, companies, calendar, analytics, sources, settings};
const TITLES = {overview: 'Overview', opportunities: 'Opportunities', applications: 'Applications', companies: 'Companies',
  calendar: 'Recruiting Calendar', analytics: 'Analytics', sources: 'Sources', settings: 'Settings'};

const store = {
  get(key, fallback = null) { try { return localStorage.getItem(key) ?? fallback; } catch { return fallback; } },
  set(key, value) { try { value === null ? localStorage.removeItem(key) : localStorage.setItem(key, value); } catch { /* private mode */ } },
};

const ctx = {
  meta: null,
  profile: null,
  status: null,
  route: parseHash(location.hash),
  store,
  navigate(path, params = {}, {replace = false} = {}) {
    const hash = buildHash(path, params);
    if (replace) history.replaceState(null, '', hash); else location.hash = hash;
    if (replace) route();
  },
  setParams(patch, {replace = false} = {}) {
    const params = {...ctx.route.params, ...patch};
    for (const k of Object.keys(params)) if (params[k] === '' || params[k] === null || params[k] === undefined) delete params[k];
    ctx.navigate(ctx.route.path, params, {replace});
  },
  /** Render the current view again from scratch (Retry); the old one is cleaned up first. */
  remount() { current.key = null; route(); },
  openJob(key) { ctx.setParams({job: key}); },
  closeJob() { ctx.setParams({job: null}); },
  /** Data changed (save, status move, watch): refresh the view softly and the drawer. */
  changed() {
    current.view?.refresh?.();
    if (drawerOpen()) reloadDrawer();
    refreshNav();
  },
  quick(action, job) { return quickAction(action, job, ctx); },
  async loadProfile() {
    const data = await get('/api/profile');
    ctx.profile = data.profile;
    return data;
  },
  loadMeta() {
    if (!ctx.metaRequest) ctx.metaRequest = get('/api/meta').then(meta => (ctx.meta = meta)).catch(error => {
      ctx.metaRequest = null;
      throw error;
    });
    return ctx.metaRequest;
  },
};

const current = {name: null, key: null, view: null};

function viewKey(r) {
  const params = {...r.params};
  delete params.job;
  return `${r.path[0]}|${r.path.slice(1).join('/')}`;
}

async function route() {
  const r = parseHash(location.hash);
  ctx.route = r;
  const name = VIEWS[r.path[0]] ? r.path[0] : 'overview';
  const key = viewKey(r);
  hideTooltip();

  document.querySelectorAll('[data-nav]').forEach(a => {
    const active = a.dataset.nav === name;
    a.classList.toggle('active', active);
    if (active) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  });
  document.title = `${TITLES[name]} · Jobwatch`;

  if (key !== current.key) {
    // A fresh container per render: views attach delegated listeners to their
    // root, and reusing one element would stack listeners across navigations.
    const root = document.createElement('div');
    document.getElementById('view').replaceChildren(root);
    const active = await mountView(current, {key, name, root, render: root => VIEWS[name].render(root, ctx), onError: err => {
      console.error(err);
      root.innerHTML = errorState(err);
      root.querySelector('[data-action=retry]')?.addEventListener('click', () => { current.key = null; route(); });
    }});
    if (!active) return;
    // URL filters may have changed while this tab's first request was pending.
    current.view?.update?.(ctx.route.params);
    current.view?.status?.(ctx.status);
    window.scrollTo(0, 0);
  } else {
    current.view?.update?.(r.params);
  }

  if (r.params.job) {
    if (drawerJob()?.key !== r.params.job) openDrawer(r.params.job, ctx);
  } else if (drawerOpen()) {
    closeDrawer();
  }
}

// ---------------------------------------------------------------- theme & density
function effectiveTheme() {
  const saved = store.get('jw-theme');
  if (saved === 'light' || saved === 'dark') return saved;
  return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function applyTheme() {
  const saved = store.get('jw-theme');
  if (saved) document.documentElement.dataset.theme = saved; else delete document.documentElement.dataset.theme;
  const btn = document.getElementById('theme-toggle');
  btn.innerHTML = icon(effectiveTheme() === 'dark' ? 'sun' : 'moon', 15);
  btn.title = effectiveTheme() === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
}

export function toggleTheme() {
  store.set('jw-theme', effectiveTheme() === 'dark' ? 'light' : 'dark');
  applyTheme();
  current.view?.redraw?.();
}

export function setDensity(value) {
  store.set('jw-density', value);
  document.documentElement.dataset.density = value;
}

// ---------------------------------------------------------------- status & nav counts
async function refreshNav() {
  try {
    // Count what Opportunities shows by default: the profile's interests.
    await Promise.all([ctx.profile || ctx.loadProfile().catch(() => null), ctx.meta || ctx.loadMeta().catch(() => null)]);
    const families = opportunities.interestsFromTargets(ctx.profile?.target_roles || [], (ctx.meta?.taxonomy || []).map(c => c.key));
    const [jobs, apps] = await Promise.all([
      get('/api/jobs', {...(families.length ? {family: families.join(',')} : {}), per_page: 1, facets: 0}),
      get('/api/applications'),
    ]);
    document.getElementById('nav-opps').textContent = compact(jobs.total);
    const active = apps.applications.filter(a => !['rejected', 'withdrawn', 'archived'].includes(a.status)).length;
    document.getElementById('nav-apps').textContent = active ? String(active) : '';
  } catch { /* server offline — status dot shows it */ }
}

let lastPollSeen = null;
let statusInFlight = false;
let lastCollectionRefresh = 0;
let collectionRefresh = false;
let collectionDirty = false;
const COLLECTION_VIEWS = new Set(['overview', 'opportunities', 'companies', 'analytics', 'sources']);
async function refreshCollectionView() {
  if (collectionRefresh || !COLLECTION_VIEWS.has(current.name) || !current.view?.refresh || isTyping({target: document.activeElement})) return;
  collectionRefresh = true;
  collectionDirty = false;
  lastCollectionRefresh = Date.now();
  try { await current.view.refresh(); } catch { /* The view owns its error state. */ }
  finally { collectionRefresh = false; }
}

async function refreshStatus() {
  if (statusInFlight) return;
  statusInFlight = true;
  const dot = document.getElementById('live-dot');
  const btn = document.getElementById('poll-now');
  try {
    const s = await get('/api/status');
    if (!ctx.meta && !ctx.metaRequest) loadMetadata();
    const previous = ctx.status;
    ctx.status = s;
    const statusError = s.error || s.progress?.error;
    const busy = s.poll_running || s.indexing || s.pending > 0;
    const panel = document.getElementById('collection-status');
    const markup = collectionMarkup(s);
    // Keep the live region quiet when the status has not changed.
    if (panel.innerHTML !== markup) panel.innerHTML = markup;
    panel.hidden = !markup;
    panel.classList.toggle('collection-error', Boolean(statusError));
    current.view?.status?.(s);
    dot.className = `live-dot ${statusError ? 'warn' : busy ? 'busy' : 'ok'}`;
    btn.title = statusError ? `Last error: ${statusError}` : s.poll_running ? 'Polling sources…'
      : s.pending > 0 ? `Indexing ${s.pending} jobs…` : `Live · last refresh ${s.last_refresh ? new Date(s.last_refresh).toLocaleTimeString() : 'pending'} · click to poll now`;
    if (s.last_poll && lastPollSeen && s.last_poll !== lastPollSeen) {
      toast('New poll finished', {action: {label: 'Refresh', fn: () => ctx.changed()}});
    }
    lastPollSeen = s.last_poll || lastPollSeen;
    const finished = previous && ((previous.poll_running && !s.poll_running) || (previous.indexing && !s.indexing) || previous.last_refresh !== s.last_refresh);
    if (finished) collectionDirty = true;
    // Background view refreshes are throttled: re-querying every few seconds
    // while collection runs made the page re-render and dim repeatedly.
    const since = Date.now() - lastCollectionRefresh;
    if ((collectionDirty && since > 10000) || (busy && since > 30000)) refreshCollectionView();
  } catch {
    dot.className = 'live-dot warn';
    btn.title = 'Dashboard server unreachable';
    const panel = document.getElementById('collection-status');
    panel.innerHTML = collectionMarkup({error: 'Connection lost. If Jobwatch was stopped, open Jobwatch again; reconnecting automatically.'});
    panel.hidden = false;
    panel.classList.add('collection-error');
  } finally {
    statusInFlight = false;
  }
}

// Update banners. The app downloads and verifies updates by itself; the banner
// appears once one is ready. "Later" hides it until an even newer release.
function notice(id, heading, body, actions) {
  document.getElementById(id)?.remove();
  const banner = document.createElement('section');
  banner.id = id;
  banner.className = 'collection-status';
  banner.setAttribute('role', 'status');
  banner.innerHTML = `<div class="collection-heading"><strong>${heading}</strong><div class="update-actions">${actions}</div></div><p>${body}</p>`;
  document.getElementById('main').prepend(banner);
  return banner;
}

async function checkForUpdate() {
  let info;
  try { info = await get('/api/update'); } catch { return; }
  showOldCopy(info.old_copy);
  const id = 'update-banner';
  const shown = document.getElementById(id);
  const failed = info.state === 'failed' && info.latest && info.url;
  if (!(info.available || failed) || store.get('jw-update-dismissed') === info.latest) { shown?.remove(); return; }
  const kind = info.state === 'ready' ? 'ready' : 'manual';
  if (shown?.dataset.kind === kind && shown.dataset.version === info.latest) return;
  const later = '<button type="button" class="btn xs" data-dismiss>Later</button>';
  const banner = kind === 'ready'
    ? notice(id, `Jobwatch ${esc(info.latest)} is ready`,
      `You have ${esc(info.current)}. Restarting takes about a minute; your data and settings are kept and this page reconnects by itself.`,
      `<button type="button" class="btn primary xs" data-apply>Restart to update</button>${later}`)
    : notice(id, `Jobwatch ${esc(info.latest)} is available`,
      `${failed ? `It could not be downloaded automatically (${esc(info.error || 'unknown error')}). ` : `You have ${esc(info.current)}. `}<a class="link" href="${esc(info.url)}" target="_blank" rel="noopener noreferrer">Download Jobwatch-Setup</a> and run it. Your data and settings are kept.`,
      later);
  banner.dataset.kind = kind;
  banner.dataset.version = info.latest;
  banner.querySelector('[data-dismiss]').addEventListener('click', () => {
    store.set('jw-update-dismissed', info.latest);
    banner.remove();
  });
  banner.querySelector('[data-apply]')?.addEventListener('click', async e => {
    const btn = e.currentTarget;
    btn.disabled = true;
    btn.textContent = 'Restarting…';
    try {
      await post('/api/update/apply', {});
    } catch (err) {
      toast(err.message, {error: true, timeout: 9000});
      btn.disabled = false;
      btn.textContent = 'Restart to update';
      return;
    }
    waitForUpdate(info.latest);
  });
}

// The installer replaces Jobwatch and starts it again on the same address.
function waitForUpdate(version) {
  ctx.stop?.();
  const overlay = document.createElement('div');
  overlay.className = 'update-overlay';
  overlay.setAttribute('role', 'alertdialog');
  overlay.setAttribute('aria-live', 'assertive');
  overlay.innerHTML = `<div class="panel panel-body"><h2>Updating Jobwatch to ${esc(version)}…</h2>
    <p class="muted" data-msg>This takes about a minute. This page reloads by itself when the new version is running.</p></div>`;
  document.body.append(overlay);
  const started = Date.now();
  const tick = async () => {
    try {
      const res = await fetch('/api/status', {cache: 'no-store'});
      if (res.ok && (await res.json()).version === version) { location.reload(); return; }
    } catch { /* restarting */ }
    if (Date.now() - started > 3 * 60 * 1000) {
      overlay.querySelector('[data-msg]').textContent = 'The update is taking longer than expected. If Jobwatch does not come back, open it from the Start menu; the installer log is in your Jobwatch data folder under updates\\install.log.';
    }
    setTimeout(tick, 2000);
  };
  setTimeout(tick, 3000);
}

function showOldCopy(folder) {
  const id = 'old-copy-banner';
  if (!folder) { document.getElementById(id)?.remove(); return; }
  if (document.getElementById(id)) return;
  const banner = notice(id, 'Jobwatch is now installed',
    `The copy you used before, in <b>${esc(folder)}</b>, is no longer needed. You can delete that folder; your data is not stored there. Open Jobwatch from the Start menu from now on.`,
    '<button type="button" class="btn xs" data-dismiss>Got it</button>');
  banner.querySelector('[data-dismiss]').addEventListener('click', async () => {
    banner.remove();
    try { await post('/api/update/old-copy/dismiss', {}); } catch { /* shown again next time */ }
  });
}

async function pollNow() {
  try {
    const r = await post('/api/refresh', {poll: true});
    toast(r.started ? 'Polling all sources — this takes a minute or two' : (r.message || 'A poll is already running'));
    refreshStatus();
  } catch (err) { toast(err.message, {error: true}); }
}

// ---------------------------------------------------------------- keys
function isTyping(e) {
  const t = e.target;
  return t && (t.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName));
}

let gPending = 0;
const G_MAP = {o: 'opportunities', a: 'applications', h: 'overview', c: 'companies', l: 'calendar', n: 'analytics', s: 'sources', ',': 'settings'};

function onKey(e) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); openPalette(ctx); return; }
  if (modalOpen() || paletteOpen()) return;
  if (e.key === 'Escape') {
    if (isTyping(e)) { e.target.blur(); return; }
    if (drawerOpen()) { ctx.closeJob(); return; }
  }
  if (isTyping(e) || e.ctrlKey || e.metaKey || e.altKey) return;

  if (gPending && Date.now() - gPending < 1200) {
    gPending = 0;
    if (G_MAP[e.key]) { e.preventDefault(); ctx.navigate([G_MAP[e.key]]); }
    return;
  }
  if (e.key === 'g') { gPending = Date.now(); return; }
  if (e.key === '?') { e.preventDefault(); openHelp(); return; }
  if (e.key === '/') {
    e.preventDefault();
    const box = document.querySelector('[data-search]');
    if (box) { box.focus(); box.select?.(); } else openPalette(ctx);
    return;
  }
  // Drawer-scoped actions take precedence over the list behind it.
  if (drawerOpen() && drawerJob() && ['s', 'a', 'o'].includes(e.key)) {
    e.preventDefault();
    quickAction({s: 'save', a: 'applied', o: 'open'}[e.key], drawerJob(), ctx);
    return;
  }
  current.view?.onKey?.(e);
}

// ---------------------------------------------------------------- boot
function loadMetadata() {
  ctx.loadMeta().then(() => {
    if (current.name === 'opportunities') collectionDirty = true;
  }).catch(() => {}); // Retry metadata on a later status tick; never gate navigation.
}

async function boot() {
  applyTheme();
  document.documentElement.dataset.density = store.get('jw-density', 'comfortable');
  const isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
  document.getElementById('cmdk-kbd').textContent = isMac ? '⌘K' : 'Ctrl K';
  document.getElementById('theme-toggle').addEventListener('click', toggleTheme);
  document.getElementById('poll-now').addEventListener('click', pollNow);
  document.getElementById('cmdk-open').addEventListener('click', () => openPalette(ctx));
  matchMedia('(prefers-color-scheme: dark)').addEventListener?.('change', () => { applyTheme(); current.view?.redraw?.(); });
  window.addEventListener('hashchange', route);
  document.addEventListener('keydown', onKey);
  ctx.applyTheme = () => { applyTheme(); current.view?.redraw?.(); };
  initPalette(ctx, {toggleTheme, pollNow, setDensity});
  if (store.get('jw-hints') === 'off') document.getElementById('hint-bar').hidden = true;

  // Each tab paints its loading/empty state immediately. Metadata and profile
  // requests must not gate the entire application shell.
  route();
  loadMetadata();
  refreshNav();
  refreshStatus();
  const timers = [setInterval(refreshStatus, 2000), setInterval(refreshNav, 120000)];
  checkForUpdate();
  timers.push(setInterval(checkForUpdate, 10 * 60 * 1000));      // cheap: the server checks GitHub itself
  // The server was stopped from Settings: nothing may poll a page that no longer exists.
  ctx.stop = () => {
    timers.forEach(clearInterval);
    current.view?.cleanup?.();
    current.view = null;
    window.removeEventListener('hashchange', route);
    document.removeEventListener('keydown', onKey);
  };
}

export const ready = boot();
