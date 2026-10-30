import {ageLong, compact, esc} from './lib.js';

// The Live card's collection status: a short title, a few labelled numbers and
// at most one plain sentence, rather than one long run of figures.
const PHASES = {starting: 'Starting a check', fetching: 'Checking sources', indexing: 'Ranking new jobs',
  alerts: 'Checking alerts', descriptions: 'Reading job descriptions', finishing: 'Wrapping up'};

const KNOWN_ERRORS = [
  [/database is locked|database is busy/i, 'Another task was using the database at the same time.'],
  [/timed? ?out/i, 'A source took too long to respond.'],
  [/connection|network|getaddrinfo|name resolution|unreachable/i, "Couldn't connect to one of the sources."],
];

export function duration(seconds = 0) {
  const s = Math.max(0, Math.round(seconds || 0));
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, '0')}s`;
}

/** "Now checking A, B and 97 more." Several sources can share a label, so names are de-duplicated. */
function nowChecking(sources) {
  const labels = [...new Set(Object.values(sources || {}).filter(source => source.state === 'running').map(source => source.label))];
  if (!labels.length) return '';
  if (labels.length <= 2) return `Now checking ${labels.join(' and ')}.`;
  return `Now checking ${labels.slice(0, 2).join(', ')} and ${labels.length - 2} more.`;
}

function errorStatus(raw) {
  const code = String(raw).replace(/^poll failed:\s*/i, '');
  const known = KNOWN_ERRORS.find(([pattern]) => pattern.test(code));
  return {title: /^poll failed/i.test(raw) ? "Last check didn't finish" : "Couldn't update your matches",
    detail: `${known ? known[1] : 'Something went wrong.'} Foothold will try again on the next check.`,
    code, error: true, progress: false};
}

function counts(p, {sources = false} = {}) {
  const stats = [];
  if (sources) stats.push({label: 'Sources', value: p.completed});
  if (p.new !== undefined && p.new !== null) stats.push({label: 'New jobs', value: compact(p.new)});
  stats.push({label: 'Scanned', value: compact(p.jobs)});
  if (!sources) stats.push({label: 'Elapsed', value: duration(p.elapsed)});
  if (p.failed) stats.push({label: 'Failed', value: p.failed, tone: 'neg'});
  return stats;
}

const figure = n => Number(n || 0).toLocaleString('en-US');

/** How far a poll is: sources fetched, then descriptions read. Its other phases have no count (value null). */
function pollWork(p) {
  const d = p.descriptions;
  if (p.phase === 'fetching' && p.total) return {value: p.completed, max: p.total, count: `${figure(p.completed)} of ${figure(p.total)}`, unit: 'sources'};
  if (p.phase === 'descriptions' && d?.total) return {value: d.completed, max: d.total, count: `${figure(d.completed)} of ${figure(d.total)}`, unit: 'descriptions'};
  return {value: null, max: 0, count: ''};
}

/** How far a ranking pass is, out of the backlog it started with; until that is known, how many are left. */
function rankWork(s) {
  const r = s.ranking;
  if (r?.total) return {value: Math.min(r.done, r.total), max: r.total, count: `${figure(r.done)} of ${figure(r.total)}`};
  return {value: null, max: 0, count: s.pending > 0 ? `${figure(s.pending)} left` : ''};
}

/** The work under way, one entry each for collecting (a poll) and ranking (a pass over the backlog), which can
 *  run at once: "Collecting · 34 of 120 sources", "Ranking · 1,200 of 4,800". */
export function backgroundWork(s) {
  const work = [];
  const p = s?.progress;
  if (s?.poll_running && p) {
    const w = pollWork(p);
    work.push({...w, key: `collect-${p.phase}`, label: 'Collecting',
      count: w.value === null ? PHASES[p.phase] || 'Checking for jobs' : `${w.count} ${w.unit}`});
  }
  // A pass that failed leaves its last count behind, which is not work under way.
  if (s?.indexing || (s?.pending > 0 && !s?.error)) {
    const w = rankWork(s);
    work.push({...w, key: 'rank', label: 'Ranking', count: w.count || 'Scoring postings'});
  }
  return work;
}

/** A bar for work under way: filled to value of max, or sliding while how much is left is not known. */
export function progressBar({key = '', label = '', value = null, max = 0}) {
  const known = value !== null && max > 0;
  const done = known ? `${+Math.min(100, Math.max(0, (value / max) * 100)).toFixed(2)}%` : '';
  return `<div class="work-bar${known ? '' : ' indeterminate'}" role="progressbar" aria-label="${esc(label)}"${key ? ` data-bar="${esc(key)}"` : ''}`
    + (known ? ` aria-valuemin="0" aria-valuemax="${max}" aria-valuenow="${value}" style="--done:${done}"` : '')
    + '><i></i></div>';
}

/** Labelled bars for the work under way, one row each. */
export function workMarkup(work) {
  return work.map(w => `<div class="work-row"><p><b>${esc(w.label)}</b> · ${esc(w.count)}</p>${progressBar(w)}</div>`).join('');
}

const shown = new WeakMap();
/** Put markup in el when it changed. A bar that was there already glides from its old value to the new one. */
export function showWork(el, markup) {
  if (shown.get(el) === markup) return;
  shown.set(el, markup);
  const was = new Map([...el.querySelectorAll('[data-bar]')].map(bar => [bar.dataset.bar, bar.style.getPropertyValue('--done')]));
  el.innerHTML = markup;
  for (const bar of el.querySelectorAll('[data-bar]')) {
    const from = was.get(bar.dataset.bar), to = bar.style.getPropertyValue('--done');
    if (!from || !to || from === to) continue;
    bar.style.setProperty('--done', from);
    bar.getBoundingClientRect();        // lay out the old width first, so the change to the new one transitions
    bar.style.setProperty('--done', to);
  }
  // Every slide keeps time with the page, so a bar drawn again goes on from where it was instead of starting over.
  for (const slide of el.querySelectorAll('.work-bar.indeterminate > i')) {
    for (const animation of slide.getAnimations()) animation.startTime = 0;
  }
}

export function collectionStatus(s) {
  const p = s.progress;
  if (s.offline) return {title: "Can't reach Foothold", detail: 'If it was closed, open Foothold from the Start menu. Reconnecting automatically.',
    error: true, progress: false};
  const error = s.error || p?.error;
  if (error) return errorStatus(error);
  if (s.poll_running && p) {
    const w = pollWork(p);
    return {...w, title: PHASES[p.phase] || 'Checking for jobs', stats: counts(p), progress: true, key: `poll-${p.phase}`,
      detail: w.unit === 'sources' ? nowChecking(p.sources) : ''};
  }
  // After an update every saved posting is re-ranked; the count shows it is getting somewhere.
  if (s.indexing || s.pending > 0) return {...rankWork(s), title: 'Ranking jobs', key: 'rank', progress: true,
    detail: 'Scoring postings against your profile. Every tab stays usable.'};
  if (p?.phase === 'complete') return {title: 'Up to date', stats: counts(p, {sources: true}), progress: false,
    detail: s.last_poll ? `Last checked ${ageLong(s.last_poll)}.` : ''};
  return null;
}

export function collectionMarkup(status) {
  const model = collectionStatus(status);
  if (!model) return '';
  const stats = model.stats?.length ? `<dl class="collection-stats">${model.stats.map(stat =>
    `<div${stat.tone ? ` class="${stat.tone}"` : ''}><dt>${esc(stat.label)}</dt><dd>${esc(stat.value)}</dd></div>`).join('')}</dl>` : '';
  return `<div class="collection-heading"><strong>${esc(model.title)}</strong>${model.count ? `<span class="collection-count">${esc(model.count)}</span>` : ''}</div>`
    + (model.progress ? progressBar({...model, label: model.title}) : '')
    + stats
    + (model.detail ? `<p>${esc(model.detail)}</p>` : '')
    + (model.code ? `<code class="collection-code">${esc(model.code)}</code>` : '');
}
