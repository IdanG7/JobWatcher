import assert from 'node:assert/strict';
import {test} from 'node:test';
import {mountView} from '../js/view-loader.js';
import {collectionMarkup, collectionStatus} from '../js/collection-status.js';
import {api} from '../js/api.js';

test('navigation stays independent of a slow previous tab and cleans it up', async () => {
  const current = {};
  let resolve, cleaned = 0;
  const slow = mountView(current, {key: 'overview', name: 'overview', root: {},
    render: () => new Promise(r => { resolve = r; }), onError: () => assert.fail()});
  const settings = {refresh() {}};
  assert.equal(await mountView(current, {key: 'settings', name: 'settings', root: {}, render: async () => settings}), true);
  resolve({cleanup() {cleaned++;}});
  assert.equal(await slow, false);
  assert.equal(current.view, settings);
  assert.equal(cleaned, 1);
});

test('an error from a departed tab does not replace the current tab', async () => {
  const current = {};
  let reject;
  const slow = mountView(current, {key: 'overview', root: {}, render: () => new Promise((_, r) => {reject = r;}), onError: () => assert.fail()});
  await mountView(current, {key: 'sources', root: {}, render: async () => ({})});
  reject(new Error('old request'));
  assert.equal(await slow, false);
  assert.equal(current.key, 'sources');
});

test('fetch progress shows real counts, active sources, failures, and escaped labels', () => {
  const status = {poll_running: true, progress: {phase: 'fetching', total: 5, completed: 2, jobs: 100, new: 7, failed: 1, elapsed: 134,
    sources: {one: {state: 'running', label: '<RBC>'}, two: {state: 'running', label: '<RBC>'}, three: {state: 'queued', label: 'TD'}}}};
  const markup = collectionMarkup(status);
  assert.match(markup, /value="2"/);
  assert.match(markup, /2 of 5/);
  assert.match(markup, /<dt>New jobs<\/dt><dd>7<\/dd>/);
  assert.match(markup, /<dt>Elapsed<\/dt><dd>2m 14s<\/dd>/);
  assert.match(markup, /<dt>Failed<\/dt><dd>1<\/dd>/);
  assert.match(markup, /Now checking &lt;RBC&gt;\./, 'shared labels are listed once');
  status.progress.failed = 0;
  assert.doesNotMatch(collectionMarkup(status), /Failed/, 'no failure count when nothing failed');
  status.progress.phase = 'indexing';
  assert.equal(collectionStatus(status).value, null);
  assert.doesNotMatch(collectionMarkup(status), / value=/, '100% sources is not 100% overall processing');
});

test('completion, indexing, zero sources and server errors have useful states', () => {
  assert.match(collectionMarkup({indexing: true}), /Ranking new jobs/);
  assert.match(collectionMarkup({progress: {phase: 'complete', completed: 0, jobs: 0, failed: 0}}), /Up to date/);
  assert.match(collectionMarkup({error: '<offline>'}), /&lt;offline&gt;/);
  assert.match(collectionMarkup({progress: {phase: 'failed', error: 'Poll timed out'}}), /Poll timed out/);
  const locked = collectionMarkup({error: 'poll failed: OperationalError: database is locked'});
  assert.match(locked, /Last check didn&#39;t finish/);
  assert.match(locked, /using the database/);
  assert.match(locked, /<code class="collection-code">OperationalError: database is locked<\/code>/);
  assert.match(collectionMarkup({offline: true}), /reach Foothold/);
  assert.match(collectionStatus({offline: true}).detail, /open Foothold from the Start menu/);
  assert.equal(collectionMarkup({}), '');
});

test('stalled requests time out, including stalled response bodies', async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async (_, {signal}) => ({ok: true, text: () => new Promise((_, reject) => {
      signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
    })});
    await assert.rejects(api('/api/overview', {timeout: 10}), /taking too long/);
    const controller = new AbortController();
    const pending = api('/api/jobs', {signal: controller.signal});
    await Promise.resolve();
    controller.abort();
    await assert.rejects(pending, {name: 'AbortError'});
  } finally { globalThis.fetch = original; }
});
