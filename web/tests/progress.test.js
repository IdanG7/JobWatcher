import assert from 'node:assert/strict';
import {test} from 'node:test';
import {backgroundWork, collectionMarkup, progressBar, workMarkup} from '../js/collection-status.js';
import {emptyListWork, firstScanState} from '../js/views/opportunities.js';

test('a bar with a count fills to it; without one it slides instead of sitting gray', () => {
  const bar = progressBar({key: 'rank', label: 'Ranking', value: 1200, max: 4800});
  assert.match(bar, /aria-valuemax="4800" aria-valuenow="1200"/);
  assert.match(bar, /style="--done:25%"/);
  assert.match(bar, /data-bar="rank"/);
  assert.doesNotMatch(bar, /indeterminate/);
  for (const unknown of [{value: null, max: 0}, {value: null, max: 10}, {value: 0, max: 0}]) {
    const sliding = progressBar({label: 'Ranking', ...unknown});
    assert.match(sliding, /class="work-bar indeterminate"/);
    assert.doesNotMatch(sliding, /aria-valuenow|--done/, 'no value: assistive tech hears it as busy');
  }
  assert.match(progressBar({value: 0, max: 120}), /--done:0%/, 'nothing done yet is an empty bar, not a sliding one');
  assert.match(progressBar({value: 130, max: 120}), /--done:100%/);
  assert.match(progressBar({value: 1, max: 3}), /--done:33.33%/);
  assert.match(progressBar({label: '<x>'}), /aria-label="&lt;x&gt;"/);
});

test('background work reads as "Collecting · 34 of 120 sources" and "Ranking · 1,200 of 4,800"', () => {
  const firstScan = {poll_running: true, indexing: true, pending: 3600, ranking: {total: 4800, done: 1200},
    progress: {phase: 'fetching', total: 120, completed: 34, sources: {}}};
  const work = backgroundWork(firstScan);
  assert.deepEqual(work.map(w => [w.label, w.count, w.value, w.max]),
    [['Collecting', '34 of 120 sources', 34, 120], ['Ranking', '1,200 of 4,800', 1200, 4800]]);
  const rows = workMarkup(work);
  assert.match(rows, /<b>Collecting<\/b> · 34 of 120 sources<\/p><div class="work-bar"/);
  assert.match(rows, /<b>Ranking<\/b> · 1,200 of 4,800/);
  // Descriptions have a count too; the other phases name themselves and slide.
  const reading = backgroundWork({poll_running: true, progress: {phase: 'descriptions', descriptions: {completed: 3, total: 40}}})[0];
  assert.deepEqual([reading.count, reading.value, reading.max], ['3 of 40 descriptions', 3, 40]);
  const alerts = backgroundWork({poll_running: true, progress: {phase: 'alerts'}})[0];
  assert.deepEqual([alerts.count, alerts.value], ['Checking alerts', null]);
  // A pass not counted yet: what is left when known, else that it is scoring.
  assert.equal(backgroundWork({indexing: true, pending: 20818})[0].count, '20,818 left');
  assert.equal(backgroundWork({indexing: true})[0].count, 'Scoring postings');
  assert.equal(backgroundWork({indexing: true, ranking: {total: 100, done: 140}})[0].value, 100);
  assert.deepEqual(backgroundWork({}), []);
  assert.deepEqual(backgroundWork(null), []);
});

test('the Live card fills its bar while collecting and ranking, and drops it when done', () => {
  const ranking = collectionMarkup({indexing: true, pending: 3600, ranking: {total: 4800, done: 1200}});
  assert.match(ranking, /<strong>Ranking jobs<\/strong><span class="collection-count">1,200 of 4,800<\/span>/);
  assert.match(ranking, /data-bar="rank" aria-valuemin="0" aria-valuemax="4800" aria-valuenow="1200" style="--done:25%"/);
  const fetching = collectionMarkup({poll_running: true, progress: {phase: 'fetching', total: 120, completed: 34, jobs: 0, sources: {}}});
  assert.match(fetching, /<strong>Checking sources<\/strong><span class="collection-count">34 of 120<\/span>/);
  assert.match(fetching, /--done:28.33%/);
  assert.match(collectionMarkup({poll_running: true, progress: {phase: 'starting', jobs: 0}}), /work-bar indeterminate/);
  assert.match(collectionMarkup({indexing: true}), /work-bar indeterminate/);
  assert.doesNotMatch(collectionMarkup({progress: {phase: 'complete', completed: 120, jobs: 900}}), /work-bar/, 'finished: the bar goes');
});

test('an empty list during a first scan shows the work, and the roles once it ends', () => {
  const scanning = {poll_running: true, progress: {phase: 'fetching', total: 120, completed: 34}};
  const empty = {jobs: [], ranked_any: false};
  assert.equal(emptyListWork(empty, scanning)[0].count, '34 of 120 sources');
  const html = firstScanState(emptyListWork(empty, scanning));
  assert.match(html, /Finding roles for you/);
  assert.match(html, /<div class="work-list" data-work><div class="work-row">/);
  assert.doesNotMatch(html, /No roles match/);
  assert.equal(emptyListWork(empty, {}), null, 'nothing running: the usual empty state');
  assert.equal(emptyListWork({jobs: [{key: 'a'}], ranked_any: true}, scanning), null);
  // Once anything is ranked, a routine poll leaves an empty search as "no roles"; a pass with postings to go does not.
  const ranked = {jobs: [], ranked_any: true};
  assert.equal(emptyListWork(ranked, scanning), null);
  assert.equal(emptyListWork(ranked, {indexing: true, ranking: {total: 4800, done: 1200}}).at(-1).count, '1,200 of 4,800');
  assert.equal(emptyListWork(ranked, {indexing: true, ranking: {total: 4800, done: 4800}}), null);
  assert.equal(emptyListWork(ranked, {indexing: true, ranking: {total: 0, done: 0}}), null, 'a pass with nothing to rank');
  assert.ok(emptyListWork(ranked, {pending: 50}));
});
