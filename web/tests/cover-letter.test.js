import assert from 'node:assert/strict';
import {test} from 'node:test';
import {bindCoverLetter, coverLetterSection, downloadLetter} from '../js/cover-letter.js';

function fixture(letter = null) {
  const controls = Object.fromEntries(['candidate_name', 'background', 'motivation', 'content'].map(key =>
    [key, {value: letter?.[key] || '', disabled: false}]));
  const buttons = Object.fromEntries(['generate', 'save', 'copy', 'download'].map(key =>
    [key, {textContent: key, disabled: false, addEventListener(type, fn) {this[type] = fn;}}]));
  const status = {textContent: ''};
  const form = {
    isConnected: true,
    elements: {namedItem: key => controls[key]},
    querySelector: selector => selector === '[data-letter-status]' ? status : buttons[selector.match(/data-letter-(\w+)/)[1]],
    querySelectorAll: () => [...Object.values(controls), ...Object.values(buttons)],
    addEventListener(type, fn) {this[type] = fn;},
  };
  const job = {key: 'rbc:one', company: 'RBC', title: 'Analyst', cover_letter: letter};
  const notifications = [];
  const copied = [];
  const downloaded = [];
  const requests = [];
  const deps = {
    notify: (...args) => notifications.push(args), confirm: async () => true,
    post: async (path, body) => {requests.push({path, body}); return {cover_letter: {...body, content: 'Generated letter'}};},
    put: async (path, body) => {requests.push({path, body}); return {cover_letter: {...body, updated_at: '2026-10-10T12:00:00Z'}};},
    copy: async text => copied.push(text), download: (job, text) => downloaded.push(text),
  };
  return {controls, buttons, status, form, job, notifications, copied, downloaded, requests, deps};
}

test('section escapes stored input and exposes accessible editing and actions', () => {
  const html = coverLetterSection({cover_letter: {candidate_name: 'A"<x>', content: '</textarea><script>alert(1)</script>'}});
  assert.match(html, /A&quot;&lt;x&gt;/);
  assert.match(html, /&lt;\/textarea&gt;&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>/);
  for (const action of ['generate', 'save', 'copy', 'download']) assert.match(html, new RegExp(`data-letter-${action}`));
  assert.match(html, /aria-live="polite"/);
  assert.match(html, /<label[^>]*>[\s\S]*Cover letter text/);
});

test('generate, edit, save, copy and download use the current editor text', async () => {
  const f = fixture();
  bindCoverLetter(f.form, f.job, f.deps);
  assert.equal(f.buttons.save.disabled, true);
  f.controls.candidate_name.value = 'Alex';
  f.controls.background.value = 'I built a model.';
  await f.buttons.generate.click();
  assert.equal(f.requests[0].path, '/api/jobs/rbc%3Aone/cover-letter/generate');
  assert.equal(f.controls.content.value, 'Generated letter');
  assert.match(f.status.textContent, /not saved/i);
  assert.equal(f.job.cover_letter, null);
  f.controls.content.value = 'My edited letter';
  f.form.input();
  assert.match(f.status.textContent, /unsaved/i);
  await f.buttons.copy.click();
  await f.buttons.download.click();
  assert.deepEqual(f.copied, ['My edited letter']);
  assert.deepEqual(f.downloaded, ['My edited letter']);
  await f.form.submit({preventDefault() {}});
  assert.equal(f.requests[1].path, '/api/jobs/rbc%3Aone/cover-letter');
  assert.equal(f.requests[1].body.content, 'My edited letter');
  assert.equal(f.job.cover_letter.content, 'My edited letter');
  assert.match(f.status.textContent, /saved/i);
});

test('canceling regeneration preserves existing edits and makes no request', async () => {
  const f = fixture({content: 'Keep this letter'});
  f.deps.confirm = async () => false;
  bindCoverLetter(f.form, f.job, f.deps);
  await f.buttons.generate.click();
  assert.equal(f.controls.content.value, 'Keep this letter');
  assert.deepEqual(f.requests, []);
  assert.equal(f.buttons.generate.disabled, false);
});

test('server and clipboard errors preserve content and restore controls', async () => {
  const f = fixture({content: 'Keep me'});
  f.deps.post = f.deps.put = f.deps.copy = async () => {throw new Error('Unavailable');};
  bindCoverLetter(f.form, f.job, f.deps);
  await f.buttons.generate.click();
  await f.form.submit({preventDefault() {}});
  await f.buttons.copy.click();
  assert.equal(f.controls.content.value, 'Keep me');
  assert.equal(f.notifications.length, 3);
  assert.ok(f.notifications.every(([, options]) => options.error));
  assert.equal(f.buttons.generate.disabled, false);
  assert.equal(f.controls.content.disabled, false);
});

test('pending generation prevents duplicate requests and editing', async () => {
  const f = fixture();
  let resolve;
  f.deps.post = () => new Promise(r => {resolve = r;});
  bindCoverLetter(f.form, f.job, f.deps);
  const pending = f.buttons.generate.click();
  assert.equal(f.controls.content.disabled, true);
  assert.equal(f.buttons.generate.disabled, true);
  await f.buttons.generate.click();
  resolve({cover_letter: {content: 'Done'}});
  await pending;
  assert.equal(f.controls.content.value, 'Done');
  assert.equal(f.controls.content.disabled, false);
});

test('responses for closed drawers are ignored', async () => {
  const f = fixture();
  f.deps.post = async () => {f.form.isConnected = false; return {cover_letter: {content: 'Old role'}};};
  bindCoverLetter(f.form, f.job, f.deps);
  await f.buttons.generate.click();
  assert.equal(f.controls.content.value, '');
});

test('download creates a UTF-8 text file with a safe name and cleans up the URL', () => {
  const calls = [];
  const link = {click() {calls.push('click');}, remove() {calls.push('remove');}};
  let cleanup;
  const env = {
    document: {createElement: () => link, body: {append: () => calls.push('append')}}, Blob,
    URL: {createObjectURL: blob => {assert.equal(blob.type, 'text/plain;charset=utf-8'); return 'blob:letter';},
      revokeObjectURL: url => calls.push(url)},
    setTimeout: fn => {cleanup = fn;},
  };
  downloadLetter({company: '../../RBC', title: 'Analyst:/2027'}, 'Hello 世界', env);
  assert.match(link.download, /^cover-letter-[a-z0-9-]+\.txt$/);
  assert.equal(link.href, 'blob:letter');
  assert.deepEqual(calls, ['append', 'click', 'remove']);
  cleanup();
  assert.equal(calls.at(-1), 'blob:letter');
});
