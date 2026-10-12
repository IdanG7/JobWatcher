// Shared DOM components: icons, fit meters, badges, toasts, modals, tooltips.
import {deadlineText, daysUntil, esc, fitBand, initials} from './lib.js';

const ICONS = {
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  star: '<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/>',
  bookmark: '<path d="M6 3h12v18l-6-4-6 4z"/>',
  external: '<path d="M14 4h6v6M20 4 10 14M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  chevronLeft: '<path d="m15 18-6-6 6-6"/>',
  chevronRight: '<path d="m9 18 6-6-6-6"/>',
  chevronDown: '<path d="m6 9 6 6 6-6"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z"/>',
  refresh: '<path d="M20 11a8 8 0 0 0-14.9-3.9L3 9M4 13a8 8 0 0 0 14.9 3.9L21 15M3 4v5h5M21 20v-5h-5"/>',
  filter: '<path d="M3 5h18l-7 8v6l-4 2v-8z"/>',
  rows: '<path d="M3 6h18M3 12h18M3 18h18"/>',
  download: '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  kanban: '<rect x="3" y="4" width="5" height="16" rx="1"/><rect x="10" y="4" width="5" height="10" rx="1"/><rect x="17" y="4" width="4" height="13" rx="1"/>',
  table: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9 10v10"/>',
  trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2 20a7 7 0 0 1 14 0M16 4.5a3.5 3.5 0 0 1 0 7M22 20a7 7 0 0 0-4-6.3"/>',
  building: '<rect x="4" y="3" width="16" height="18" rx="1"/><path d="M9 7h2M13 7h2M9 11h2M13 11h2M9 15h2M13 15h2M10 21v-3h4v3"/>',
  bell: '<path d="M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8M10 20a2 2 0 0 0 4 0"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  pulse: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
  arrowRight: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  edit: '<path d="M4 20h4L20 8l-4-4L4 16z"/>',
  eyeOff: '<path d="M3 3l18 18M10.6 6.1A10 10 0 0 1 12 6c6 0 9.5 6 9.5 6a17 17 0 0 1-3 3.6M6.6 6.6A17 17 0 0 0 2.5 12S6 18 12 18a9.7 9.7 0 0 0 4.4-1"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
  command: '<path d="M9 6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3z"/>',
};

export function icon(name, size = 14) {
  return `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ''}</svg>`;
}

export function fitMeter(fit) {
  if (fit === null || fit === undefined) return '<span class="fit low"><b>—</b><i style="--w:0%"></i></span>';
  const band = fitBand(fit);
  return `<span class="fit ${band}" title="Fit score ${fit}/100"><b>${fit}</b><i style="--w:${Math.max(4, fit)}%"></i></span>`;
}

const BADGE_CLASS = {
  'NEW': 'new', 'TODAY': 'today', '48H': 'h48', 'DEADLINE SOON': 'deadline', 'ROLLING': 'rolling',
  'CLOSED': 'closed', 'POSSIBLY CLOSED': 'closed', 'UPDATED': 'updated',
};

const BADGE_LABELS = {'POSSIBLY CLOSED': 'May be closed', 'DEADLINE SOON': 'Closing soon', '48H': '2 days', 'CO-OP': 'Co-op'};

/** Badge codes from the API (NEW, DEADLINE SOON, 2027) as sentence-case labels. */
export function badgeLabel(text = '') {
  return BADGE_LABELS[text] || (text === text.toUpperCase() ? text.charAt(0) + text.slice(1).toLowerCase() : text);
}

export function badge(text) {
  const cls = BADGE_CLASS[text] || (/^\d{4}$/.test(text) ? 'year' : 'level');
  return `<span class="badge ${cls}">${esc(badgeLabel(text))}</span>`;
}

export function badges(list = [], max = 4) {
  return (list || []).slice(0, max).map(badge).join('');
}

export function logo(name, large = false) {
  return `<span class="logo${large ? ' lg' : ''}" aria-hidden="true">${esc(initials(name))}</span>`;
}

export function statusPill(status, label) {
  if (!status) return '<span class="muted">—</span>';
  return `<span class="status-pill st-${esc(status)}"><i></i>${esc(label || STATUS_LABELS[status] || status)}</span>`;
}

