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

export function collectionStatus(s) {
  const p = s.progress;
  if (s.offline) return {title: "Can't reach Foothold", detail: 'If it was closed, open Foothold from the Start menu. Reconnecting automatically.',
    error: true, progress: false};
  const error = s.error || p?.error;
  if (error) return errorStatus(error);
  if (s.poll_running && p) {
    const model = {title: PHASES[p.phase] || 'Checking for jobs', stats: counts(p), progress: true, value: null, max: 1};
    if (p.phase === 'fetching' && p.total) {
      Object.assign(model, {count: `${p.completed} of ${p.total}`, value: p.completed, max: p.total, detail: nowChecking(p.sources)});
    } else if (p.phase === 'descriptions' && p.descriptions?.total) {
      Object.assign(model, {count: `${p.descriptions.completed} of ${p.descriptions.total}`, value: p.descriptions.completed, max: p.descriptions.total});
    }
    return model;
  }
  if (s.indexing || s.pending > 0) return {title: 'Ranking new jobs',
    detail: 'Scoring new postings against your profile. Every tab stays usable.', progress: true, value: null, max: 1};
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
    + (model.progress ? `<progress aria-label="${esc(model.title)}" max="${model.max}"${model.value === null ? '' : ` value="${model.value}"`}></progress>` : '')
    + stats
    + (model.detail ? `<p>${esc(model.detail)}</p>` : '')
    + (model.code ? `<code class="collection-code">${esc(model.code)}</code>` : '');
}
