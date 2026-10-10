// Application CRM: kanban board (drag & drop), table, and networking contacts.
import {del, enc, get, patch} from '../api.js';
import {daysUntil, esc, fmtDay, safeUrl} from '../lib.js';
import {
  STATUS_LABELS, STATUS_ORDER, confirmDialog, deadlineCell, emptyState, errorState, fitMeter, icon, options,
  prettyKey, skeletonRows, statusPill, toast,
} from '../ui.js';
import {contactForm, logTouchpoint} from '../forms.js';

const BOARD = [
  {key: 'saved', label: 'Saved', statuses: ['discovered', 'saved']},
  {key: 'preparing', label: 'Preparing', statuses: ['preparing']},
  {key: 'applied', label: 'Applied', statuses: ['applied']},
  {key: 'assessment', label: 'OA / Assessment', statuses: ['assessment']},
  {key: 'phone_screen', label: 'Phone Screen', statuses: ['phone_screen']},
  {key: 'first_round', label: 'First Round', statuses: ['first_round']},
  {key: 'final_round', label: 'Superday / Final', statuses: ['final_round']},
  {key: 'offer', label: 'Offer', statuses: ['offer']},
  {key: 'rejected', label: 'Closed out', statuses: ['rejected', 'withdrawn', 'archived']},
];
const INTERVIEWING = ['assessment', 'phone_screen', 'first_round', 'final_round'];