export const STATUS_LABELS = {
  discovered: 'Discovered', saved: 'Saved', preparing: 'Preparing', applied: 'Applied',
  assessment: 'OA / Assessment', phone_screen: 'Phone Screen', first_round: 'First Round',
  final_round: 'Superday / Final', offer: 'Offer', rejected: 'Rejected', withdrawn: 'Withdrawn', archived: 'Archived',
};
export const STATUS_ORDER = Object.keys(STATUS_LABELS);

export function deadlineCell(iso, windowStatus) {
  if (!iso) return windowStatus === 'rolling' ? '<span class="muted">Rolling</span>' : '<span class="muted">—</span>';
  const n = daysUntil(iso);
  const cls = n < 0 ? 'dl-closed' : n <= 7 ? 'dl-warn' : '';
  return `<span class="${cls}">${esc(deadlineText(iso))}</span>`;
}

export function locationText(job) {
  const loc = job.city_label || job.location || '';
  return loc.length > 34 ? `${loc.slice(0, 32)}…` : loc;
}

export function categoryText(job) {
  if (!job.category) return job.family ? job.family.replace(/_/g, ' ') : '';
  return job.subcategory_label && job.subcategory_label !== job.category_label
    ? `${job.category_label} · ${job.subcategory_label}` : job.category_label;
}

// ---------------------------------------------------------------- states
export function skeletonRows(n = 6) {
  return `<div class="skel-rows" aria-busy="true" aria-label="Loading">${Array.from({length: n}, (_, i) =>
    `<div class="skel-row"><div class="skel" style="height:28px"></div><div><div class="skel" style="width:${70 - (i % 3) * 12}%"></div><div class="skel" style="width:${40 + (i % 4) * 8}%;margin-top:7px;height:9px"></div></div><div class="skel"></div></div>`).join('')}</div>`;
}

export function emptyState(title, text = '', action = '') {
  return `<div class="empty"><strong>${esc(title)}</strong>${text ? `<p>${text}</p>` : ''}${action}</div>`;
}

export function errorState(err, retry = true) {
  return `<div class="empty"><strong>Something went wrong</strong><p>${esc(err?.message || String(err))}</p>${retry ? '<button class="btn sm" data-action="retry">Retry</button>' : ''}</div>`;
}

// ---------------------------------------------------------------- toasts
export function toast(message, {error = false, action = null, timeout = 4200} = {}) {
  const zone = document.getElementById('toasts');
  const el = document.createElement('div');
  el.className = `toast${error ? ' error' : ''}`;
  el.innerHTML = `<span>${esc(message)}</span>${action ? `<button type="button">${esc(action.label)}</button>` : ''}`;
  if (action) el.querySelector('button').addEventListener('click', () => { action.fn(); el.remove(); });
  zone.appendChild(el);
  setTimeout(() => el.remove(), timeout);
}

// ---------------------------------------------------------------- focus
const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type=hidden]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Keep Tab / Shift+Tab inside a dialog. Call from its keydown handler. */
export function trapFocus(container, e) {
  if (e.key !== 'Tab') return;
  const items = [...container.querySelectorAll(FOCUSABLE)].filter(n => !n.hidden && n.offsetParent !== null);
  if (!items.length) { e.preventDefault(); container.focus?.(); return; }
  const first = items[0];
  const last = items[items.length - 1];
  const inside = container.contains(document.activeElement);
  if (e.shiftKey && (document.activeElement === first || !inside)) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && (document.activeElement === last || !inside)) { e.preventDefault(); first.focus(); }
}

// ---------------------------------------------------------------- modals
let modalStack = 0;
export function modalOpen() { return modalStack > 0; }

/**
 * openModal({title, body, submitLabel, wide, danger, onMount, onSubmit}) -> Promise<result|null>
 * `body` is trusted HTML built by the caller (all user values escaped there).
 * onSubmit(form, data) may return a value (resolves) or throw (shows error, stays open).
 */
