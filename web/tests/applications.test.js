import assert from 'node:assert/strict';
import {test} from 'node:test';

import {appRow, defaultTab, listHtml, summaryLine} from '../js/views/applications.js';

const TODAY = new Date(2026, 10, 12, 10, 0);
const app = (over = {}) => ({key: 'halden:7', title: 'Embedded Firmware Intern', company: 'Halden Semiconductor', location: 'Toronto, ON',
  fit: 91, status: 'saved', status_label: 'Saved', deadline: '', applied_date: '', next_step: '', next_action_date: '', interview_date: '',
  url: 'https://jobs.example/7', ...over});
const text = html => html.replace(/<[^>]+>/g, '');

test('the summary reads as one sentence, and a zero is left out', () => {
  const apps = [app(), app({status: 'applied'}), app({status: 'first_round'}), app({status: 'offer'}), app({status: 'rejected'})];
  assert.equal(text(summaryLine(apps)), '4 active, 1 interviewing, 1 offer and 1 closed.');
  assert.equal(text(summaryLine([app(), app({status: 'preparing'})])), '2 active.');
  assert.equal(text(summaryLine([])), 'Nothing tracked yet.');
});

test('the list is the default until five applications are active, then the board', () => {
  const four = [app(), app(), app(), app(), app({status: 'rejected'}), app({status: 'archived'})];
  assert.equal(defaultTab(four), 'list');
  assert.equal(defaultTab([...four, app({status: 'applied'})]), 'board');
  assert.equal(defaultTab([]), 'list');
});

test('a row shows fit, the role as a button, the employer and the stage as a select', () => {
  const html = appRow(app({status: 'applied', applied_date: '2026-11-03'}), {today: TODAY});
  assert.match(html, /<tr data-key="halden:7">/);
  assert.doesNotMatch(html, /role="button"/);                    // the row holds a select; the title is the button
  assert.match(html, /class="fit high"[^>]*><b>91<\/b>/);
  assert.match(html, /<button type="button" class="role-open" data-open>Embedded Firmware Intern<\/button>/);
  assert.match(html, /Halden Semiconductor/);
  assert.match(html, /Toronto, ON/);
  assert.match(html, /<td class="c-applied num">Nov 3<\/td>/);
  assert.match(html, /<option value="applied" selected>Applied<\/option>/);
  assert.match(html, /aria-label="Stage for Halden Semiconductor Embedded Firmware Intern"/);
});

test('the next step sits under the role, and is a warning once it is overdue', () => {
  const due = appRow(app({status: 'applied', next_step: 'Check for a reply', next_action_date: '2026-11-25'}), {today: TODAY});
  assert.match(due, /<div class="reason">Check for a reply · Nov 25<\/div>/);
  const late = appRow(app({status: 'applied', next_step: 'Check for a reply', next_action_date: '2026-11-10'}), {today: TODAY});
  assert.match(late, /<div class="reason warn">/);
  assert.match(text(late), /Overdue · Check for a reply · Nov 10/);
  const interview = appRow(app({status: 'first_round', interview_date: '2026-11-20T14:00', next_step: 'Prepare'}), {today: TODAY});
  assert.match(interview, /<div class="reason">Interview Nov 20<\/div>/);
  assert.doesNotMatch(appRow(app(), {today: TODAY}), /class="reason/);   // nothing known, nothing shown
});

test('the deadline shows only while there is still something to send', () => {
  const saved = appRow(app({deadline: '2026-11-16'}), {today: TODAY});
  assert.match(saved, /<span class="by soon">Nov 16<small>4 days<\/small><\/span>/);
  const far = appRow(app({status: 'preparing', deadline: '2026-12-20'}), {today: TODAY});
  assert.match(far, /<span class="by">Dec 20<small>38 days<\/small><\/span>/);
  const sent = appRow(app({status: 'applied', deadline: '2026-11-16'}), {today: TODAY});
  assert.doesNotMatch(sent, /Nov 16/);
  const closed = appRow(app({status: 'rejected', deadline: '2026-11-16', next_step: 'Check for a reply'}), {today: TODAY});
  assert.match(closed, /<tr data-key="halden:7" class="is-closed">/);
  assert.doesNotMatch(closed, /Nov 16|Check for a reply/);
});

test('the list puts the furthest along first and closed applications in their own group', () => {
  const html = listHtml([
    app({key: 'a', title: 'Saved role'}), app({key: 'b', title: 'Rejected role', status: 'rejected'}),
    app({key: 'c', title: 'Offer role', status: 'offer'}), app({key: 'd', title: 'Applied role', status: 'applied'}),
    app({key: 'e', title: 'Final role', status: 'final_round'}),
  ], {today: TODAY});
  const order = [...html.matchAll(/data-open>([^<]+)</g)].map(m => m[1]);
  assert.deepEqual(order, ['Offer role', 'Final role', 'Applied role', 'Saved role', 'Rejected role']);
  assert.match(html, /<tbody class="closed">\s*<tr class="group"><th colspan="7" scope="rowgroup">Closed <span class="count">1<\/span><\/th><\/tr>/);
  assert.doesNotMatch(listHtml([app()], {today: TODAY}), /class="closed"/);
});
