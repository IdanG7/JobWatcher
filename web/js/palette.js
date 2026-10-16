// Cmd/Ctrl+K command palette (navigation, actions, saved views, live job and
// company search) and the keyboard-shortcut help sheet.
import {get} from './api.js';
import {debounce, esc} from './lib.js';
import {contactForm, eventForm} from './forms.js';
import {icon, modKey, openModal} from './ui.js';

let open = false;
let actions = {};
export function paletteOpen() { return open; }

export function initPalette(ctx, fns) { actions = fns; }

// What Enter does for the highlighted row, shown in the footer (Raycast's action bar).
const VERBS = {'Go to': 'Go to page', Views: 'Show view', 'Saved views': 'Open view', Actions: 'Run command',
  Companies: 'Open company', Postings: 'Open posting'};

function baseCommands(ctx) {
  const nav = (label, path, params = {}, ic = 'arrowRight', keys = '') => ({group: 'Go to', label, icon: ic, keys, run: () => ctx.navigate(path, params)});
  return [
    nav('Today', ['overview'], {}, 'pulse', 'g h'),
    nav('Opportunities', ['opportunities'], {}, 'list', 'g o'),
    nav('Applications', ['applications'], {}, 'kanban', 'g a'),
    nav('Companies', ['companies'], {}, 'building', 'g c'),
    nav('Recruiting calendar', ['calendar'], {}, 'calendar', 'g l'),
    nav('Analytics', ['analytics'], {}, 'chart', 'g n'),
    nav('Sources', ['sources'], {}, 'refresh', 'g s'),
    nav('Settings & profile', ['settings'], {}, 'settings', 'g ,'),
    nav('Networking contacts', ['applications'], {tab: 'contacts'}, 'users'),
    {group: 'Views', label: 'High fit roles', icon: 'filter', run: () => ctx.navigate(['opportunities'], {min_fit: 75})},
    {group: 'Views', label: 'Posted today', icon: 'filter', run: () => ctx.navigate(['opportunities'], {posted: 'today', sort: 'newest'})},
    {group: 'Views', label: 'Closing within 7 days', icon: 'filter', run: () => ctx.navigate(['opportunities'], {deadline: '7d', sort: 'deadline'})},
    {group: 'Views', label: 'Investment banking', icon: 'filter', run: () => ctx.navigate(['opportunities'], {category: 'investment_banking'})},
    {group: 'Views', label: '2027 internships', icon: 'filter', run: () => ctx.navigate(['opportunities'], {cycle: '2027', stage: 'internship'})},
    {group: 'Views', label: 'Watchlist companies', icon: 'star', run: () => ctx.navigate(['opportunities'], {watchlist: 1})},
    {group: 'Actions', label: 'Poll all sources now', icon: 'refresh', run: () => actions.pollNow?.()},
    {group: 'Actions', label: 'Toggle light / dark theme', icon: 'moon', run: () => actions.toggleTheme?.()},
    {group: 'Actions', label: 'Compact table density', icon: 'rows', run: () => actions.setDensity?.('compact')},
    {group: 'Actions', label: 'Comfortable table density', icon: 'rows', run: () => actions.setDensity?.('comfortable')},
    {group: 'Actions', label: 'Add networking contact', icon: 'user', run: () => contactForm({}, ctx).then(r => r && ctx.changed())},
    {group: 'Actions', label: 'Add calendar event', icon: 'calendar', run: () => eventForm().then(r => r && ctx.changed())},
    {group: 'Actions', label: 'Export current filters to CSV', icon: 'download', run: () => {
      const params = ctx.route.path[0] === 'opportunities' ? {...ctx.route.params} : {};
      delete params.job; delete params.page;
      window.location.href = `/api/export.csv?${new URLSearchParams(params)}`;
    }},
    {group: 'Actions', label: 'Keyboard shortcuts', icon: 'command', keys: '?', run: () => openHelp()},
  ];
}

function score(label, q) {
  const l = label.toLowerCase();
  if (!q) return 1;
  if (l.startsWith(q)) return 3;
  if (l.includes(q)) return 2;
  // subsequence match ("opp" -> "Opportunities", "ib" -> "investment banking")
  let i = 0;
  for (const ch of l) if (ch === q[i]) i++;
  return i === q.length ? 1 : 0;
}

