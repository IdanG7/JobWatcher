import {compact, esc} from './lib.js';

export function collectionStatus(s) {
  const p = s.progress;
  const error = s.error || p?.error;
  if (error) return {title: 'Collection needs attention', detail: error, error: true, progress: false};
  if (s.poll_running && p) {
    const phases = {starting: 'Starting collection', fetching: 'Fetching job sources', indexing: 'Matching and ranking jobs',
      alerts: 'Checking alerts', descriptions: 'Fetching job descriptions', finishing: 'Finishing collection'};
    const active = Object.values(p.sources || {}).filter(source => source.state === 'running').map(source => source.label);
    const details = [`${p.completed} / ${p.total} sources checked`, `${compact(p.jobs)} postings fetched`,
      `${p.failed} failed`, `${p.elapsed || 0}s elapsed`];
    if (p.skipped) details.push(`${p.skipped} not due yet`);
    if (p.phase === 'fetching' && active.length) details.push(`Fetching: ${active.slice(0, 3).join(', ')}${active.length > 3 ? ` +${active.length - 3} more` : ''}`);
    if (p.phase === 'descriptions' && p.descriptions) details.push(`${p.descriptions.completed} / ${p.descriptions.total} descriptions`);
    return {title: phases[p.phase] || 'Collecting jobs', detail: details.join(' · '), progress: true,
      value: p.phase === 'fetching' && p.total ? p.completed : null, max: p.total || 1};
  }
  if (s.indexing || s.pending > 0) return {title: 'Matching and ranking jobs',
    detail: 'Preparing your job matches. You can keep using every tab.', progress: true, value: null, max: 1};
  if (p?.phase === 'complete') return {title: 'Collection complete',
    detail: `${p.completed} sources checked · ${compact(p.jobs)} postings fetched · ${p.failed} failed${p.skipped ? ` · ${p.skipped} not due yet` : ''}${p.failed ? ' — see Sources for details' : ''}`, progress: false};
  return null;
}

export function collectionMarkup(status) {
  const model = collectionStatus(status);
  if (!model) return '';
  return `<div class="collection-heading"><strong>${esc(model.title)}</strong><a class="link" href="#/sources">View sources</a></div>
    <p>${esc(model.detail)}</p>${model.progress ? `<progress aria-label="${esc(model.title)}" max="${model.max}"${model.value === null ? '' : ` value="${model.value}"`}></progress><span class="collection-note">Results appear as they are processed. All tabs remain available.</span>` : ''}`;
}
