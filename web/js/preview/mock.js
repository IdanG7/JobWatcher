// DESIGN PREVIEW ONLY: answers the dashboard's /api calls in the browser with
// fictional sample data, so the redesigned pages run without a Jobwatch server.
// Filters follow the same rules as job_query.build_where; nothing is persisted.
import {PROFILES, buildJobs, sampleDescription} from './sample-data.js';

const realFetch = window.fetch.bind(window);
const PROFILE_KEY = 'jw-preview-profile';
const profileKey = (() => { try { return localStorage.getItem(PROFILE_KEY) || 'mixed'; } catch { return 'mixed'; } })();
const active = PROFILES[profileKey] || PROFILES.mixed;

const metaReady = realFetch('/js/preview/meta.json').then(r => r.json());
let jobs = null;
const apps = new Map();          // key -> status
const hidden = new Set();
const watched = new Set(['meridian']);
let saved = [{id: 1, name: 'Toronto internships', params: {location: 'toronto', stage: 'internship'}, created_at: '2026-10-01', new_count: 3}];

async function data() {
  const meta = await metaReady;
  if (!jobs) {
    jobs = buildJobs(meta, active.profile);
    // A couple of tracked roles so status columns and filters have something to show.
    apps.set(jobs[1].key, 'applied');
    apps.set(jobs[21].key, 'saved');
  }
  return meta;
}

const list = v => (v == null || v === '' ? [] : String(v).split(',').map(s => s.trim()).filter(Boolean));
const POSTED = {today: 24, '24h': 24, '48h': 48, '3d': 72, '7d': 168, '14d': 336, '30d': 720};

function matches(job, p) {
  const status = apps.get(job.key) || null;
  if (!p.include_hidden && hidden.has(job.key)) return false;
  if (p.resume_match === '1' && !job.eligible) return false;
  if (p.q) {
    const hay = `${job.title} ${job.company} ${job.category_label} ${job.subcategory_label || ''} ${job.location} ${job.cycle_label || ''}`.toLowerCase();
    if (!p.q.toLowerCase().split(/\s+/).every(t => hay.includes(t))) return false;
  }
  const fams = list(p.family);
  if (fams.length && !fams.some(f => (f === 'finance' ? job.is_finance : job.family === f))) return false;
  const cats = list(p.category);
  if (cats.length && !cats.some(c => {
    const [cat, sub] = c.split('.');
    return job.category === cat && (!sub || job.subcategory === sub);
  })) return false;
  const anyOf = (key, value) => !list(p[key]).length || list(p[key]).includes(value);
  if (!anyOf('company_type', job.company_type) || !anyOf('stage', job.stage) || !anyOf('company', job.company_key)) return false;
  const cycles = list(p.cycle);
  if (cycles.length && !cycles.some(c => (/^\d{4}$/.test(c) ? job.cycle_year === Number(c) : job.cycle === c))) return false;
  const locs = list(p.location);
  if (locs.length && !locs.some(l => (l === 'canada' ? job.country === 'CA' || (job.remote && job.country !== 'US')
    : l === 'us' ? job.country === 'US' : /^[A-Z]{2}$/.test(l) ? job.country === l : l === 'remote' ? job.remote : job.cities.split(' ').includes(l)))) return false;
  if (POSTED[p.posted] && job.posted_ref < Date.now() / 1000 - POSTED[p.posted] * 3600) return false;
  if (p.deadline) {
    if (p.deadline === 'rolling') return false;          // no rolling roles in the sample
    if (!job.deadline) return false;
    if (p.deadline !== 'any') {
      const days = (new Date(job.deadline) - Date.now()) / 86400000;
      if (days < -1 || days > Number(p.deadline.slice(0, -1))) return false;
    }
  }
  if (p.min_fit && job.fit < Number(p.min_fit)) return false;
  if (p.comp_min && !(job.comp_annual_max >= Number(p.comp_min))) return false;
  const statuses = list(p.status);
  if (statuses.length && !statuses.some(s => (s === 'untracked' ? !status : s === 'tracked' ? !!status
    : s === 'active' ? ['saved', 'preparing', 'applied', 'assessment', 'phone_screen', 'first_round', 'final_round', 'offer'].includes(status)
      : status === s))) return false;
  if (p.watchlist && !watched.has(job.company_key)) return false;
  return true;
}

