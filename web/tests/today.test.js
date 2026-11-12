import assert from 'node:assert/strict';
import {test} from 'node:test';

import {fitMeter, fitWord} from '../js/ui.js';
import {countsLine, leadHtml, listRow} from '../js/views/overview.js';

const NOW = Date.UTC(2026, 10, 12, 15, 0);
const TODAY = new Date(2026, 10, 12, 10, 0);
const JOB = {key: 'halden:7', title: 'Embedded Firmware Intern', company: 'Halden Semiconductor', location: 'Toronto, ON', city_label: 'Toronto',
  fit: 94, posted_ref: NOW / 1000 - 2 * 3600, deadline: '2026-11-20', cycle_label: 'Summer 2027', category: 'hardware', category_label: 'Hardware',
  badges: ['NEW', '2027'], fit_why: ['4 of 5 skills', 'Intern level'], fit_caution: '', url: 'https://jobs.example/7'};

test('the counts read as one sentence, and a zero is left out', () => {
  const html = countsLine({new_today: 3, shortlist: 38, closing_soon: 2, applications: 4, interviews: 1, follow_ups: 0}, {shortlistOn: true, highFit: 75});
  const text = html.replace(/<[^>]+>/g, '');
  assert.equal(text, '3 new today, 38 on your short list, 2 closing this week, 4 applications and 1 interview.');
  assert.match(html, /href="#\/opportunities\?posted=today&amp;sort=newest"/);
  const quiet = countsLine({new_today: 0, shortlist: 0, closing_soon: 0, applications: 1, interviews: 0, follow_ups: 2}, {shortlistOn: true});
  assert.equal(quiet.replace(/<[^>]+>/g, ''), '1 application and 2 follow-ups due.');
  assert.equal(countsLine({new_today: 0, applications: 0}, {shortlistOn: true}).replace(/<[^>]+>/g, ''), 'Nothing new since yesterday.');
  // With no resume there is no short list to count.
  assert.doesNotMatch(countsLine({new_today: 5, shortlist: 900}, {shortlistOn: false}), /short list/);
});

test('the lead role shows its fit, why, deadline and one primary action', () => {
  const html = leadHtml(JOB, {now: NOW, today: TODAY});
  assert.match(html, /<h2[^>]*>Embedded Firmware Intern<\/h2>/);
  assert.match(html, /Halden Semiconductor/);
  assert.match(html, /New · 2 hours ago/);
  assert.match(html, /Apply by<\/dt><dd>Nov 20<span>8 days<\/span>/);       // over a week away: not yet a warning
  assert.match(leadHtml({...JOB, deadline: '2026-11-16'}, {now: NOW, today: TODAY}), /<dd class="soon">Nov 16<span>4 days<\/span>/);
  assert.match(html, /class="tok">.*4 of 5 skills/);
  assert.match(html, /class="fit-num[^"]*"[^>]*>94</);
  assert.match(html, /Strong fit/);
  assert.equal((html.match(/class="btn primary/g) || []).length, 1);
  assert.match(html, /data-lead-act="review"/);
  // Already tracked: no Save button, the status instead.
  assert.doesNotMatch(leadHtml({...JOB, app_status: 'saved'}, {now: NOW, today: TODAY}), /data-lead-act="save"/);
  // A concern is a warning token, and text from a posting is escaped.
  const risky = leadHtml({...JOB, title: '<b>x</b>', fit: 72, fit_why: [], fit_caution: 'Experience required', deadline: '', badges: []}, {now: NOW, today: TODAY});
  assert.match(risky, /class="tok warn">.*Experience required/);
  assert.match(risky, /&lt;b&gt;x&lt;\/b&gt;/);
  assert.match(risky, /Good fit/);
  assert.doesNotMatch(risky, /Apply by/);
});

test('a short-list row carries the fit figure, one reason in words and the deadline', () => {
  const html = listRow({...JOB, fit: 81, fit_why: [], fit_caution: 'Asks for 2 years', deadline: '2026-11-16', app_status: 'saved'}, {now: NOW, today: TODAY});
  assert.match(html, /data-job="halden:7"/);
  assert.match(html, /class="fit good"/);
  assert.match(html, /class="reason warn">.*Asks for 2 years/);
  assert.match(html, /class="by soon">Nov 16<small>4 days<\/small>/);
  assert.match(html, /Saved/);
  assert.match(listRow(JOB, {now: NOW, today: TODAY}), /class="reason">4 of 5 skills · Intern level</);
});

test('the fit bar separates scores in the range a short list lives in', () => {
  const width = fit => Number(fitMeter(fit).match(/--w:(\d+)%/)[1]);
  assert.ok(width(94) - width(77) >= 30, `${width(94)} vs ${width(77)}`);
  assert.ok(width(40) >= 4);
  assert.equal(fitWord(94), 'Strong fit');
  assert.equal(fitWord(72), 'Good fit');
  assert.equal(fitWord(55), 'Possible fit');
  assert.equal(fitWord(20), 'Weak fit');
  assert.equal(fitWord(null), 'Not scored yet');
});
