// What's new: after an install or update, a card in the corner lists what changed, once. The
// last version the user closed is kept by the server (kv `whats_new_seen`), so the app window and
// a browser tab agree. Settings › System and the command palette open it again.
import {get, post} from './api.js';
import {esc} from './lib.js';
import {icon} from './ui.js';
import {RELEASE_NOTES} from './release-notes.js';

const MAX_RELEASES = 3;      // after skipped updates, the latest three releases at most
const SHOW_AFTER = 900;      // ms: the page paints before the card arrives
const LEAVE_MS = 180;
const MARK = '<svg class="wn-mark" viewBox="0 0 24 24" aria-hidden="true"><rect width="24" height="24" rx="5.5"/><path transform="matrix(.7778 0 0 .7778 2.15 2.15)" d="M11 4.75A1.75 1.75 0 0 1 12.75 3h6.5A1.75 1.75 0 0 1 21 4.75v14.5A1.75 1.75 0 0 1 19.25 21H4.75A1.75 1.75 0 0 1 3 19.25v-5.5A1.75 1.75 0 0 1 4.75 12h5.5a.75.75 0 0 0 .75-.75z"/></svg>';

/** "0.3.10" → [0, 3, 10]; anything unreadable sorts first. */
export function versionParts(version) {
  const parts = String(version ?? '').match(/\d+/g);
  return parts ? parts.slice(0, 3).map(Number) : [0];
}

export function compareVersions(a, b) {
  const x = versionParts(a);
  const y = versionParts(b);
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    const d = (x[i] ?? 0) - (y[i] ?? 0);
    if (d) return Math.sign(d);
  }
  return 0;
}

function releasesUpTo(current, notes) {
  return notes.filter(r => compareVersions(r.version, current) <= 0).sort((a, b) => compareVersions(b.version, a.version));
}

/**
 * The releases the card lists after an update: newer than the last one closed (`seen`), up to the
 * running version, newest first. Without `seen` (an existing install meeting this card for the
 * first time), only the running version's own notes.
 */
export function pendingReleases(current, seen, notes = RELEASE_NOTES) {
  if (seen && compareVersions(seen, current) >= 0) return [];
  const unread = seen ? r => compareVersions(r.version, seen) > 0 : r => compareVersions(r.version, current) === 0;
  return releasesUpTo(current, notes).filter(unread).slice(0, MAX_RELEASES);
}

/** Opened again on purpose: the running version's notes and the ones before it. */
export function recentReleases(current, notes = RELEASE_NOTES) {
  return releasesUpTo(current, notes).slice(0, MAX_RELEASES);
}

/** "All updates": every release older than the ones the card shows (`shown`), newest first. */
export function earlierReleases(current, shown, notes = RELEASE_NOTES) {
  const oldest = shown.at(-1)?.version ?? current;
  return releasesUpTo(current, notes).filter(r => compareVersions(r.version, oldest) < 0);
}

/** What the card shows for GET /api/whats-new, or null: nothing new, or the intro or setup is on screen. */
export function cardToShow(info, routeName = '', notes = RELEASE_NOTES) {
  if (!info?.version || routeName === 'welcome' || routeName === 'intro') return null;
  const releases = pendingReleases(info.version, info.seen, notes);
  return releases.length ? {current: info.version, seen: info.seen || null, releases} : null;
}

/**
 * The version's segments. The ones that changed since `from` roll over from their old value, and
 * every segment after the first change rolls too (0.3.9 → 0.4.0). Without `from`, the last
 * segment rolls in from blank; `from` equal to `to` rolls nothing.
 */
export function rollSegments(from, to) {
  const next = String(to).split('.');
  const prev = from ? String(from).split('.') : null;
  let rolling = false;
  return next.map((text, i) => {
    if (!prev) return {text, from: i === next.length - 1 ? '' : null};
    rolling ||= prev[i] !== text;
    return {text, from: rolling ? (prev[i] ?? '') : null};
  });
}

function releasedOn(date) {
  const day = date ? new Date(`${date}T12:00:00`) : null;
  return day && !Number.isNaN(day.getTime()) ? day.toLocaleDateString(undefined, {month: 'short', day: 'numeric', year: 'numeric'}) : '';
}

// The old value is CSS generated content with empty alt text, so the heading reads "0.3.4" to
// screen readers and in copied text.
function versionMarkup(segments) {
  return segments.map((s, i) => {
    const dot = i ? '.' : '';
    if (s.from === null) return dot + esc(s.text);
    return `${dot}<span class="wn-roll"><span class="wn-roll-col" data-from="${esc(s.from)}" style="--i:${i}">${esc(s.text)}</span></span>`;
  }).join('');
}

