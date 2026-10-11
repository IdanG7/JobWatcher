import assert from 'node:assert/strict';
import {test} from 'node:test';
import {documentsSections, mountDocuments} from '../js/documents.js';

function section(fields = {}) {
  return {innerHTML: '', handlers: {}, fields,
    addEventListener(type, fn) { this.handlers[type] = fn; },
    querySelector(sel) { return this.fields[sel] ?? null; }};
}

async function fixture(state) {
  const cover = section({'[data-cover-notes]': {value: 'mention Excel'}, '[data-cover-body]': {value: 'Edited body'}});
  const merge = section();
  const el = {querySelector: sel => ({'[data-cover-root]': cover, '[data-merge-root]': merge})[sel]};
  const calls = [];
  const toasts = [];
  const deps = {
    get: async path => { calls.push(['get', path]); return state; },
    api: async (path, opts) => { calls.push(['api', path, opts]); return {...state, letter: {body: 'New letter', model: 'gemini-3.6-flash', notes: opts.body.notes}}; },
    put: async (path, body) => { calls.push(['put', path, body]); return {...state, letter: {...state.letter, body: body.body, edited: true}}; },
    download: async (path, body) => { calls.push(['download', path, body]); return 'RBC - Analyst.pdf'; },
    fileToBase64: async file => `b64:${file.name}`,
    toast: (msg, opts) => toasts.push([msg, opts]),
    confirm: async () => true,
  };
  await mountDocuments(el, {key: 'rbc:1', company: 'RBC', title: 'Analyst'}, deps);
  const click = (root, attrs) => root.handlers.click({target: {closest: sel => (sel in attrs ? attrs[sel] : null)}});
  return {cover, merge, calls, toasts, click};
}

test('sections render placeholders for the drawer', () => {
  assert.match(documentsSections(), /data-cover-root/);
  assert.match(documentsSections(), /data-merge-root/);
});

test('without a Gemini key the drawer points to Settings', async () => {
  const {cover} = await fixture({letter: null, ai: false, resume: true, reference: null});
  assert.match(cover.innerHTML, /Connect a free Gemini API key/);
  assert.doesNotMatch(cover.innerHTML, /Write with Gemini/);
});

test('generate sends notes, then the letter is offered for merging', async () => {
  const f = await fixture({letter: null, ai: true, resume: true, reference: {filename: 'old.pdf'}});
  assert.match(f.cover.innerHTML, /Write with Gemini/);
  assert.match(f.cover.innerHTML, /style of your past letter \(old\.pdf\)/);
  assert.match(f.merge.innerHTML, /data-merge-act="merge" disabled/);
  await f.click(f.cover, {'[data-cover-act]': {dataset: {coverAct: 'generate'}}});
  const call = f.calls.find(c => c[0] === 'api');
  assert.equal(call[1], '/api/jobs/rbc%3A1/cover-letter');
  assert.deepEqual(call[2].body, {notes: 'mention Excel'});
  assert.match(f.cover.innerHTML, /New letter/);
  assert.match(f.merge.innerHTML, /Cover letter \(from above\)/);
});

test('merge saves pending edits and sends files in order', async () => {
  const f = await fixture({letter: {body: 'Old body', model: 'm'}, ai: true, resume: true, reference: null});
  f.merge.handlers.change({target: {matches: () => true, files: [{name: 'resume.pdf'}, {name: 'transcript.pdf'}]}});
  assert.match(f.merge.innerHTML, /1\. Cover letter/);
  assert.match(f.merge.innerHTML, /3\. transcript\.pdf/);
  // move the resume (item 2) to the top
  await f.click(f.merge, {'[data-merge-act]': {dataset: {mergeAct: 'up'}, closest: () => ({dataset: {mergeI: '1'}})}});
  const btn = {dataset: {mergeAct: 'merge'}, closest: () => null};
  await f.click(f.merge, {'[data-merge-act]': btn});
  assert.deepEqual(f.calls.find(c => c[0] === 'put').slice(1), ['/api/jobs/rbc%3A1/cover-letter', {body: 'Edited body'}]);
  const sent = f.calls.find(c => c[0] === 'download')[2];
  assert.deepEqual(sent.files, [{filename: 'resume.pdf', data: 'b64:resume.pdf'}, {cover_letter: 'rbc:1'},
    {filename: 'transcript.pdf', data: 'b64:transcript.pdf'}]);
  assert.equal(sent.name, 'RBC - Analyst');
  assert.match(f.toasts.at(-1)[0], /RBC - Analyst\.pdf/);
});
