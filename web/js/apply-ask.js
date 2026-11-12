// "Did you apply?" (plans/assisted-apply.md, part 1). Opening a posting sends the person to the employer's
// site; nothing brought them back to record what happened, so the tracker stayed empty. The posting panel
// now asks once when they are back. Which postings were opened is kept in this browser only.
import {icon} from './ui.js';

const KEY = 'jw-opened';
const KEEP_DAYS = 14;            // an unanswered question is dropped after this
const KEEP_MAX = 50;
const BACK_AFTER_MS = 3000;      // the window regaining focus sooner is the browser opening, not a return
const LATER_MS = 60_000;         // looked at again this long after opening: ask even if no return was seen
export const FOLLOW_UP_DAYS = 14;
// Statuses before "applied": only these (or no application yet) are asked about.
const EARLY = ['discovered', 'saved', 'preparing'];

/** The postings opened and not yet answered: {key: {at, back}}. */
export function readOpened(store, now = Date.now()) {
  let map;
  try { map = JSON.parse(store.get(KEY) || '{}'); } catch { return {}; }
  if (!map || typeof map !== 'object' || Array.isArray(map)) return {};
  return Object.fromEntries(Object.entries(map)
    .filter(([, e]) => e && typeof e.at === 'number' && now - e.at < KEEP_DAYS * 86_400_000));
}

function write(store, map) {
  const latest = Object.entries(map).sort((a, b) => b[1].at - a[1].at).slice(0, KEEP_MAX);
  store.set(KEY, JSON.stringify(Object.fromEntries(latest)));
}

export function noteOpened(store, key, now = Date.now()) {
  const map = readOpened(store, now);
  if (!map[key]) write(store, {...map, [key]: {at: now, back: false}});
}

/** The window is in front again: the postings the person has now come back from. */
export function noteReturned(store, now = Date.now()) {
  const map = readOpened(store, now);
  const back = Object.keys(map).filter(key => !map[key].back && now - map[key].at >= BACK_AFTER_MS);
  if (back.length) write(store, {...map, ...Object.fromEntries(back.map(key => [key, {...map[key], back: true}]))});
  return back;
}

export function clearOpened(store, key) {
  const map = readOpened(store);
  if (map[key]) { delete map[key]; write(store, map); }
}

export function shouldAsk(entry, status, now = Date.now()) {
  return Boolean(entry) && (!status || EARLY.includes(status)) && (entry.back || now - entry.at >= LATER_MS);
}

/** The day to check for a reply, as the local calendar date (YYYY-MM-DD). */
export function followUpDate(today = new Date()) {
  const day = new Date(today.getFullYear(), today.getMonth(), today.getDate() + FOLLOW_UP_DAYS);
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`;
}

export function askHtml() {
  return `<div class="callout info dh-callout ask-applied" role="group" aria-label="Did you apply?">${icon('check')}<div>
    <p><b>Did you apply?</b> You opened this posting.</p>
    <div class="ask-actions">
      <button type="button" class="btn sm" data-act="ask" data-answer="applied">I applied</button>
      <button type="button" class="btn sm ghost" data-act="ask" data-answer="working">Still working on it</button>
      <button type="button" class="btn sm ghost" data-act="ask" data-answer="no">Not for me</button>
      <button type="button" class="btn sm ghost icon" data-act="ask" data-answer="dismiss" aria-label="Don’t ask about this posting" title="Don’t ask">${icon('x', 13)}</button>
    </div></div></div>`;
}

/** Carry out an answer; returns what to tell the person. ``deps``: post, patch, hide(), today. */
export async function applyAnswer(answer, job, {post, patch, hide, today = new Date()}) {
  const status = job.app_status || job.application?.status;
  const path = `/api/applications/${encodeURIComponent(job.key)}`;
  const fresh = body => post('/api/applications', {key: job.key, ...body, job: {key: job.key, title: job.title,
    company: job.company, location: job.location, url: job.url, salary: job.salary, posted: job.posted}});
  if (answer === 'applied') {
    // A next step the person wrote themselves stays; otherwise one is set so the application isn't forgotten.
    const due = followUpDate(today);
    const followUp = job.application?.next_step ? {} : {next_step: 'Check for a reply', next_action_date: due};
    if (status) await patch(path, {status: 'applied', ...followUp}); else await fresh({status: 'applied', ...followUp});
    const [y, m, d] = due.split('-').map(Number);
    return followUp.next_step ? `Marked applied · follow-up set for ${new Date(y, m - 1, d).toLocaleDateString('en', {month: 'short', day: 'numeric'})}` : 'Marked applied';
  }
  if (answer === 'working') {
    if (!status) await fresh({status: 'preparing'});
    else if (status !== 'preparing') await patch(path, {status: 'preparing'});
    return 'Kept in your tracker as Preparing';
  }
  if (answer === 'no') { await hide(); return 'Hidden from lists'; }
  return '';
}
