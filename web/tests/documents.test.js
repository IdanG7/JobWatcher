import assert from 'node:assert/strict';
import {mock, test} from 'node:test';
import {documentsSections, mountDocuments, stepFill, useAddress} from '../js/documents.js';

function section(fields = {}) {
  return {innerHTML: '', handlers: {}, fields, isConnected: true,
    addEventListener(type, fn) { this.handlers[type] = fn; },
    querySelector(sel) { return this.fields[sel] ?? null; }};
}

async function fixture(state, overrides = {}) {
  const cover = section({'[data-cover-notes]': {value: 'mention Excel'}, '[data-cover-body]': {value: 'Edited body'}});
  const merge = section();
  const el = {querySelector: sel => ({'[data-cover-root]': cover, '[data-merge-root]': merge})[sel]};
  const calls = [];
  const toasts = [];
  const deps = {
    get: async path => { calls.push(['get', path]); return state; },
    api: async (path, opts) => { calls.push(['api', path, opts]); return {...state, letter: {body: 'New letter', model: 'llama3.1:8b', references: ['er.pdf'], notes: opts.body.notes}}; },
    put: async (path, body) => { calls.push(['put', path, body]); return {...state, letter: {...state.letter, body: body.body, edited: true}}; },
    download: async (path, body) => { calls.push(['download', path, body]); return 'RBC - Analyst.pdf'; },
    fileToBase64: async file => `b64:${file.name}`,
    toast: (msg, opts) => toasts.push([msg, opts]),
    confirm: async () => true,
    ...overrides,
  };
  await mountDocuments(el, {key: 'rbc:1', company: 'RBC', title: 'Analyst'}, deps);
  const click = (root, attrs) => root.handlers.click({target: {closest: sel => (sel in attrs ? attrs[sel] : null)}});
  return {cover, merge, calls, toasts, click};
}

test('sections render placeholders for the drawer', () => {
  assert.match(documentsSections(), /data-cover-root/);
  assert.match(documentsSections(), /data-merge-root/);
});