export function openModal({title, body, submitLabel = 'Save', cancelLabel = 'Cancel', wide = false, danger = false,
  onMount, onSubmit, extraFoot = ''}) {
  return new Promise(resolve => {
    const root = document.getElementById('modal-root');
    const wrap = document.createElement('div');
    wrap.innerHTML = `<div class="scrim show"></div><div class="modal-wrap" role="dialog" aria-modal="true" aria-label="${esc(title)}">
      <form class="modal${wide ? ' wide' : ''}" novalidate>
        <div class="modal-head"><h2>${esc(title)}</h2><button type="button" class="btn ghost sm icon" data-close aria-label="Close">${icon('x')}</button></div>
        <div class="modal-body">${body}<div class="callout neg" data-error hidden></div></div>
        <div class="modal-foot">${extraFoot}<span style="flex:1"></span><button type="button" class="btn" data-close>${esc(cancelLabel)}</button>${submitLabel ? `<button type="submit" class="btn ${danger ? 'danger' : 'primary'}">${esc(submitLabel)}</button>` : ''}</div>
      </form></div>`;
    root.appendChild(wrap);
    modalStack += 1;
    const previous = document.activeElement;
    const form = wrap.querySelector('form');
    const close = (value = null) => {
      modalStack -= 1;
      wrap.remove();
      document.removeEventListener('keydown', onKey, true);
      previous?.focus?.();
      resolve(value);
    };
    const onKey = e => {
      if (e.key === 'Escape') { e.stopPropagation(); e.preventDefault(); close(); }
      else if (wrap === root.lastElementChild) trapFocus(wrap.querySelector('.modal-wrap'), e);
    };
    document.addEventListener('keydown', onKey, true);
    wrap.querySelectorAll('[data-close]').forEach(b => b.addEventListener('click', () => close()));
    wrap.querySelector('.modal-wrap').addEventListener('mousedown', e => { if (e.target.classList.contains('modal-wrap')) close(); });
    form.addEventListener('submit', async e => {
      e.preventDefault();
      const data = Object.fromEntries(new FormData(form).entries());
      form.querySelectorAll('input[type=checkbox][name]').forEach(cb => { data[cb.name] = cb.checked; });
      const errorBox = form.querySelector('[data-error]');
      try {
        const result = onSubmit ? await onSubmit(form, data) : data;
        close(result === undefined ? data : result);
      } catch (err) {
        errorBox.textContent = err.message || String(err);
        errorBox.hidden = false;
      }
    });
    onMount?.(form, close);
    (form.querySelector('[autofocus]') || form.querySelector('input, select, textarea, button[type=submit]'))?.focus();
  });
}

export async function confirmDialog(message, {title = 'Are you sure?', confirmLabel = 'Delete', danger = true} = {}) {
  const result = await openModal({title, body: `<p style="margin:0">${esc(message)}</p>`, submitLabel: confirmLabel, danger,
    onSubmit: () => true});
  return result === true;
}

// ---------------------------------------------------------------- tooltip
/** Tooltip markup may carry scraped titles: keep the text and <b> emphasis only. */
export function tooltipNodes(markup) {
  const template = document.createElement('template');
  template.innerHTML = markup;              // inert: nothing in a template runs or loads
  const copy = node => {
    if (node.nodeType === Node.TEXT_NODE) return document.createTextNode(node.textContent);
    if (node.nodeType !== Node.ELEMENT_NODE) return null;
    const out = node.tagName === 'B' ? document.createElement('b') : document.createDocumentFragment();
    node.childNodes.forEach(child => { const c = copy(child); if (c) out.append(c); });
    return out;
  };
  const fragment = document.createDocumentFragment();
  template.content.childNodes.forEach(child => { const c = copy(child); if (c) fragment.append(c); });
  return fragment;
}

export function bindTooltips(root) {
  const tip = document.getElementById('tooltip');
  root.addEventListener('mousemove', e => {
    const target = e.target.closest('[data-tip]');
    if (!target || !root.contains(target)) { tip.hidden = true; return; }
    tip.replaceChildren(tooltipNodes(target.getAttribute('data-tip')));
    tip.hidden = false;
    tip.style.left = `${e.clientX}px`;
    tip.style.top = `${e.clientY}px`;
  });
  root.addEventListener('mouseleave', () => { tip.hidden = true; });
}

export function hideTooltip() {
  const tip = document.getElementById('tooltip');
  if (tip) tip.hidden = true;
}

/** Build <option> list. options: [{key,label}] or [string] */
export function options(list, selected = '', {blank = null} = {}) {
  const sel = Array.isArray(selected) ? selected : [selected];
  const head = blank !== null ? `<option value="">${esc(blank)}</option>` : '';
  return head + list.map(o => {
    const key = typeof o === 'string' ? o : o.key;
    const label = typeof o === 'string' ? o : o.label;
    return `<option value="${esc(key)}"${sel.includes(key) ? ' selected' : ''}>${esc(label)}</option>`;
  }).join('');
}

export function prettyKey(key = '') {
  return String(key).replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}
