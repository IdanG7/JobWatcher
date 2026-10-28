import assert from 'node:assert/strict';
import {test} from 'node:test';

import {
  age, buildHash, cleanParams, cleanQuote, cycleLabel, daysUntil, deadlineText, descriptionHtml, esc, fitBand, followTop,
  levelText, licenceText, niceMax,
  parseHash, safeUrl, sourceName, toggleListParam,
} from '../js/lib.js';

test('escaping and URL safety', () => {
  assert.equal(esc('<a href="x">&\'</a>'), '&lt;a href=&quot;x&quot;&gt;&amp;&#39;&lt;/a&gt;');
  assert.equal(safeUrl('javascript:alert(1)'), '#');
  assert.equal(safeUrl('https://jobs.rbc.com/x'), 'https://jobs.rbc.com/x');
});

test('URL state round-trips filters (back button / shareable views)', () => {
  const hash = buildHash(['opportunities'], {category: 'investment_banking', location: 'toronto,new_york', page: 2, empty: ''});
  assert.equal(hash, '#/opportunities?category=investment_banking&location=toronto%2Cnew_york&page=2');
  assert.deepEqual(parseHash(hash), {path: ['opportunities'], params: {category: 'investment_banking', location: 'toronto,new_york', page: '2'}});
  assert.deepEqual(parseHash(''), {path: ['overview'], params: {}});
  assert.deepEqual(parseHash('#/companies/rbc'), {path: ['companies', 'rbc'], params: {}});
  assert.deepEqual(cleanParams({a: 0, b: false, c: null, d: ['x', 'y']}), {a: '0', d: 'x,y'});
});

test('list params toggle like filter chips', () => {
  assert.equal(toggleListParam('', 'toronto'), 'toronto');
  assert.equal(toggleListParam('toronto,new_york', 'toronto'), 'new_york');
  assert.equal(toggleListParam('toronto', 'chicago'), 'toronto,chicago');
});

test('ages and deadlines', () => {
  const now = Date.parse('2026-10-10T12:00:00Z');
  assert.equal(age(now / 1000 - 3 * 3600, now), '3h');
  assert.equal(age(now / 1000 - 3 * 86400, now), '3d');
  assert.equal(age(null, now), '—');
  const today = new Date(2026, 9, 10);
  assert.equal(daysUntil('2026-10-13', today), 3);
  assert.equal(deadlineText('2026-10-11', today), 'Tomorrow');
  assert.equal(deadlineText('2026-10-01', today), 'Closed Oct 1');
  assert.equal(deadlineText('2026-11-20', today), 'Nov 20');
});

test('labels, bands and axis maths', () => {
  assert.equal(cycleLabel('summer_2027'), 'Summer 2027');
  assert.equal(cycleLabel('new_grad_2027'), 'New Grad 2027');
  assert.equal(cycleLabel('off_cycle_2027'), 'Off-Cycle 2027');
  assert.equal(fitBand(91), 'high');
  assert.equal(fitBand(72), 'good');
  assert.equal(fitBand(10), 'low');
  assert.equal(niceMax(37), 40);
  assert.equal(niceMax(1234), 1500);
});

test('a side panel taller than the window follows the page to its end and back to its start', () => {
  const box = {base: 68, height: 1276, viewport: 860};      // 16px gap: lowest top is 860 - 1276 - 16
  assert.equal(followTop(68, 100, box), -32);               // scrolling down moves it with the page
  assert.equal(followTop(-400, 100, box), -432);            // ...until its end is in view
  assert.equal(followTop(-432, 300, box), -432);            // then it stays put
  assert.equal(followTop(-432, -100, box), -332);           // scrolling up brings its start back
  assert.equal(followTop(0, -200, box), 68);                // ...and pins it under the nav
  assert.equal(followTop(-300, 0, {...box, height: 600}), 68);   // a panel that fits stays pinned
});