/** Shortcut notation → keycaps: "g h" is a sequence, "j/k" alternatives, "mod+K" a chord. */
export function keycaps(spec) {
  const cap = k => `<kbd>${esc(k === 'mod' ? modKey() : k)}</kbd>`;
  const parts = (text, sep) => (text.length > 1 ? text.split(sep) : [text]);   // a lone "/" or "+" is the key itself
  return spec.split(' ').map(step => parts(step, '/').map(alt => parts(alt, '+').map(cap).join('')).join('<span class="kc-or">/</span>'))
    .join('<span class="kc-then">then</span>');
}

export function openPalette(ctx) {
  if (open) return;
  open = true;
  const root = document.getElementById('palette-root');
  // No open/close animation: the palette is summoned many times a day and must feel instant.
  root.innerHTML = `<div class="scrim show"></div><div class="palette" role="dialog" aria-modal="true" aria-label="Command palette">
    <div class="palette-box">
      <div class="palette-input">${icon('search', 16)}<input type="text" placeholder="Search postings, companies and commands…" aria-label="Search postings, companies and commands" role="combobox" aria-expanded="true" aria-controls="palette-list" aria-autocomplete="list" autocomplete="off" spellcheck="false"><kbd>esc</kbd></div>
      <div class="palette-list" id="palette-list" role="listbox" aria-label="Results"></div>
      <div class="palette-foot"><span class="pf-action" data-pf-action></span><span class="pf-keys"><kbd>↑</kbd><kbd>↓</kbd> move</span></div>
    </div></div>`;
  const input = root.querySelector('input');
  const list = root.querySelector('.palette-list');
  const foot = root.querySelector('[data-pf-action]');
  const commands = baseCommands(ctx);
  let saved = [];
  let remote = [];
  let items = [];
  let active = 0;
  let seq = 0;
  let searching = false;

  get('/api/saved-searches').then(d => {
    if (!open) return;
    saved = d.saved_searches.map(s => ({group: 'Saved views', label: s.name, icon: 'bookmark',
      hint: s.new_since_visit ? `${s.new_since_visit} new` : `${s.total ?? ''}`, hintClass: s.new_since_visit ? 'new' : 'num',
      run: () => ctx.navigate(['opportunities'], {...s.query, saved: s.id})}));
    draw();
  }).catch(() => {});

  const close = () => {
    open = false;
    root.innerHTML = '';
    document.removeEventListener('keydown', onKey, true);
  };

  function setActive(i, scroll = true) {
    if (!items.length) { foot.innerHTML = ''; input.removeAttribute('aria-activedescendant'); return; }
    active = Math.max(0, Math.min(items.length - 1, i));
    list.querySelectorAll('.palette-item').forEach(el => {
      const on = Number(el.dataset.i) === active;
      el.classList.toggle('active', on);
      el.setAttribute('aria-selected', String(on));
    });
    input.setAttribute('aria-activedescendant', `pal-${active}`);
    foot.innerHTML = `${esc(VERBS[items[active].group] || 'Open')}<kbd>↵</kbd>`;
    if (scroll) list.querySelector('.palette-item.active')?.scrollIntoView({block: 'nearest'});
  }

  function draw() {
    const q = input.value.trim().toLowerCase();
    const local = [...saved, ...commands].map(c => ({...c, s: score(c.label, q)})).filter(c => c.s > 0)
      .sort((a, b) => b.s - a.s).slice(0, q ? 8 : 40);
    items = q ? [...remote, ...local] : local;
    let lastGroup = '';
    const rows = items.map((c, i) => {
      const head = c.group !== lastGroup ? `<div class="palette-group" role="presentation">${esc(c.group)}</div>` : '';
      lastGroup = c.group;
      const right = c.keys ? `<span class="hint keys">${keycaps(c.keys)}</span>` : c.hint ? `<span class="hint ${c.hintClass || ''}">${esc(c.hint)}</span>` : '';
      return `${head}<div class="palette-item" id="pal-${i}" role="option" data-i="${i}" aria-selected="false">${c.html || `${icon(c.icon || 'arrowRight')}<span class="label">${esc(c.label)}</span>`}${right}</div>`;
    }).join('');
    const status = searching && q.length >= 2 ? '<div class="palette-status">Searching postings and companies…</div>' : '';
    list.innerHTML = rows || status ? rows + status
      : `<div class="palette-empty"><strong>No results for “${esc(input.value.trim())}”</strong><span>Try a company, a role title or a command.</span></div>`;
    setActive(active);
  }

  const search = debounce(async q => {
    const mine = ++seq;
    if (q.length < 2) { remote = []; searching = false; draw(); return; }
    // Either search may fail (offline, older server); show whatever came back.
    const [jobs, comps] = await Promise.allSettled([
      get('/api/jobs', {q, per_page: 6, facets: 0}),
      get('/api/companies', {q, finance: 0}),
    ]);
    if (mine !== seq || !open) return;
    remote = [
      ...(comps.value?.companies || []).slice(0, 3).map(c => ({group: 'Companies', label: c.name, icon: 'building',
        hint: `${c.active} open`, run: () => ctx.navigate(['companies', c.company_key])})),
      ...(jobs.value?.jobs || []).map(j => ({group: 'Postings', label: `${j.company} ${j.title}`,
        html: `${icon('list')}<span class="label"><b>${esc(j.company || '')}</b><span class="sep">·</span>${esc(j.title)}</span>`,
        hint: j.fit !== null && j.fit !== undefined ? `${j.fit}` : '', hintClass: `num fit-hint${j.fit >= 85 ? ' high' : ''}`, run: () => ctx.openJob(j.key)})),
    ];
    active = 0;
    searching = false;
    draw();
  }, 160);

  function run(i) {
    const item = items[i];
    if (!item) return;
    close();
    item.run();
  }

  function onKey(e) {
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); setActive(active + 1 >= items.length ? 0 : active + 1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(active - 1 < 0 ? items.length - 1 : active - 1); }
    else if (e.key === 'Enter') { e.preventDefault(); run(active); }
    else if (e.key === 'Tab') e.preventDefault();   // the input is the only stop inside the palette
  }

  document.addEventListener('keydown', onKey, true);
  input.addEventListener('input', () => {
    active = 0;
    searching = input.value.trim().length >= 2;
    draw();
    search(input.value.trim());
  });
  list.addEventListener('mousemove', e => {
    const el = e.target.closest('.palette-item');
    if (el && Number(el.dataset.i) !== active) setActive(Number(el.dataset.i), false);
  });
  list.addEventListener('mousedown', e => e.preventDefault());   // keep focus in the input
  list.addEventListener('click', e => { const el = e.target.closest('.palette-item'); if (el) run(Number(el.dataset.i)); });
  root.querySelector('.palette').addEventListener('mousedown', e => { if (e.target.classList.contains('palette')) close(); });
  draw();
  input.focus();
}

