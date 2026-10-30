// The tour: once after first-run setup, and again from Settings › System or the palette, a
// spotlight steps through the header's main places with an ink slip saying what each is for.
import {ONBOARDING, stepAfter} from './lib.js';
import {modKey, modalOpen, trapFocus} from './ui.js';
import {paletteOpen} from './palette.js';

export const TOUR_KEY = 'jw-tour';      // 'due' after first-run setup, 'seen' once it has started
const PAD = 6;

export const TOUR_STOPS = [
  {target: '.nav-links [data-nav="opportunities"]', title: 'Opportunities',
    text: 'Every posting from your boards, best fit first. Open one to see why it fits, when it closes, and to start a cover letter.'},
  {target: '.nav-links [data-nav="overview"]', title: 'Today',
    text: 'A daily brief: your top opportunities, what needs attention, and the next seven days.'},
  {target: '.nav-links [data-nav="applications"]', title: 'Applications',
    text: 'Roles you’ve saved or applied to, by stage. Move one along as you hear back.'},
  {target: '#status-toggle', title: 'Live',
    text: 'Foothold checks your sources in the background. Hover here to see what it’s doing, or to check now.'},
  {target: '#cmdk-open', title: 'Search',
    text: () => `Find any role or company, or jump to any page. ${modKey()} K works from anywhere, and ? lists every shortcut.`},
  {target: '.nav-actions [data-nav="settings"]', title: 'Settings',
    text: 'Your resume, boards, alerts and theme. This tour and the intro are under System when you want them again.'},
];

/** Whether the tour starts on this page: it is due (first-run setup just ended) and setup is no longer on screen. */
export function tourDue(state, route) {
  return state === 'due' && !ONBOARDING.has(route);
}

/** The stops whose target is on screen (`shown(selector)`), in order. */
export function tourStops(shown, stops = TOUR_STOPS) {
  return stops.filter(stop => shown(stop.target));
}

/** The spotlight around a target: padded, and no taller than a header control. */
export function spotRect(rect, pad = PAD) {
  const height = Math.min(rect.height + pad * 2, 40);
  return {left: rect.left - pad, top: rect.top + rect.height / 2 - height / 2, width: rect.width + pad * 2, height};
}

/** Where the slip goes: under the spotlight when it fits, else above it, always inside the window. */
export function cardPlacement(spot, card, view, {gap = 12, margin = 16} = {}) {
  const below = spot.top + spot.height + gap + card.height <= view.height - margin;
  const top = below ? spot.top + spot.height + gap : Math.max(margin, spot.top - gap - card.height);
  const left = Math.min(Math.max(margin, spot.left), view.width - margin - card.width);
  return {left: Math.max(margin, left), top, side: below ? 'below' : 'above'};
}

const visible = selector => {
  const el = document.querySelector(selector);
  return el && el.getClientRects().length && el.getBoundingClientRect().width > 0;
};

let tour = null;      // {el, close}

/** Starts the tour over the current page. Returns false when nothing it points at is on screen. */
export function startTour({onEnd = () => {}} = {}) {
  if (tour) return true;
  const stops = tourStops(visible);
  if (!stops.length) return false;
  const opener = document.activeElement;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const el = document.createElement('div');
  el.className = 'tour';
  el.innerHTML = `<div class="tour-spot"></div>
    <section class="tour-card" role="dialog" aria-modal="true" aria-labelledby="tour-title" aria-describedby="tour-text" tabindex="-1">
      <p class="tour-count"></p><h2 class="tour-title" id="tour-title"></h2><p class="tour-text" id="tour-text"></p>
      <div class="tour-foot"><button type="button" class="tour-end" data-tour="end">End tour</button>
        <span class="tour-nav"><button type="button" class="tour-back" data-tour="back">Back</button><button type="button" class="tour-next" data-tour="next"></button></span></div>
    </section>`;
  document.body.append(el);
  const spot = el.querySelector('.tour-spot');
  const card = el.querySelector('.tour-card');
  let index = 0;

  function place() {
    const target = document.querySelector(stops[index].target);
    if (!target) return;
    const s = spotRect(target.getBoundingClientRect());
    Object.assign(spot.style, {left: `${s.left}px`, top: `${s.top}px`, width: `${s.width}px`, height: `${s.height}px`});
    const p = cardPlacement(s, {width: card.offsetWidth, height: card.offsetHeight}, {width: innerWidth, height: innerHeight});
    Object.assign(card.style, {left: `${p.left}px`, top: `${p.top}px`});
    card.dataset.side = p.side;
  }

  function show(i) {
    index = i;
    const stop = stops[i];
    const last = i === stops.length - 1;
    // A nav link can sit scrolled out of a narrow header.
    document.querySelector(stop.target)?.scrollIntoView({block: 'nearest', inline: 'center', behavior: 'instant'});
    card.querySelector('.tour-count').textContent = `${i + 1} of ${stops.length}`;
    card.querySelector('.tour-title').textContent = stop.title;
    card.querySelector('.tour-text').textContent = typeof stop.text === 'function' ? stop.text() : stop.text;
    card.querySelector('.tour-back').hidden = i === 0;
    card.querySelector('.tour-next').textContent = last ? 'Done' : 'Next';
    place();
    card.querySelector('.tour-next').focus({preventScroll: true});
  }

  function go(action) {
    const next = stepAfter(index, action, stops.length);
    if (next.done) close(); else if (next.index !== index) show(next.index);
  }

  function onKey(e) {
    if (modalOpen() || paletteOpen()) return;      // a dialog opened over the tour has the keys
    if (e.key === 'Escape') close();
    else if (e.key === 'ArrowRight') go('next');
    else if (e.key === 'ArrowLeft') go('back');
    else if (e.key === 'Tab') { trapFocus(card, e); return; }
    else return;
    e.preventDefault();
    e.stopPropagation();      // the page's own keys wait until the tour is over
  }

  function close() {
    if (tour?.el !== el) return;
    tour = null;
    document.removeEventListener('keydown', onKey, true);
    removeEventListener('resize', place);
    removeEventListener('hashchange', close);
    watch.disconnect();
    el.classList.add('leaving');
    setTimeout(() => el.remove(), reduced ? 0 : 160);
    if (opener?.isConnected) opener.focus({preventScroll: true});
    onEnd();
  }

  el.addEventListener('click', e => {
    const act = e.target.closest('[data-tour]')?.dataset.tour;
    if (act === 'end') close(); else if (act) go(act);
  });
  document.addEventListener('keydown', onKey, true);
  addEventListener('resize', place);
  addEventListener('hashchange', close);      // it points at this page's header
  // A header control can change size mid-stop: Live's label, the counts.
  const watch = new ResizeObserver(() => place());
  stops.forEach(stop => { const target = document.querySelector(stop.target); if (target) watch.observe(target); });
  tour = {el, close};
  show(0);
  return true;
}