const SORT = {
  fit: j => j.fit, newest: j => j.posted_ref, deadline: j => j.deadline || '9999', company: j => j.company.toLowerCase(),
  title: j => j.title.toLowerCase(), category: j => j.category_label, location: j => j.location, cycle: j => j.cycle_label || 'zz',
  status: j => apps.get(j.key) || 'zz', urgency: j => j.fit,
};

async function jobList(p, meta) {
  const page = Math.max(1, Number(p.page) || 1);
  const perPage = Math.min(200, Number(p.per_page) || 50);
  const rows = jobs.map(j => ({...j, app_status: apps.get(j.key) || null})).filter(j => matches(j, p));
  const key = SORT[p.sort] ? p.sort : 'fit';
  const dir = p.dir || (['fit', 'newest', 'urgency'].includes(key) ? 'desc' : 'asc');
  rows.sort((a, b) => {
    const x = SORT[key](a), y = SORT[key](b);
    return (x < y ? -1 : x > y ? 1 : 0) * (dir === 'asc' ? 1 : -1) || b.fit - a.fit;
  });
  const facet = (field, label) => {
    const counts = new Map();
    for (const j of rows) if (j[field] != null) counts.set(j[field], (counts.get(j[field]) || 0) + 1);
    return [...counts].sort((a, b) => b[1] - a[1]).map(([k, n]) => ({key: k, count: n, label: label(k)}));
  };
  const labels = {
    category: k => rows.find(j => j.category === k)?.category_label || k,
    company_type: k => (meta.company_types.find(t => t.key === k) || {}).label || k,
    cycle: k => rows.find(j => j.cycle === k)?.cycle_label || k,
    city: k => (meta.cities.find(c => c.key === k) || {}).label || k,
  };
  const unfiltered = p.resume_match === '1' ? jobs.filter(j => matches(j, {...p, resume_match: '0'})).length : rows.length;
  return {
    jobs: rows.slice((page - 1) * perPage, page * perPage), total: rows.length, page, per_page: perPage,
    pages: Math.max(1, Math.ceil(rows.length / perPage)),
    facets: p.facets === '0' ? {} : {
      category: facet('category', labels.category), company_type: facet('company_type', labels.company_type),
      stage: facet('stage', k => k), cycle: facet('cycle', labels.cycle), city: facet('city', labels.city),
    },
    resume_matching: {available: true, enabled: profileKey !== 'none', active: p.resume_match === '1' && profileKey !== 'none',
      pending: 0, targets: active.profile.target_roles, unfiltered_total: unfiltered, excluded_total: unfiltered - rows.length, pending_filtered: 0},
  };
}

function detail(job) {
  const status = apps.get(job.key) || null;
  return {
    ...job, app_status: status, watched: watched.has(job.company_key), override: hidden.has(job.key) ? {hidden: 1} : null,
    description: sampleDescription(job), description_source: 'sample listing', department: '',
    facts: {
      classification: {is_finance: !!job.is_finance, category_label: job.category_label, subcategory_label: job.subcategory_label, confidence: 0.8},
      seniority: {level_label: job.level ? job.level[0].toUpperCase() + job.level.slice(1) : '', stage: job.stage},
      cycle: {label: job.cycle_label}, location: {city_labels: [job.location], remote: job.remote},
      compensation: job.comp_annual_max ? {display: `${job.comp_currency} ${job.comp_annual_max.toLocaleString()} / year (sample)`} : {},
      eligibility: {degree: "Bachelor's (in progress)", degree_text: 'Currently pursuing a degree with graduation in 2027'},
      graduation: {years: [2027], text: 'graduation in 2027'}, skills: [], deadline: job.deadline ? {confidence: 'high', text: 'Sample deadline'} : null,
    },
    fit_detail: {reasons: ['Matches a selected interest (sample score)', 'Matches your target level'], concerns: job.eligible ? [] : ['Asks for more experience than your profile shows'], subscores: []},
    resume_match: null, sources: [{label: 'Sample source', kind: 'sample', url: job.url, first_seen: job.first_seen, canonical: true}],
    discovered_from: ['Sample source'], changes: [], contacts: [], company_meta: {},
    application: status ? {status, notes: '', next_step: '', next_action_date: '', updated_at: new Date().toISOString()} : null,
    application_events: [], posting_scan: null,
  };
}

const json = (body, status = 200) => new Response(JSON.stringify(body), {status, headers: {'Content-Type': 'application/json'}});