export async function render(root, ctx) {
  const state = {tab: ctx.route.params.tab || 'board', apps: [], contacts: [], q: ''};
  root.innerHTML = `
  <div class="page-head">
    <div><h1>Applications</h1><p class="sub" data-summary>Your private recruiting CRM — stored only in the local database.</p></div>
    <div class="page-actions">
      <label class="search"><span class="sr-only">Filter applications</span>${icon('search')}<input class="input" data-search type="search" placeholder="Filter by company or role…" style="width:240px"></label>
      <div class="segmented" role="tablist" aria-label="View">
        <button role="tab" data-tab="board">${icon('kanban')} Board</button>
        <button role="tab" data-tab="table">${icon('table')} Table</button>
        <button role="tab" data-tab="contacts">${icon('users')} Networking</button>
      </div>
      <button class="btn primary" data-act="add-contact" hidden>${icon('plus')} Add contact</button>
      <a class="btn primary" data-act="find" href="#/opportunities?family=finance&min_fit=70&status=untracked">${icon('plus')} Find roles</a>
    </div>
  </div>
  <div data-body>${skeletonRows(6)}</div>`;
  const $ = s => root.querySelector(s);
  const body = $('[data-body]');

  async function load() {
    try {
      const [apps, contacts] = await Promise.all([get('/api/applications'), get('/api/contacts')]);
      state.apps = apps.applications;
      state.contacts = contacts.contacts;
      draw();
    } catch (err) {
      body.innerHTML = errorState(err);
      body.querySelector('[data-action=retry]')?.addEventListener('click', load);
    }
  }

  function filtered() {
    const q = state.q.toLowerCase();
    let apps = state.apps;
    if (ctx.route.params.status === 'interviewing') apps = apps.filter(a => INTERVIEWING.includes(a.status));
    if (q) apps = apps.filter(a => `${a.company} ${a.title}`.toLowerCase().includes(q));
    return apps;
  }

  function draw() {
    root.querySelectorAll('[data-tab]').forEach(b => { b.classList.toggle('on', b.dataset.tab === state.tab); b.setAttribute('aria-selected', String(b.dataset.tab === state.tab)); });
    $('[data-act=add-contact]').hidden = state.tab !== 'contacts';
    $('[data-act=find]').hidden = state.tab === 'contacts';
    const active = state.apps.filter(a => !['rejected', 'withdrawn', 'archived'].includes(a.status)).length;
    const due = state.contacts.filter(c => c.next_follow_up && daysUntil(c.next_follow_up) <= 0).length;
    $('[data-summary]').innerHTML = state.tab === 'contacts'
      ? `${state.contacts.length} contacts${due ? ` · <span class="dl-warn">${due} follow-up${due === 1 ? '' : 's'} due</span>` : ''} · private, never synced`
      : `${active} active · ${state.apps.filter(a => INTERVIEWING.includes(a.status)).length} interviewing · ${state.apps.filter(a => a.status === 'offer').length} offers${ctx.route.params.status === 'interviewing' ? ' · <a class="link" href="#/applications">showing interviews only — clear</a>' : ''}`;
    if (state.tab === 'contacts') return drawContacts();
    if (!state.apps.length) {
      body.innerHTML = `<div class="panel">${emptyState('No applications yet', 'Press <kbd>s</kbd> on any opportunity to save it here, then drag it across the board as you progress.', '<a class="btn primary sm" href="#/opportunities?family=finance">Browse opportunities</a>')}</div>`;
      return;
    }
    return state.tab === 'table' ? drawTable() : drawBoard();
  }

  function card(a) {
    const dl = a.deadline && !['rejected', 'withdrawn', 'archived', 'offer'].includes(a.status) ? a.deadline : '';
    const next = a.interview_date && INTERVIEWING.includes(a.status) ? `Interview ${fmtDay(a.interview_date.slice(0, 10))}`
      : a.next_step ? `${a.next_step}${a.next_action_date ? ` · ${fmtDay(a.next_action_date)}` : ''}` : '';
    const overdue = a.next_action_date && daysUntil(a.next_action_date) < 0;
    return `<article class="card" draggable="true" data-key="${esc(a.key)}" tabindex="0" aria-label="${esc(`${a.company} ${a.title}, ${a.status_label}`)}">
      <div class="t">${esc(a.title)}</div>
      <div class="c"><span>${esc(a.company || '')}</span>${['rejected', 'withdrawn', 'archived'].includes(a.status) ? `<span class="muted">${esc(a.status_label)}</span>` : ''}</div>
      <div class="f"><span>${dl ? deadlineCell(dl) : a.applied_date ? `Applied ${fmtDay(a.applied_date)}` : esc(a.category_label || '')}</span>${a.fit !== null && a.fit !== undefined ? fitMeter(a.fit) : ''}</div>
      ${next ? `<div class="next${overdue ? ' dl-warn' : ''}">${overdue ? 'Overdue · ' : ''}${esc(next)}</div>` : ''}
    </article>`;
  }

  function drawBoard() {
    const apps = filtered();
    body.innerHTML = `<div class="board" data-board>${BOARD.map(col => {
      const items = apps.filter(a => col.statuses.includes(a.status));
      return `<section class="col" data-col="${col.key}" aria-label="${esc(col.label)}"><div class="col-head">${statusPill(col.key, col.label)}<span class="n">${items.length}</span></div>
        <div class="col-body">${items.map(card).join('') || '<div class="muted" style="font-size:12px;padding:6px 4px">Drop here</div>'}</div></section>`;
    }).join('')}</div>`;
  }

  function drawTable() {
    const apps = filtered();
    body.innerHTML = `<section class="panel" style="overflow:hidden"><div class="table-wrap"><table class="data">
      <thead><tr><th>Fit</th><th>Company</th><th>Role</th><th>Status</th><th>Deadline</th><th>Applied</th><th>Next step</th><th>Interview</th><th>Resume</th><th></th></tr></thead>
      <tbody>${apps.map(a => `<tr data-key="${esc(a.key)}">
        <td>${fitMeter(a.fit)}</td>
        <td class="nowrap"><b>${esc(a.company || '')}</b></td>
        <td><div class="role"><span class="t">${esc(a.title)}</span></div></td>
        <td><select class="select" data-status style="height:26px;font-size:12px" aria-label="Status">${options(STATUS_ORDER.map(k => ({key: k, label: STATUS_LABELS[k]})), a.status)}</select></td>
        <td class="nowrap">${deadlineCell(a.deadline)}</td>
        <td class="nowrap muted">${a.applied_date ? fmtDay(a.applied_date) : '—'}</td>
        <td>${esc(a.next_step || '')}${a.next_action_date ? ` <span class="${daysUntil(a.next_action_date) < 0 ? 'dl-warn' : 'muted'}">· ${fmtDay(a.next_action_date)}</span>` : ''}</td>
        <td class="nowrap">${a.interview_date ? fmtDay(a.interview_date.slice(0, 10)) : '<span class="muted">—</span>'}</td>
        <td class="muted">${esc(a.resume_version || '—')}</td>
        <td class="actions"><a class="btn xs icon" href="${esc(safeUrl(a.url))}" target="_blank" rel="noopener noreferrer" title="Open posting">${icon('external', 12)}</a></td>
      </tr>`).join('')}</tbody></table></div></section>`;
  }

  function drawContacts() {
    const q = state.q.toLowerCase();
    const contacts = q ? state.contacts.filter(c => `${c.name} ${c.company} ${c.position}`.toLowerCase().includes(q)) : state.contacts;
    if (!state.contacts.length) {
      body.innerHTML = `<div class="panel">${emptyState('No networking contacts yet', 'Track alumni, recruiters and referrals you meet. Jobwatch never scrapes LinkedIn — you add people yourself, and everything stays local.', '<button class="btn primary sm" data-act="add-contact">Add your first contact</button>')}</div>`;
      return;
    }
    body.innerHTML = `<section class="panel" style="overflow:hidden"><div class="table-wrap"><table class="data">
      <thead><tr><th>Name</th><th>Company</th><th>Relationship</th><th>Last contact</th><th>Follow up</th><th>Recent</th><th></th></tr></thead>
      <tbody>${contacts.map(c => {
        const n = c.next_follow_up ? daysUntil(c.next_follow_up) : null;
        return `<tr data-contact="${c.id}" style="cursor:default">
        <td><b>${esc(c.name)}</b><div class="muted" style="font-size:11.5px">${esc(c.position || '')}</div></td>
        <td>${c.company_key ? `<a class="link" href="#/companies/${enc(c.company_key)}">${esc(c.company || c.company_key)}</a>` : esc(c.company || '—')}</td>
        <td><span class="tag">${esc(prettyKey(c.relationship))}</span></td>
        <td class="nowrap muted">${c.last_contacted ? fmtDay(c.last_contacted) : 'Never'}</td>
        <td class="nowrap ${n !== null && n <= 0 ? 'dl-warn' : ''}">${c.next_follow_up ? (n < 0 ? `Overdue · ${fmtDay(c.next_follow_up)}` : n === 0 ? 'Today' : fmtDay(c.next_follow_up)) : '<span class="muted">—</span>'}</td>
        <td class="muted" style="max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${c.log?.[0] ? `${esc(prettyKey(c.log[0].kind))}: ${esc(c.log[0].note || '')}` : esc(c.notes || '')}</td>
        <td class="actions"><button class="btn xs" data-c-act="log">Log</button> <button class="btn xs icon" data-c-act="edit" title="Edit">${icon('edit', 12)}</button> <button class="btn xs icon danger" data-c-act="delete" title="Delete">${icon('trash', 12)}</button></td>
      </tr>`;
      }).join('')}</tbody></table></div></section>`;
  }

  async function move(key, status) {
    const app = state.apps.find(a => a.key === key);
    if (!app || app.status === status) return;
    const prev = app.status;
    app.status = status;                     // optimistic
    app.status_label = STATUS_LABELS[status];
    draw();
    try {
      await patch(`/api/applications/${enc(key)}`, {status});
      toast(`${app.company} → ${STATUS_LABELS[status]}`, {action: {label: 'Undo', fn: () => move(key, prev)}});
    } catch (err) {
      app.status = prev;
      app.status_label = STATUS_LABELS[prev];
      draw();
      toast(err.message, {error: true});
    }
  }

  // drag & drop
  let dragKey = null;
  root.addEventListener('dragstart', e => {
    const c = e.target.closest?.('.card');
    if (!c) return;
    dragKey = c.dataset.key;
    c.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', dragKey);
  });
  root.addEventListener('dragend', e => { e.target.closest?.('.card')?.classList.remove('dragging'); root.querySelectorAll('.col.drop').forEach(c => c.classList.remove('drop')); });
  root.addEventListener('dragover', e => {
    const col = e.target.closest?.('.col');
    if (!col || !dragKey) return;
    e.preventDefault();
    root.querySelectorAll('.col.drop').forEach(c => c !== col && c.classList.remove('drop'));
    col.classList.add('drop');
  });
  root.addEventListener('drop', e => {
    const col = e.target.closest?.('.col');
    if (!col || !dragKey) return;
    e.preventDefault();
    const target = BOARD.find(b => b.key === col.dataset.col);
    const app = state.apps.find(a => a.key === dragKey);
    if (target && app && !target.statuses.includes(app.status)) move(dragKey, target.key === 'saved' ? 'saved' : target.statuses[0]);
    dragKey = null;
  });

  root.addEventListener('click', async e => {
    const tab = e.target.closest('[data-tab]');
    if (tab) { state.tab = tab.dataset.tab; ctx.setParams({tab: state.tab === 'board' ? null : state.tab}, {replace: true}); draw(); return; }
    if (e.target.closest('[data-act=add-contact]')) { if (await contactForm({}, ctx)) load(); return; }
    const cAct = e.target.closest('[data-c-act]');
    if (cAct) {
      const c = state.contacts.find(x => String(x.id) === cAct.closest('tr').dataset.contact);
      if (cAct.dataset.cAct === 'log' && await logTouchpoint(c)) load();
      if (cAct.dataset.cAct === 'edit' && await contactForm(c, ctx)) load();
      if (cAct.dataset.cAct === 'delete' && await confirmDialog(`Delete ${c.name} and their interaction log?`)) {
        try { await del(`/api/contacts/${c.id}`); toast('Contact deleted'); load(); } catch (err) { toast(err.message, {error: true}); }
      }
      return;
    }
    if (e.target.closest('select, a, button')) return;
    const el = e.target.closest('[data-key]');
    if (el) ctx.openJob(el.dataset.key);
  });
  root.addEventListener('keydown', e => {
    const c = e.target.closest?.('.card');
    if (c && e.key === 'Enter') ctx.openJob(c.dataset.key);
  });
  root.addEventListener('change', e => {
    if (e.target.matches('[data-status]')) move(e.target.closest('tr').dataset.key, e.target.value);
  });
  $('[data-search]').addEventListener('input', e => { state.q = e.target.value.trim(); draw(); });

  await load();
  return {refresh: load, update(params) { state.tab = params.tab || 'board'; draw(); }};
}