const SHORTCUTS = [
  ['General', [['mod+K', 'Command palette'], ['/', 'Focus search'], ['?', 'Keyboard shortcuts'], ['Esc', 'Close the posting, or leave a field']]],
  ['Lists', [['j/k', 'Next / previous row'], ['Enter', 'Open the posting'], ['f', 'Toggle filters']]],
  ['Posting', [['s', 'Save to your tracker'], ['a', 'Mark applied'], ['o', 'Open the original posting']]],
  ['Calendar', [['t', 'Jump to today'], ['←/→', 'Previous / next'], ['m/w/l', 'Month, week or list']]],
  ['Go to', [['g h', 'Today'], ['g o', 'Opportunities'], ['g a', 'Applications'], ['g c', 'Companies'], ['g l', 'Calendar'],
    ['g n', 'Analytics'], ['g s', 'Sources'], ['g ,', 'Settings']]],
];

export function openHelp() {
  openModal({title: 'Keyboard shortcuts', submitLabel: '', cancelLabel: 'Close', wide: true,
    body: `<div class="shortcuts">${SHORTCUTS.map(([group, rows]) => `<section><h3>${esc(group)}</h3><dl>${rows.map(([keys, label]) =>
      `<div class="sc-row"><dt>${esc(label)}</dt><dd>${keycaps(keys)}</dd></div>`).join('')}</dl></section>`).join('')}</div>`});
}
