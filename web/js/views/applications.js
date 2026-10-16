// Application CRM: kanban board (drag & drop), table, and networking contacts.
import {del, enc, get, patch} from '../api.js';
import {daysUntil, esc, fmtDay, safeUrl} from '../lib.js';
import {
  STATUS_LABELS, STATUS_ORDER, confirmDialog, deadlineCell, emptyState, errorState, fitMeter, icon, logo, options,
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
const CLOSED = ['rejected', 'withdrawn', 'archived'];
const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

export async function render(root, ctx) {
  const state = {tab: ctx.route.params.tab || 'board', apps: [], contacts: [], q: ''};
  root.innerHTML = `
  <div class="page-head">
    <div><h1>Applications</h1><p class="sub" data-summary>Your private recruiting CRM, stored only in the local database.</p></div>
    <div class="page-actions">
      <button class="btn primary" data-act="add-contact" hidden>${icon('plus')} Add contact</button>
      <a class="btn primary" data-act="find" href="#/opportunities?min_fit=70&status=untracked">${icon('search')} Find roles</a>
    </div>
  </div>
  <div class="toolbar">
    <div class="segmented" role="tablist" aria-label="View">
      <button type="button" role="tab" data-tab="board">${icon('kanban', 13)} Board</button>
      <button type="button" role="tab" data-tab="table">${icon('table', 13)} Table</button>
      <button type="button" role="tab" data-tab="contacts">${icon('users', 13)} Networking</button>
    </div>
    <label class="search toolbar-search"><span class="sr-only">Filter applications</span>${icon('search')}<input class="input" data-search type="search" placeholder="Filter by company or role" autocomplete="off"><kbd>/</kbd></label>
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
    $('[data-search]').placeholder = state.tab === 'contacts' ? 'Filter by name or company' : 'Filter by company or role';
    const active = state.apps.filter(a => !CLOSED.includes(a.status)).length;
    const due = state.contacts.filter(c => c.next_follow_up && daysUntil(c.next_follow_up) <= 0).length;
    $('[data-summary]').innerHTML = state.tab === 'contacts'
      ? `${plural(state.contacts.length, 'contact')}${due ? ` · <span class="dl-warn">${plural(due, 'follow-up')} due</span>` : ''} · private, never synced`
      : `${active} active · ${state.apps.filter(a => INTERVIEWING.includes(a.status)).length} interviewing · ${plural(state.apps.filter(a => a.status === 'offer').length, 'offer')}${ctx.route.params.status === 'interviewing' ? ' · <a class="link" href="#/applications">showing interviews only, clear</a>' : ''}`;
    if (state.tab === 'contacts') return drawContacts();
    if (!state.apps.length) {
      body.innerHTML = emptyState('No applications yet', 'Press <kbd>s</kbd> on any opportunity to save it here, then drag it across the board as you progress.', '<a class="btn primary sm" href="#/opportunities">Browse opportunities</a>');
      return;
    }
    return state.tab === 'table' ? drawTable() : drawBoard();
  }

  function card(a) {
    const closed = CLOSED.includes(a.status);
    const dl = a.deadline && !closed && a.status !== 'offer' ? a.deadline : '';
    const next = a.interview_date && INTERVIEWING.includes(a.status) ? `Interview ${fmtDay(a.interview_date.slice(0, 10))}`
      : a.next_step ? `${a.next_step}${a.next_action_date ? ` · ${fmtDay(a.next_action_date)}` : ''}` : '';
    const overdue = a.next_action_date && daysUntil(a.next_action_date) < 0;
    const meta = dl ? deadlineCell(dl) : a.applied_date ? `Applied ${fmtDay(a.applied_date)}` : esc(a.category_label || '');
    return `<article class="card" draggable="true" data-key="${esc(a.key)}" tabindex="0" aria-label="${esc(`${a.company} ${a.title}, ${a.status_label}`)}">
      <div class="card-co">${logo(a.company || '?')}<span class="card-co-name">${esc(a.company || '')}</span>${a.fit !== null && a.fit !== undefined ? fitMeter(a.fit) : ''}</div>
      <div class="t">${esc(a.title)}</div>
      ${meta || closed ? `<div class="f">${meta ? `<span>${meta}</span>` : ''}${closed ? `<span class="card-state">${esc(a.status_label)}</span>` : ''}</div>` : ''}
      ${next ? `<div class="next${overdue ? ' dl-warn' : ''}">${icon(overdue ? 'clock' : 'arrowRight', 12)}<span>${overdue ? 'Overdue · ' : ''}${esc(next)}</span></div>` : ''}
    </article>`;
  }

  function drawBoard() {
    const apps = filtered();
    body.innerHTML = `<div class="board apps-board" data-board>${BOARD.map(col => {
      const items = apps.filter(a => col.statuses.includes(a.status));
      return `<section class="col${items.length ? '' : ' is-empty'}${col.key === 'rejected' ? ' is-closed' : ''}" data-col="${col.key}" aria-label="${esc(`${col.label}, ${items.length}`)}">
        <div class="col-head">${statusPill(col.key, col.label)}<span class="n">${items.length}</span></div>
        <div class="col-body">${items.map(card).join('')}</div></section>`;
    }).join('')}</div>
    <p class="board-hint">Drag a card onto another stage to update it. Empty stages stay folded until something lands in them.</p>`;
  }

  function drawTable() {
    const apps = filtered();
    body.innerHTML = `<section class="sheet"><div class="table-wrap"><table class="data tidy apps-table">
      <thead><tr><th>Fit</th><th>Company</th><th>Role</th><th>Status</th><th>Deadline</th><th>Applied</th><th>Next step</th><th>Interview</th><th>Resume</th><th><span class="sr-only">Posting</span></th></tr></thead>
      <tbody>${apps.map(a => `<tr data-key="${esc(a.key)}">
        <td class="c-fit">${fitMeter(a.fit)}</td>
        <td class="nowrap"><div class="co">${logo(a.company || '?')}<span>${esc(a.company || '')}</span></div></td>
        <td class="c-role"><div class="role"><span class="t">${esc(a.title)}</span></div></td>
        <td><span class="status-edit st-${esc(a.status)}"><i></i><select class="status-select" data-status aria-label="Status for ${esc(a.company || '')} ${esc(a.title)}">${options(STATUS_ORDER.map(k => ({key: k, label: STATUS_LABELS[k]})), a.status)}</select>${icon('chevronDown', 12)}</span></td>
        <td class="nowrap figure">${deadlineCell(a.deadline)}</td>
        <td class="nowrap figure muted">${a.applied_date ? fmtDay(a.applied_date) : '—'}</td>
        <td class="c-next">${esc(a.next_step || '')}${a.next_action_date ? ` <span class="${daysUntil(a.next_action_date) < 0 ? 'dl-warn' : 'muted'}">· ${fmtDay(a.next_action_date)}</span>` : ''}${!a.next_step && !a.next_action_date ? '<span class="muted">—</span>' : ''}</td>
        <td class="nowrap figure">${a.interview_date ? fmtDay(a.interview_date.slice(0, 10)) : '<span class="muted">—</span>'}</td>
        <td class="muted">${esc(a.resume_version || '—')}</td>
        <td class="actions row-actions"><a class="btn ghost xs icon" href="${esc(safeUrl(a.url))}" target="_blank" rel="noopener noreferrer" title="Open posting" aria-label="Open posting">${icon('external', 13)}</a></td>
      </tr>`).join('')}</tbody></table></div>${apps.length ? '' : emptyState('No applications match', 'Try a different filter.')}</section>`;
  }

  function drawContacts() {
    const q = state.q.toLowerCase();
    const contacts = q ? state.contacts.filter(c => `${c.name} ${c.company} ${c.position}`.toLowerCase().includes(q)) : state.contacts;
    if (!state.contacts.length) {
      body.innerHTML = emptyState('No networking contacts yet', 'Track alumni, recruiters and referrals you meet. Foothold never scrapes LinkedIn: you add people yourself, and everything stays local.', '<button type="button" class="btn primary sm" data-act="add-contact">Add your first contact</button>');
      return;
    }
    body.innerHTML = `<section class="sheet"><div class="table-wrap"><table class="data tidy contacts-table">
      <thead><tr><th>Name</th><th>Company</th><th>Relationship</th><th>Last contact</th><th>Follow up</th><th>Recent</th><th><span class="sr-only">Actions</span></th></tr></thead>
      <tbody>${contacts.map(c => {
        const n = c.next_follow_up ? daysUntil(c.next_follow_up) : null;
        return `<tr data-contact="${c.id}" class="static">
        <td><div class="person"><span class="avatar" aria-hidden="true">${esc((c.name || '?').slice(0, 1).toUpperCase())}</span><div><b>${esc(c.name)}</b>${c.position ? `<small>${esc(c.position)}</small>` : ''}</div></div></td>
        <td class="nowrap">${c.company_key ? `<a class="link quiet-link" href="#/companies/${enc(c.company_key)}">${esc(c.company || c.company_key)}</a>` : esc(c.company || '—')}</td>
        <td class="nowrap dim">${esc(prettyKey(c.relationship))}</td>
        <td class="nowrap figure muted">${c.last_contacted ? fmtDay(c.last_contacted) : 'Never'}</td>
        <td class="nowrap figure ${n !== null && n <= 0 ? 'dl-warn' : ''}">${c.next_follow_up ? (n < 0 ? `Overdue · ${fmtDay(c.next_follow_up)}` : n === 0 ? 'Today' : fmtDay(c.next_follow_up)) : '<span class="muted">—</span>'}</td>
        <td class="muted c-recent">${c.log?.[0] ? `${esc(prettyKey(c.log[0].kind))}: ${esc(c.log[0].note || '')}` : esc(c.notes || '')}</td>
        <td class="actions row-actions"><button type="button" class="btn ghost xs" data-c-act="log">Log touchpoint</button><button type="button" class="btn ghost xs icon" data-c-act="edit" title="Edit contact" aria-label="Edit ${esc(c.name)}">${icon('edit', 13)}</button><button type="button" class="btn ghost xs icon danger" data-c-act="delete" title="Delete contact" aria-label="Delete ${esc(c.name)}">${icon('trash', 13)}</button></td>
      </tr>`;
      }).join('')}</tbody></table></div>${contacts.length ? '' : emptyState('No contacts match', 'Try a different filter.')}</section>`;
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
  const endDrag = () => {
    root.querySelectorAll('.col.drop').forEach(c => c.classList.remove('drop'));
    root.querySelector('[data-board]')?.classList.remove('is-dragging');
  };
  root.addEventListener('dragstart', e => {
    const c = e.target.closest?.('.card');
    if (!c) return;
    dragKey = c.dataset.key;
    c.classList.add('dragging');
    root.querySelector('[data-board]')?.classList.add('is-dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', dragKey);
  });
  root.addEventListener('dragend', e => { e.target.closest?.('.card')?.classList.remove('dragging'); endDrag(); });
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
    endDrag();
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
