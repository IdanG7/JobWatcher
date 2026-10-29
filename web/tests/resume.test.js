import assert from 'node:assert/strict';
import {test} from 'node:test';
import {mountResume, resumeChanges, resumeFacts, resumeMatchSection} from '../js/resume.js';

const parsed = {education: {graduation_year: 2028, graduation_month: 4, level: 'undergraduate', gpa: 3.92},
  skills: [{key:'excel', label:'Excel'}], roles: [{title:'Treasury Analyst'}], languages:['English']};

async function fixture(saved = {available: false}) {
  const controls = Object.fromEntries(['file', 'text', 'saved', 'status', 'result'].map(k => [k, {
    value: '', textContent: '', hidden: false, disabled: false, files: [],
    setAttribute(k, v) {this[k] = v;}, addEventListener(type, fn) {this[type] = fn;},
  }]));
  const buttons = Object.fromEntries(['preview', 'apply', 'cancel', 'toggle', 'remove'].map(key => [key, {
    disabled: false, matches: s => s === `[data-resume-${key}]`, closest() {return this;},
  }]));
  const root = {isConnected: true, innerHTML: '',
    querySelector: s => controls[s.match(/data-resume-([a-z]+)/)[1]],
    querySelectorAll: () => [...Object.values(controls), ...Object.values(buttons)],
    addEventListener(type, fn) {this[type] = fn;},
  };
  const calls = [], applied = [];
  const deps = {
    get: async () => saved,
    post: async (path, body) => {calls.push({path, body}); return path.endsWith('/parse')
      ? {parsed, changes: {skills: {before:['python'], after:['excel']}}} : {profile:{graduation_year:2028}};},
    patch: async (path, body) => {calls.push({path, body}); return {...saved, ...body};},
    del: async path => calls.push({path}), toast() {}, confirm: async () => true,
  };
  await mountResume(root, {meta: {}, onApply: p => applied.push(p)}, deps);
  return {root, controls, buttons, deps, calls, applied, click: name => root.click({target: buttons[name]})};
}

test('facts, proposed changes and matching reasons escape document text', () => {
  const bad = '</dd><script>alert(1)</script>';
  for (const html of [resumeFacts({...parsed, roles:[{title:bad}]}),
    resumeChanges({skills:{before:[], after:[bad]}}),
    resumeMatchSection({matched:false, exclusions:[bad], reasons:[], review:[bad]})]) {
    assert.doesNotMatch(html, /<script>/);
    assert.match(html, /&lt;script&gt;/i);
  }
  assert.match(resumeFacts(parsed), /Apr 2028/);
  assert.match(resumeMatchSection({matched:false, exclusions:['Wrong graduation']}), /Excluded/);
  assert.equal(resumeMatchSection(null), '');
});

test('proposed changes name the licences a resume adds', () => {
  const meta = {licences: [{key: 'rn', label: 'Registered Nurse (RN)'}, {key: 'bls', label: 'BLS'}]};
  assert.match(resumeChanges({licences: {before: null, after: ['rn', 'bls']}}, meta), /Registered Nurse \(RN\), BLS/);
});

test('preview never applies; apply submits original input and updates profile', async () => {
  const f = await fixture();
  f.controls.text.value = 'A complete resume entered by the candidate';
  await f.click('preview');
  assert.equal(f.calls[0].path, '/api/resume/parse');
  assert.equal(f.applied.length, 0);
  assert.equal(f.controls.result.hidden, false);
  await f.click('apply');
  assert.equal(f.calls[1].path, '/api/resume');
  assert.deepEqual(f.calls[1].body, f.calls[0].body);
  assert.equal(f.applied[0].graduation_year, 2028);
  assert.equal(f.controls.text.value, '');
});

test('editing after preview and cancel prevent stale apply', async () => {
  const f = await fixture(); f.controls.text.value = 'Original resume';
  await f.click('preview'); f.controls.text.value = 'Edited resume'; f.controls.text.input();
  await f.click('apply'); assert.equal(f.calls.length, 1);
  await f.click('preview'); await f.click('cancel'); await f.click('apply');
  assert.equal(f.applied.length, 0);
  assert.equal(f.controls.result.hidden, true);
});

test('unsaved profile edits prevent apply without losing the resume preview', async () => {
  const f = await fixture();
  await mountResume(f.root, {meta:{}, canApply:() => false, onApply:p => f.applied.push(p)}, f.deps);
  f.controls.text.value = 'Resume text';
  await f.click('preview'); await f.click('apply');
  assert.equal(f.calls.length, 1);
  assert.match(f.controls.status.textContent, /Save your profile edits/);
  assert.equal(f.controls.result.hidden, false);
});

test('file upload sends base64 bytes and enforces size before a request', async () => {
  const f = await fixture();
  f.controls.file.files = [{name:'resume.txt', size:5000001}];
  await f.click('preview'); assert.equal(f.calls.length, 0);
  assert.match(f.controls.status.textContent, /5 MB/);
  f.controls.file.files = [{name:'resume.txt', size:5, arrayBuffer:async () => new TextEncoder().encode('Excel').buffer}];
  await f.click('preview'); assert.equal(f.calls[0].body.data, btoa('Excel'));
});

test('pending preview locks controls and ignores duplicate clicks', async () => {
  const f = await fixture(); f.controls.text.value = 'Resume text';
  let resolve;
  f.deps.post = () => new Promise(r => {resolve = r;});
  // Dependencies are captured at mount; use a fresh mount for the deferred request.
  await mountResume(f.root, {meta:{}, onApply() {}}, f.deps);
  const pending = f.click('preview');
  assert.equal(f.buttons.preview.disabled, true);
  await f.click('preview');
  resolve({parsed, changes:{}}); await pending;
  assert.equal(f.buttons.preview.disabled, false);
});

test('request failures preserve input and restore controls; detached views ignore replies', async () => {
  const f = await fixture();
  await mountResume(f.root, {meta:{}, onApply() {}}, {...f.deps, post:async () => {throw new Error('Unreadable PDF');}});
  f.controls.text.value = 'Keep this text'; await f.click('preview');
  assert.equal(f.controls.text.value, 'Keep this text');
  assert.equal(f.controls.status.role, 'alert');
  assert.equal(f.buttons.preview.disabled, false);
  let resolve;
  await mountResume(f.root, {meta:{}, onApply() {throw new Error('Stale apply');}}, {...f.deps, post:() => new Promise(r => {resolve = r;})});
  const pending = f.click('preview'); f.root.isConnected = false;
  resolve({parsed, changes:{}}); await pending;
  assert.equal(f.applied.length, 0);
});

test('pause and remove use explicit actions and removal can be canceled', async () => {
  const f = await fixture({available:true, enabled:true, filename:'resume.pdf', parsed});
  await f.click('toggle'); assert.deepEqual(f.calls[0].body, {enabled:false});
  await f.click('remove'); assert.equal(f.calls[1].path, '/api/resume');
  assert.match(f.controls.status.textContent, /removed/);
  const g = await fixture({available:true, enabled:true, parsed});
  await mountResume(g.root, {meta:{}, onApply() {}}, {...g.deps, confirm:async () => false});
  await g.click('remove'); assert.equal(g.calls.length, 0);
});