function itemMarkup(item, i) {
  const body = `<span class="wn-icon">${icon(item.icon, 15)}</span><span class="wn-text"><b>${esc(item.title)}</b><span>${esc(item.text)}</span></span>`;
  return `<li style="--i:${i}">${item.link
    ? `<a class="wn-item" href="${esc(item.link)}">${body}<span class="wn-go">${icon('arrowRight', 14)}</span></a>`
    : `<div class="wn-item">${body}</div>`}</li>`;
}

function releasesMarkup(releases, labelled) {
  let n = 0;      // across releases, so each item rises a beat after the one before
  return releases.map(r => {
    const date = labelled ? releasedOn(r.date) : '';
    const head = labelled ? `<h3 class="wn-release-v">${esc(r.version)}${date ? ` <time datetime="${esc(r.date)}">${esc(date)}</time>` : ''}</h3>` : '';
    return `<section class="wn-release">${head}
      <ul class="wn-items">${r.items.map(item => itemMarkup(item, n++)).join('')}</ul></section>`;
  }).join('');
}

// Folded (inert: out of the tab order and screen readers) until the row's button opens it.
function earlierMarkup(earlier) {
  if (!earlier.length) return '';
  return `<div class="wn-all"><button type="button" class="wn-more" data-wn-more aria-expanded="false" aria-controls="wn-earlier">
      <span>All updates</span><span class="wn-more-n">${earlier.length} earlier</span>${icon('chevronDown', 14)}</button></div>
    <div class="wn-earlier" id="wn-earlier" inert><div>${releasesMarkup(earlier, true)}</div></div>`;
}

/**
 * The card. `manual`: opened again from Settings or the palette, so nothing rolls and no hint.
 * `earlier`: the releases before these, behind "All updates".
 */
export function cardMarkup({current, seen = null, releases, earlier = [], manual = false}) {
  const labelled = releases.length > 1 || releases[0]?.version !== current;
  const date = releases[0]?.version === current ? releasedOn(releases[0].date) : '';
  const sub = !manual && seen ? `New since ${esc(seen)}` : date ? `Released ${esc(date)}` : '';
  const body = releasesMarkup(releases, labelled) + earlierMarkup(earlier);
  return `<aside class="wn" id="whats-new" role="dialog" aria-modal="false" aria-labelledby="wn-title" tabindex="-1">
    <div class="wn-head">
      <p class="wn-eyebrow" aria-hidden="true">${MARK}What’s new</p>
      <button type="button" class="wn-close" data-wn-close aria-label="Close what’s new" title="Close (Esc)">${icon('x', 14)}</button>
    </div>
    <h2 class="wn-title" id="wn-title"><span class="sr-only">What’s new in Foothold </span>${versionMarkup(rollSegments(manual ? current : seen, current))}</h2>
    ${sub ? `<p class="wn-sub">${sub}</p>` : ''}
    <div class="wn-body">${body}</div>
    <div class="wn-foot">${manual ? '' : '<span class="wn-hint">Find it again in Settings › System</span>'}<button type="button" class="wn-ok" data-wn-close>Got it</button></div>
    <p class="sr-only" role="status" data-wn-say></p>
  </aside>`;
}

// ---------------------------------------------------------------- the card on the page
let card = null;      // {el, current, opener, recheck, focusOnShow}
let aside = false;    // the intro or setup fills the window

export function whatsNewOpen() { return card !== null && !aside; }

/**
 * Asked for on the intro or setup, where the card waits hidden: when it shows, by the buttons that screen
 * has. On a first run the intro leads into setup, whose way out is Skip for now; run again, Cancel.
 */
export function whatsNewOnceLeft(route, firstRun) {
  if (route === 'intro' && !firstRun) return 'What’s new opens when you close the intro';
  return `What’s new opens when you finish or ${firstRun ? 'skip' : 'cancel'} setup`;
}

/** While the intro or setup is on screen the card steps aside, still unread, and comes back after. */
export function setWhatsNewAside(value) {
  aside = value;
  if (!card) return;
  card.el.hidden = value;
  // Asked for while it waited: it takes focus as it shows, as it would have when asked for anywhere else.
  if (!value && card.focusOnShow) {
    card.focusOnShow = false;
    card.el.focus({preventScroll: true});
  }
}

