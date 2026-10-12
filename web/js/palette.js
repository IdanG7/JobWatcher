// Cmd/Ctrl+K command palette (navigation, actions, saved views, live job and
// company search) and the keyboard-shortcut help sheet.
import {get} from './api.js';
import {debounce, esc} from './lib.js';
import {contactForm, eventForm} from './forms.js';
import {icon, openModal} from './ui.js';

let open = false;
let actions = {};
export function paletteOpen() { return open; }

export function initPalette(ctx, fns) { actions = fns; }

function baseCommands(ctx) {
  const nav = (label, path, params = {}, ic = 'arrowRight', hint = '') => ({group: 'Go to', label, icon: ic, hint, run: () => ctx.navigate(path, params)});
  return [
    nav('Overview', ['overview'], {}, 'pulse', 'g h'),
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
    {group: 'Actions', label: 'Keyboard shortcuts', icon: 'command', hint: '?', run: () => openHelp()},
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

export function openPalette(ctx) {
  if (open) return;
  open = true;
  const root = document.getElementById('palette-root');
  root.innerHTML = `<div class="scrim show"></div><div class="palette" role="dialog" aria-modal="true" aria-label="Command palette">
    <div class="palette-box"><input type="text" placeholder="Search jobs, companies, commands…" aria-label="Search" autocomplete="off" spellcheck="false">
    <div class="palette-list" role="listbox"></div>
    <div class="palette-foot"><span><kbd>↑</kbd><kbd>↓</kbd> navigate</span><span><kbd>Enter</kbd> open</span><span><kbd>Esc</kbd> close</span></div></div></div>`;
  const input = root.querySelector('input');
  const list = root.querySelector('.palette-list');
  const commands = baseCommands(ctx);
  let saved = [];
  let remote = [];
  let items = [];
  let active = 0;
  let seq = 0;

  get('/api/saved-searches').then(d => {
    saved = d.saved_searches.map(s => ({group: 'Saved views', label: s.name, icon: 'bookmark',
      hint: s.new_since_visit ? `${s.new_since_visit} new` : `${s.total}`,
      run: () => ctx.navigate(['opportunities'], {...s.query, saved: s.id})}));
    draw();
  }).catch(() => {});

  const close = () => {
    open = false;
    root.innerHTML = '';
    document.removeEventListener('keydown', onKey, true);
  };

  function draw() {
    const q = input.value.trim().toLowerCase();
    const local = [...saved, ...commands].map(c => ({...c, s: score(c.label, q)})).filter(c => c.s > 0)
      .sort((a, b) => b.s - a.s).slice(0, q ? 8 : 40);
    items = q ? [...remote, ...local] : local;
    if (active >= items.length) active = Math.max(0, items.length - 1);
    let lastGroup = '';
    list.innerHTML = items.length ? items.map((c, i) => {
      const head = c.group !== lastGroup ? `<div class="palette-group">${esc(c.group)}</div>` : '';
      lastGroup = c.group;
      return `${head}<div class="palette-item${i === active ? ' active' : ''}" role="option" data-i="${i}" aria-selected="${i === active}">${c.html || `${icon(c.icon || 'arrowRight')}<span>${esc(c.label)}</span>`}${c.hint ? `<span class="hint">${esc(c.hint)}</span>` : ''}</div>`;
    }).join('') : '<div class="empty" style="padding:24px"><p>No matches</p></div>';
    list.querySelector('.palette-item.active')?.scrollIntoView({block: 'nearest'});
  }

  const search = debounce(async q => {
    const mine = ++seq;
    if (q.length < 2) { remote = []; draw(); return; }
    try {
      const [jobs, comps] = await Promise.all([
        get('/api/jobs', {q, per_page: 6, facets: 0}),
        get('/api/companies', {q, finance: 0}),
      ]);
      if (mine !== seq) return;
      remote = [
        ...comps.companies.slice(0, 3).map(c => ({group: 'Companies', label: c.name, icon: 'building',
          hint: `${c.active} open`, run: () => ctx.navigate(['companies', c.company_key])})),
        ...jobs.jobs.map(j => ({group: 'Jobs', label: `${j.company} ${j.title}`,
          html: `${icon('list')}<span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"><b>${esc(j.company || '')}</b> · ${esc(j.title)}</span>`,
          hint: j.fit !== null ? `Fit ${j.fit}` : '', run: () => ctx.openJob(j.key)})),
      ];
      active = 0;
      draw();
    } catch { /* offline */ }
  }, 160);

  function run(i) {
    const item = items[i];
    if (!item) return;
    close();
    item.run();
  }

  function onKey(e) {
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); active = Math.min(items.length - 1, active + 1); draw(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); active = Math.max(0, active - 1); draw(); }
    else if (e.key === 'Enter') { e.preventDefault(); run(active); }
  }

  document.addEventListener('keydown', onKey, true);
  input.addEventListener('input', () => { active = 0; draw(); search(input.value.trim()); });
  list.addEventListener('mousemove', e => {
    const el = e.target.closest('.palette-item');
    if (el && Number(el.dataset.i) !== active) { active = Number(el.dataset.i); draw(); }
  });
  list.addEventListener('click', e => { const el = e.target.closest('.palette-item'); if (el) run(Number(el.dataset.i)); });
  root.querySelector('.palette').addEventListener('mousedown', e => { if (e.target.classList.contains('palette')) close(); });
  draw();
  input.focus();
}

export function openHelp() {
  const rows = [
    ['Ctrl/⌘ K', 'Command palette'], ['/', 'Focus search'], ['j / k', 'Next / previous row'],
    ['Enter', 'Open job details'], ['s', 'Save job'], ['a', 'Mark applied'], ['o', 'Open original posting'],
    ['f', 'Toggle filters'], ['Esc', 'Close drawer / blur input'], ['g o', 'Go to opportunities'],
    ['g a', 'Go to applications'], ['g h', 'Go to overview'], ['g c', 'Go to companies'], ['g l', 'Go to calendar'],
    ['g n', 'Go to analytics'], ['g s', 'Go to sources'], ['?', 'This help'],
  ];
  openModal({title: 'Keyboard shortcuts', submitLabel: '', cancelLabel: 'Close',
    body: `<dl class="kv" style="grid-template-columns:120px 1fr">${rows.map(([k, v]) => `<dt>${k.split(' ').map(x => `<kbd>${esc(x)}</kbd>`).join(' ')}</dt><dd>${esc(v)}</dd>`).join('')}</dl>`});
}
