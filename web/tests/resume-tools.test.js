import assert from 'node:assert/strict';
import {test} from 'node:test';
import {checkHtml, suggest, tweaksHtml} from '../js/resume-tools.js';

const check = {available: true, pages: 1, bullets: 6, lines: ['Built <3 models.', 'Helped with close.'], findings: [
  {key: 'weak_openers', title: '1 bullet opens with what you were given', detail: 'Start with the verb.', lines: ['Helped with close.']},
  {key: 'no_numbers', title: '4 of 6 bullets have no number', detail: 'Add one where you have it.', lines: ['Wrote the guide.']},
  {key: 'length', title: '2 pages; 1 is usual', detail: 'Cut the oldest lines.', lines: []},
]};

test('the check lists each finding with its lines; only wording problems offer a rewording', () => {
  const html = checkHtml(check);
  assert.match(html, /1 bullet opens with what you were given/);
  assert.match(html, /Start with the verb\./);
  assert.match(html, /data-rt-suggest data-line="Helped with close\."/);
  assert.equal(html.match(/data-rt-suggest/g).length, 3);      // the weak opener, then both lines under "every line"
  assert.doesNotMatch(html.split('Reword line by line')[0], /data-line="Wrote the guide\."/);   // a model can't add a number
  assert.match(html, /Built &lt;3 models\./);
  assert.match(html, /data-rt-all/);
});

test('a resume with nothing to fix says so, and no resume says nothing', () => {
  assert.match(checkHtml({available: true, findings: [], lines: []}), /Nothing a rule can see/);
  assert.equal(checkHtml({available: false, findings: []}), '');
  assert.equal(checkHtml(undefined), '');
});

test('what to tweak shows three states and suggests wording only where the resume shows the work', () => {
  const html = tweaksHtml({posting: true, items: [
    {phrase: 'cash flow forecasts', state: 'in_words', line: 'Built forecasts.'},
    {phrase: 'payment matching', state: 'other_words', line: 'Reconciled bank statements.'},
    {phrase: 'capital raising', state: 'absent', line: ''}]});
  assert.match(html, /cash flow forecasts.*In your resume in these words/s);
  assert.match(html, /data-rt-suggest data-line="Reconciled bank statements\." data-phrase="payment matching"/);
  assert.equal(html.match(/data-rt-suggest/g).length, 1);
  assert.match(html, /capital raising.*Not in your resume/s);
  assert.doesNotMatch(html, /score|%/i);
  assert.match(tweaksHtml({posting: false, items: []}), /description/);
  assert.match(tweaksHtml({posting: true, items: []}), /couldn’t pick out/);
});

function row(line, phrase = '') {
  const out = {hidden: true, innerHTML: '', className: ''};
  const button = {disabled: false, textContent: 'Suggest wording', dataset: {line, phrase},
    closest: () => ({querySelector: () => out})};
  return {button, out};
}

test('a suggestion is asked for one line and shown beside it to copy', async () => {
  const calls = [];
  const {button, out} = row('Helped with close.', 'month-end close');
  await suggest(button, {api: async (path, opts) => { calls.push([path, opts.body]); return {line: 'Closed the <books>.'}; }});
  assert.deepEqual(calls, [['/api/resume/reword', {line: 'Helped with close.', phrase: 'month-end close'}]]);
  assert.equal(out.hidden, false);
  assert.match(out.innerHTML, /Closed the &lt;books&gt;\./);
  assert.match(out.innerHTML, /data-rt-copy/);
  assert.equal(button.disabled, false);
  assert.equal(button.textContent, 'Try again');
});

test('a refused or failed rewording says why in place', async () => {
  const {button, out} = row('Helped with close.');
  await suggest(button, {api: async () => { throw new Error('The model’s rewording added something'); }});
  assert.match(out.innerHTML, /added something/);
  assert.match(out.className, /failed/);
  assert.equal(button.disabled, false);
});