// "All updates" opens or folds the earlier releases. Opened, the list scrolls so the row sits at
// its top with them under it, when they don't all fit already.
function toggleEarlier(button) {
  const body = button.closest('.wn-body');
  const row = button.parentElement;
  const list = document.getElementById(button.getAttribute('aria-controls'));
  const open = button.getAttribute('aria-expanded') !== 'true';
  // Already as tall as the window allows: no height to grow into, so it opens at once and scrolls.
  const full = open && body.scrollHeight > body.clientHeight;
  list.classList.toggle('wn-snap', full);
  list.inert = !open;
  button.setAttribute('aria-expanded', String(open));
  if (!open) return;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const reveal = () => {
    if (button.getAttribute('aria-expanded') !== 'true') return;
    const view = body.getBoundingClientRect();
    const rect = list.getBoundingClientRect();
    if (rect.bottom <= view.bottom) return;
    // From the list, not the row: the row may be stuck to the bottom edge, away from its place.
    const top = body.scrollTop + rect.top - view.top - body.clientTop - row.offsetHeight;
    body.scrollTo({top, behavior: reduced ? 'auto' : 'smooth'});
  };
  if (full || reduced) { reveal(); return; }
  list.addEventListener('transitionend', function grown(e) {
    if (e.target !== list || e.propertyName !== 'grid-template-rows') return;      // not an item's hover
    list.removeEventListener('transitionend', grown);
    reveal();
  });
}

function mount({current, seen, releases, manual}) {
  const holder = document.createElement('div');
  holder.innerHTML = cardMarkup({current, seen, releases, earlier: earlierReleases(current, releases), manual});
  const el = holder.firstElementChild;
  card = {el, current, opener: manual ? document.activeElement : null, recheck: null, focusOnShow: manual && aside};
  el.hidden = aside;
  el.addEventListener('click', e => {
    if (e.target.closest('[data-wn-close]')) closeWhatsNew();
    const more = e.target.closest('[data-wn-more]');
    if (more) toggleEarlier(more);
  });
  el.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    e.preventDefault();
    e.stopPropagation();       // the page's own Escape (close the drawer) waits for the next press
    closeWhatsNew();
  });
  // Early in the tab order, after the header: it is about the whole app, not the page under it.
  const main = document.getElementById('main');
  if (main) main.before(el); else document.body.append(el);
  if (manual) {
    el.focus({preventScroll: true});
    return;
  }
  const count = releases.reduce((total, r) => total + r.items.length, 0);
  setTimeout(() => {
    const say = el.querySelector('[data-wn-say]');
    if (say) say.textContent = `What’s new in Foothold ${current}: ${count} ${count === 1 ? 'change' : 'changes'}. Press Escape to close.`;
  }, 400);
  // Closed in the other window (the app window and a browser tab): leave quietly here too.
  card.recheck = async () => {
    if (document.hidden || card?.el !== el) return;
    const info = await get('/api/whats-new').catch(() => null);
    if (card?.el === el && info?.seen && compareVersions(info.seen, current) >= 0) remove();
  };
  document.addEventListener('visibilitychange', card.recheck);
}

function remove() {
  if (!card) return null;
  const {el, opener, recheck} = card;
  card = null;
  if (recheck) document.removeEventListener('visibilitychange', recheck);
  const hadFocus = el.contains(document.activeElement);
  el.inert = true;
  el.classList.add('leaving');
  setTimeout(() => el.remove(), LEAVE_MS);
  if (hadFocus) (opener?.isConnected ? opener : document.getElementById('main'))?.focus({preventScroll: true});
  return el;
}

/** Close it for good: the server remembers the version this card showed. */
export function closeWhatsNew() {
  const current = card?.current;
  if (!remove()) return;
  post('/api/whats-new/seen', {version: current}).catch(() => {});      // failed: it shows again next time
}

/** After boot: show the card if this version has notes the user hasn't closed. */
export async function checkWhatsNew({route = () => ''} = {}) {
  let info;
  try { info = await get('/api/whats-new'); } catch { return; }
  if (!cardToShow(info, route())) return;
  await new Promise(resolve => setTimeout(resolve, SHOW_AFTER));
  const show = cardToShow(info, route());       // setup may have opened in the meantime
  if (show && !card) mount(show);
}

/** Settings › System and the palette: this version's notes, whether or not they were closed. */
export async function openWhatsNew() {
  if (card) {
    if (aside) card.focusOnShow = true; else card.el.focus({preventScroll: true});
    return;
  }
  const info = await get('/api/whats-new').catch(() => null);
  const releases = info?.version ? recentReleases(info.version) : [];
  if (!releases.length) return false;
  mount({current: info.version, seen: info.seen, releases, manual: true});
  return true;
}