test('until a local model is ready the drawer points to Settings', async () => {
  const {cover} = await fixture({letter: null, running: false, model: '', resume: true, references: 0});
  assert.match(cover.innerHTML, /no account or API key/);
  assert.match(cover.innerHTML, /#\/settings\?tab=letters/);
  assert.doesNotMatch(cover.innerHTML, /Write letter/);
  const noModel = await fixture({letter: null, running: true, model: '', resume: true, references: 0});
  assert.match(noModel.cover.innerHTML, /Download a writing model/);
});

test('generate sends notes, then the letter is offered for merging', async () => {
  const f = await fixture({letter: null, running: true, model: 'llama3.1:8b', resume: true, references: 2});
  assert.match(f.cover.innerHTML, /Write letter/);
  assert.match(f.cover.innerHTML, /closest of your 2 past letters/);
  assert.match(f.merge.innerHTML, /data-merge-act="merge" disabled/);
  await f.click(f.cover, {'[data-cover-act]': {dataset: {coverAct: 'generate'}}});
  const call = f.calls.find(c => c[0] === 'api');
  assert.equal(call[1], '/api/jobs/rbc%3A1/cover-letter');
  assert.deepEqual(call[2].body, {notes: 'mention Excel'});
  assert.match(f.cover.innerHTML, /New letter/);
  assert.match(f.cover.innerHTML, /Written by llama3\.1:8b/);
  assert.match(f.cover.innerHTML, /Adapted from your past letter er\.pdf/);
  assert.match(f.merge.innerHTML, /Cover letter \(from above\)/);
});

test('merge saves pending edits and sends files in order', async () => {
  const f = await fixture({letter: {body: 'Old body', model: 'm'}, running: true, model: 'm', resume: true, references: 0});
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

test('a change request goes with the letter as shown', async () => {
  const f = await fixture({letter: {body: 'Old body', model: 'm'}, running: true, model: 'm', resume: true, references: 1});
  assert.match(f.cover.innerHTML, /Ask for a change/);
  assert.doesNotMatch(f.cover.innerHTML, /Anything to emphasize/);
  let focused = false;
  f.cover.fields['[data-cover-ask]'] = {value: '  ', focus: () => { focused = true; }};
  await f.click(f.cover, {'[data-cover-act]': {dataset: {coverAct: 'revise'}}});
  assert.ok(focused);
  assert.equal(f.calls.filter(c => c[0] === 'api').length, 0);
  f.cover.fields['[data-cover-ask]'] = {value: ' shorten it '};
  await f.click(f.cover, {'[data-cover-act]': {dataset: {coverAct: 'revise'}}});
  const call = f.calls.find(c => c[0] === 'api');
  assert.equal(call[1], '/api/jobs/rbc%3A1/cover-letter/revise');
  assert.deepEqual(call[2].body, {request: 'shorten it', body: 'Edited body'});
  assert.match(f.cover.innerHTML, /New letter/);
  assert.match(f.toasts.at(-1)[0], /Change made/);
});

test('a requirement the letter misses becomes a change request in one click', async () => {
  const needs = [{phrase: 'cash flow forecasting', evidence: 'Oxford Properties Group, Student Treasury Analyst', covered: true},
    {phrase: 'liquidity management', evidence: 'McAsphalt Industries, Finance Intern', covered: false},
    {phrase: 'client service', evidence: '', covered: false}];
  const f = await fixture({letter: {body: 'Old body', model: 'm', needs}, running: true, model: 'm', resume: true, references: 1});
  assert.match(f.cover.innerHTML, /The posting asks for/);
  assert.match(f.cover.innerHTML, /class="badge best"[^>]*>.*cash flow forecasting/);
  assert.match(f.cover.innerHTML, /data-cover-act="need" data-need="1"[^>]*>.*liquidity management/);
  let focused = false;
  f.cover.fields['[data-cover-ask]'] = {value: '', focus: () => { focused = true; }};
  await f.click(f.cover, {'[data-cover-act]': {dataset: {coverAct: 'need'}}, '[data-need]': {dataset: {need: '1'}}});
  assert.ok(focused);
  assert.match(f.cover.innerHTML, /value="Work &quot;liquidity management&quot; into the paragraph about McAsphalt Industries, Finance Intern"/);
  assert.equal(f.calls.filter(c => c[0] === 'api').length, 0);      // nothing is sent until the user asks
  assert.match(f.cover.innerHTML, /data-need="2" title="Not in the letter yet. Your resume doesn’t show this/);
  await f.click(f.cover, {'[data-cover-act]': {dataset: {coverAct: 'need'}}, '[data-need]': {dataset: {need: '2'}}});
  assert.match(f.cover.innerHTML, /value="Say that I look forward to &quot;client service&quot; in this role/);
});

test('a found street address replaces the old one under the company', () => {
  const street = ['200 Bay Street', 'Toronto, ON M5J 2J5'];
  assert.deepEqual(useAddress(['Hiring Manager', 'RBC', 'Toronto, ON'], 'RBC', street), ['Hiring Manager', 'RBC', ...street]);
  assert.deepEqual(useAddress(['Ms. Chen', 'Treasury', 'rbc'], 'RBC', street), ['Ms. Chen', 'Treasury', 'rbc', ...street]);
  assert.deepEqual(useAddress(['Somewhere'], 'RBC', street), ['Hiring Manager', 'RBC', ...street]);
  assert.deepEqual(useAddress(['Hiring Manager', 'RBC', 'Toronto, ON'], 'RBC', street, 'Jane Smith'), ['Jane Smith', 'RBC', ...street]);
});

test('the letter is addressed from the To line: find, use, then save', async () => {
  const recipient = {lines: ['Hiring Manager', 'RBC', 'Toronto, ON'], source: 'city'};
  const found = {query: 'RBC, Toronto', results: [{name: 'RBC Centre', lines: ['155 Wellington St W', 'Toronto, ON M5V 3H1']}]};
  const sent = [];
  const f = await fixture({letter: {body: 'Old body', model: 'm'}, running: true, model: 'm', resume: true, references: 1, recipient}, {
    api: async (path, opts) => { sent.push(['api', path, opts]); return found; },
    put: async (path, body) => { sent.push(['put', path, body]); return {letter: {body: 'Readdressed', model: 'm'}, running: true, model: 'm', resume: true, references: 1, recipient: {lines: body.lines, source: 'saved'}}; },
  });
  assert.match(f.cover.innerHTML, /Hiring Manager, RBC, Toronto, ON/);
  assert.match(f.cover.innerHTML, /No street address/);
  assert.match(f.cover.innerHTML, /data-cover-act="address" disabled/);     // nothing to save yet

  f.cover.fields['[data-cover-recipient]'] = {value: recipient.lines.join('\n')};
  f.cover.fields['[data-cover-to]'] = {open: true};
  await f.click(f.cover, {'[data-cover-act]': {dataset: {coverAct: 'find'}}});
  assert.deepEqual(sent[0].slice(0, 2), ['api', '/api/jobs/rbc%3A1/recipient/lookup']);
  assert.match(f.cover.innerHTML, /RBC Centre/);
  assert.match(f.cover.innerHTML, /<details class="doc-to" data-cover-to open>/);

  await f.click(f.cover, {'[data-cover-act]': {dataset: {coverAct: 'use'}}, '[data-found]': {dataset: {found: '0'}}});
  assert.match(f.cover.innerHTML, /Hiring Manager\nRBC\n155 Wellington St W\nToronto, ON M5V 3H1<\/textarea>/);
  assert.equal(sent.length, 1);                                               // nothing saved until asked

  f.cover.fields['[data-cover-recipient]'] = {value: 'Hiring Manager\nRBC\n155 Wellington St W\nToronto, ON M5V 3H1\n'};
  await f.click(f.cover, {'[data-cover-act]': {dataset: {coverAct: 'address'}}});
  assert.deepEqual(sent[1], ['put', '/api/jobs/rbc%3A1/recipient',
    {lines: ['Hiring Manager', 'RBC', '155 Wellington St W', 'Toronto, ON M5V 3H1'], body: 'Edited body'}]);
  assert.match(f.cover.innerHTML, /Readdressed/);
  assert.match(f.cover.innerHTML, />Saved</);
  assert.doesNotMatch(f.cover.innerHTML, /RBC Centre/);
  assert.match(f.toasts.at(-1)[0], /readdressed/);
});

test('an address typed but not saved goes into the next letter', async () => {
  const recipient = {lines: ['Hiring Manager', 'RBC', 'Toronto, ON'], source: 'city'};
  const sent = [];
  const f = await fixture({letter: null, running: true, model: 'm', resume: true, references: 0, recipient}, {
    api: async (path, opts) => { sent.push(['api', path, opts.body]); return {letter: {body: 'New letter', model: 'm'}, recipient}; },
    put: async (path, body) => { sent.push(['put', path, body]); return {recipient: {lines: body.lines, source: 'saved'}}; },
  });
  f.cover.fields['[data-cover-recipient]'] = {value: 'Hiring Manager\nRBC\n200 Bay Street'};
  await f.click(f.cover, {'[data-cover-act]': {dataset: {coverAct: 'generate'}}});
  assert.deepEqual(sent.map(c => c.slice(0, 2)), [['put', '/api/jobs/rbc%3A1/recipient'], ['api', '/api/jobs/rbc%3A1/cover-letter']]);
  assert.deepEqual(sent[0][2], {lines: ['Hiring Manager', 'RBC', '200 Bay Street']});
});

// The letter is written on the server; the panel follows it a beat at a time.
const READY = {letter: null, running: true, model: 'qwen3:8b', resume: true, references: 0};
const WRITING = {kind: 'write', steps: ['Reading the posting', 'Reading your resume', 'Writing the letter'], step: 0,
  started_at: new Date().toISOString()};
const beat = async () => {
  mock.timers.tick(1500);
  for (let i = 0; i < 3; i++) await new Promise(r => setImmediate(r));
};

test('a letter written in the background shows its steps, then the letter', async () => {
  mock.timers.enable({apis: ['setTimeout']});
  try {
    let served = READY;
    const f = await fixture(READY, {get: async () => served, api: async () => ({...READY, writing: {...WRITING}})});
    await f.click(f.cover, {'[data-cover-act]': {dataset: {coverAct: 'generate'}}});
    assert.match(f.cover.innerHTML, /aria-busy="true">.*Writing…<\/button>/s);
    assert.match(f.cover.innerHTML, /data-cover-act="generate" disabled/);
    assert.match(f.cover.innerHTML, /Reading the posting…/);
    assert.match(f.cover.innerHTML, /Step 1 of 3 · 0:0\d/);
    assert.match(f.cover.innerHTML, /value="mention Excel"/);       // the notes stay while it writes
    served = {...READY, writing: {...WRITING, step: 2}};
    await beat();
    assert.match(f.cover.innerHTML, /<li class="done"><\/li><li class="done"><\/li><li class="now"><\/li>/);
    assert.match(f.cover.innerHTML, /Writing the letter…/);
    assert.deepEqual(f.toasts, []);
    served = {...READY, letter: {body: 'New letter', model: 'qwen3:8b', references: []}, writing: null};
    await beat();
    assert.match(f.cover.innerHTML, /New letter/);
    assert.doesNotMatch(f.cover.innerHTML, /data-cover-progress/);
    assert.match(f.merge.innerHTML, /Cover letter \(from above\)/);
    assert.deepEqual(f.toasts.map(t => t[0]), ['Cover letter written. Read it over before sending.']);
  } finally {
    mock.timers.reset();
  }
});

test('reopening the posting shows the letter under way, and a failure says why', async () => {
  mock.timers.enable({apis: ['setTimeout']});
  try {
    let served = {...READY, writing: {...WRITING, step: 1}};
    const f = await fixture(served, {get: async () => served});
    assert.match(f.cover.innerHTML, /Reading your resume…/);
    assert.match(f.cover.innerHTML, /data-cover-act="generate" disabled/);
    served = {...READY, writing: {...WRITING, step: 1, error: 'The model stopped answering.'}};
    await beat();
    assert.match(f.cover.innerHTML, /role="alert">.*The model stopped answering\./s);
    assert.match(f.cover.innerHTML, /data-cover-act="generate">.*Write letter/s);      // free to try again
    assert.deepEqual(f.toasts.map(t => [t[0], t[1].error]), [['The model stopped answering.', true]]);
  } finally {
    mock.timers.reset();
  }
});

test('a letter that lands after the user moved on is announced, with a way back', async () => {
  mock.timers.enable({apis: ['setTimeout']});
  try {
    let served = {...READY, writing: {...WRITING}};
    const f = await fixture(served, {get: async () => served});
    f.cover.isConnected = false;                                     // another posting is open now
    served = {...READY, letter: {body: 'New letter', model: 'qwen3:8b'}, writing: null};
    await beat();
    assert.deepEqual(f.toasts.map(t => [t[0], t[1].action.label]), [['Your letter for RBC is ready.', 'Open']]);
    await beat();
    assert.equal(f.toasts.length, 1);                                // and the following stops
  } finally {
    mock.timers.reset();
  }
});

test('steps finished between two looks fill one after another, then the step under way starts', () => {
  const w = {steps: ['Reading the posting', 'Reading your resume', 'Updating your past letter', 'Writing the letter', 'Checking'], step: 3};
  assert.deepEqual(stepFill(w, ['now', '', '', '', '']),
    [{cls: 'done', delay: 0}, {cls: 'done', delay: 140}, {cls: 'done', delay: 280}, {cls: 'now', delay: 420}, {cls: '', delay: 0}]);
  assert.deepEqual(stepFill({...w, step: 4}, ['done', 'done', 'done', 'now', '']).map(s => s.delay), [0, 0, 0, 0, 140]);
  assert.deepEqual(stepFill(w).map(s => s.cls), ['done', 'done', 'done', 'now', '']);         // first drawn
});