async function handle(url, method, body) {
  const meta = await data();
  const path = decodeURIComponent(url.pathname);
  const p = Object.fromEntries(url.searchParams);
  if (path === '/api/meta') return json(meta);
  if (path === '/api/status') return json({indexing: false, last_refresh: new Date().toISOString(), last_stats: {}, poll_running: false, last_poll: null, error: null, progress: null, version: 'preview', pending: 0});
  if (path === '/api/update') return json({current: 'preview', latest: null, state: 'idle', available: false});
  if (path === '/api/profile') return json({profile: active.profile, defaults: active.profile});
  if (path === '/api/resume') return json({resume: null, enabled: profileKey !== 'none'});
  if (path === '/api/applications' && method === 'GET') return json({applications: [...apps].map(([key, status]) => ({key, status}))});
  if (path === '/api/applications' && method === 'POST') { apps.set(body.key, body.status || 'saved'); return json({ok: true}); }
  let m = path.match(/^\/api\/applications\/(.+)$/);
  if (m && method === 'PATCH') { apps.set(m[1], body.status || apps.get(m[1]) || 'saved'); return json({ok: true}); }
  if (m && method === 'DELETE') { apps.delete(m[1]); return json({ok: true}); }
  if (path === '/api/saved-searches' && method === 'GET') return json({saved_searches: saved});
  if (path === '/api/saved-searches' && method === 'POST') {
    const item = {id: saved.length + 1, name: body.name, params: body.params, created_at: new Date().toISOString(), new_count: 0};
    saved = [...saved, item];
    return json(item);
  }
  if (path === '/api/jobs') return json(await jobList(p, meta));
  m = path.match(/^\/api\/jobs\/(.+?)\/cover-letter$/);
  if (m) return json({letter: null, ai: false, resume: false, reference: null});
  m = path.match(/^\/api\/jobs\/(.+?)\/override$/);
  if (m && method === 'PUT') { if (body.hidden) hidden.add(m[1]); else hidden.delete(m[1]); return json({ok: true}); }
  m = path.match(/^\/api\/jobs\/(.+)$/);
  if (m) {
    const job = jobs.find(j => j.key === m[1]);
    return job ? json(detail(job)) : json({error: 'Not found in the sample data'}, 404);
  }
  m = path.match(/^\/api\/companies\/(.+?)\/watch$/);
  if (m && method === 'PUT') { if (body.watched) watched.add(m[1]); else watched.delete(m[1]); return json({ok: true}); }
  if (path === '/api/events') return json({ok: true});
  return json({error: `Not available in the design preview: ${path}`}, 501);
}

window.fetch = async (input, init = {}) => {
  const url = new URL(typeof input === 'string' ? input : input.url, location.origin);
  if (url.origin !== location.origin || !url.pathname.startsWith('/api/')) return realFetch(input, init);
  let body = null;
  try { body = init.body ? JSON.parse(init.body) : null; } catch { body = null; }
  await new Promise(r => setTimeout(r, 120));     // a little latency, so loading states are visible
  return handle(url, (init.method || 'GET').toUpperCase(), body);
};

// Exporting needs the real server; say so instead of navigating to a 404.
document.addEventListener('click', e => {
  if (e.target.closest?.('[data-act=export]')) {
    e.preventDefault();
    e.stopImmediatePropagation();
    import('../ui.js').then(({toast}) => toast('CSV export needs the real Jobwatch server; it is off in this preview.'));
  }
}, true);

// The preview bar: sample-data label, sample profile picker and theme.
function mountBar() {
  const bar = document.createElement('div');
  bar.className = 'preview-bar';
  bar.setAttribute('role', 'region');
  bar.setAttribute('aria-label', 'Design preview');
  bar.innerHTML = `<strong>Design preview</strong><span class="preview-note">Sample data · fictional companies, postings and fit scores</span>
    <label class="preview-pick"><span>Sample profile</span><select class="select" data-preview-profile>${Object.entries(PROFILES)
      .map(([k, v]) => `<option value="${k}"${k === profileKey ? ' selected' : ''}>${v.label}</option>`).join('')}</select></label>`;
  bar.querySelector('[data-preview-profile]').addEventListener('change', e => {
    try { localStorage.setItem(PROFILE_KEY, e.target.value); } catch { /* private mode */ }
    location.hash = '#/opportunities';
    location.reload();
  });
  document.body.prepend(bar);
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mountBar); else mountBar();