test('posting text reads cleanly: levels said once, quotes cut at whole words, readable sources', () => {
  assert.equal(levelText({level_label: 'Intern', stage: 'internship'}), 'Intern');
  assert.equal(levelText({level_label: 'Associate', stage: 'experienced'}), 'Associate · Experienced hire');
  assert.equal(levelText({stage: 'new_grad'}), 'New grad program');
  assert.equal(levelText({}), '');
  assert.equal(cleanQuote('ion reimbursement\n\n Posting End Date: \n\n16 Oct 2026 * Jo'), '…reimbursement Posting End Date: 16 Oct 2026…');
  assert.equal(cleanQuote('Candidates must be enrolled in a degree program.'), 'Candidates must be enrolled in a degree program.');
  assert.equal(cleanQuote(''), '');
  assert.ok(cleanQuote('word '.repeat(80), 40).length <= 42);
  assert.equal(sourceName('GitHub · Automated-List-Of-Summer-2027-and-Fall-2026-Tech-Internships'), 'GitHub · Summer 2027 and Fall 2026 Tech Internships');
  assert.equal(sourceName('Wells Fargo Careers'), 'Wells Fargo Careers');
  assert.equal(sourceName('LinkedIn · Toronto · Finance'), 'LinkedIn · Toronto · Finance');
});

test('a posting’s licences and certifications read by their labels', () => {
  const defs = [{key: 'rn', label: 'Registered Nurse (RN)', kind: 'licence'}, {key: 'bls', label: 'BLS / CPR', kind: 'certification'},
    {key: 'acls', label: 'ACLS', kind: 'certification'}];
  assert.deepEqual(licenceText({required: ['rn'], certifications: ['bls', 'acls']}, defs),
    {licences: 'Registered Nurse (RN)', certifications: 'BLS / CPR · ACLS'});
  // before /api/meta arrives, the key stands in
  assert.deepEqual(licenceText({required: ['respiratory_therapist']}), {licences: 'RESPIRATORY THERAPIST', certifications: ''});
  // postings on other boards carry no licences
  assert.deepEqual(licenceText(undefined, defs), {licences: '', certifications: ''});
});

test('descriptions read as paragraphs, tight lists and small headings, not a column of spaced-out lines', () => {
  // a career site's list: every bullet set apart by a blank line, one wrapped mid-sentence
  assert.equal(descriptionHtml('Responsibilities\n\n• Build models\n\n• Write reports on\nquarterly results\n\n• Present findings'),
    '<h4 class="desc-head">Responsibilities</h4><ul><li>Build models</li><li>Write reports on quarterly results</li><li>Present findings</li></ul>');
  assert.equal(descriptionHtml('3. Third\n4) Fourth'), '<ol start="3"><li>Third</li><li>Fourth</li></ol>');
  // blank lines padded with spaces, nbsp and zero-width characters still end a paragraph; runs of spaces close up
  assert.equal(descriptionHtml('First   line.\n   ​\n\n\nSecond line.'), '<p>First line.</p><p>Second line.</p>');
  // "Label: value" lines are text, not headings
  assert.equal(descriptionHtml('Location: Toronto\nType: Full-time'), '<p>Location: Toronto<br>Type: Full-time</p>');
  // a form's labels over their values read as one line each, grouped; a code is a value, never a heading
  assert.equal(descriptionHtml('Job ID\n\n26WD101684\n\nWork Location\n\nToronto, Ontario'),
    '<p class="desc-facts"><span class="desc-label">Job ID</span> 26WD101684<br><span class="desc-label">Work Location</span> Toronto, Ontario</p>');
  // a "Label:" heading's value under it, a blank line apart (Eightfold pages), is a value, not another heading
  assert.equal(descriptionHtml('Company:\n\nQualcomm Canada ULC\n\nJob Area:\n\nInterns Group\n\nOverview:\n\nQualcomm is a company of inventors.'),
    '<p class="desc-facts"><span class="desc-label">Company</span> Qualcomm Canada ULC<br><span class="desc-label">Job Area</span> Interns Group'
    + '<br><span class="desc-label">Overview</span> Qualcomm is a company of inventors.</p>');
  const long = 'You will support the desk with research, models and client materials every day.';
  assert.equal(descriptionHtml(`What you'll do:\n${long}`), `<h4 class="desc-head">What you&#39;ll do</h4><p>${long}</p>`);
  // a short last line is not a heading over nothing
  assert.equal(descriptionHtml('We are hiring.\n\nApply now'), '<p>We are hiring.</p><p>Apply now</p>');
  // the posting's text is escaped, never markup
  assert.equal(descriptionHtml('<script>alert(1)</script>\r\n- <b>bold</b>'), '<p>&lt;script&gt;alert(1)&lt;/script&gt;</p><ul><li>&lt;b&gt;bold&lt;/b&gt;</li></ul>');
  assert.equal(descriptionHtml(''), '');
  assert.equal(descriptionHtml(null), '');
});
