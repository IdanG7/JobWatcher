import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';

import {RELEASE_NOTES} from '../js/release-notes.js';
import {icon} from '../js/ui.js';
import {cardMarkup, cardToShow, compareVersions, earlierReleases, pendingReleases, recentReleases, rollSegments} from '../js/whats-new.js';

const release = (version, n = 2) => ({version, date: '2026-10-01', items: Array.from({length: n}, (_, i) => ({icon: 'spark', title: `${version} change ${i + 1}`, text: 'One line.'}))});
// Out of order on purpose: the card sorts newest first itself.
const NOTES = [release('0.3.4'), release('0.3.6'), release('0.3.3'), release('0.3.5')];
const versions = list => list.map(r => r.version);

test('versions compare by number, not as text', () => {
  assert.equal(compareVersions('0.3.10', '0.3.9'), 1);
  assert.equal(compareVersions('0.3', '0.3.0'), 0);
  assert.equal(compareVersions('0.2.5', '0.3.0'), -1);
  assert.equal(compareVersions('v1.0.0', '0.9.9'), 1);
  assert.equal(compareVersions('', '0.0.1'), -1);
});

test('after an update the card lists every release since the last one closed, newest first', () => {
  assert.deepEqual(versions(pendingReleases('0.3.5', '0.3.3', NOTES)), ['0.3.5', '0.3.4']);
  assert.deepEqual(versions(pendingReleases('0.3.4', '0.3.3', NOTES)), ['0.3.4']);
});

test('an existing install meeting the card for the first time sees only this version’s notes', () => {
  assert.deepEqual(versions(pendingReleases('0.3.5', null, NOTES)), ['0.3.5']);
  assert.deepEqual(pendingReleases('0.3.7', null, NOTES), []);        // no entry for this version: no card
});

test('closed, downgraded or not yet released: nothing shows', () => {
  assert.deepEqual(pendingReleases('0.3.5', '0.3.5', NOTES), []);
  assert.deepEqual(pendingReleases('0.3.4', '0.3.5', NOTES), []);
  // Notes written ahead of the version bump wait until that version runs.
  assert.deepEqual(versions(pendingReleases('0.3.5', '0.3.4', NOTES)), ['0.3.5']);
});

test('a version without notes still shows the releases it skipped; at most three', () => {
  assert.deepEqual(versions(pendingReleases('0.3.7', '0.3.4', NOTES)), ['0.3.6', '0.3.5']);
  assert.deepEqual(versions(pendingReleases('0.3.6', '0.1.0', NOTES)), ['0.3.6', '0.3.5', '0.3.4']);
});

test('reopening shows this version and the ones before it, never a newer one', () => {
  assert.deepEqual(versions(recentReleases('0.3.5', NOTES)), ['0.3.5', '0.3.4', '0.3.3']);
  assert.deepEqual(versions(recentReleases('0.3.3', NOTES)), ['0.3.3']);
});

test('“All updates” holds every release before the ones on the card, newest first, never a newer one', () => {
  assert.deepEqual(versions(earlierReleases('0.3.6', pendingReleases('0.3.6', null, NOTES), NOTES)), ['0.3.5', '0.3.4', '0.3.3']);
  assert.deepEqual(versions(earlierReleases('0.3.4', pendingReleases('0.3.4', '0.3.3', NOTES), NOTES)), ['0.3.3']);
  assert.deepEqual(versions(earlierReleases('0.3.7', pendingReleases('0.3.7', '0.3.4', NOTES), NOTES)), ['0.3.4', '0.3.3']);
  // More than three skipped: the ones the card leaves out are still there.
  assert.deepEqual(versions(earlierReleases('0.3.6', pendingReleases('0.3.6', '0.1.0', NOTES), NOTES)), ['0.3.3']);
  assert.deepEqual(earlierReleases('0.3.5', recentReleases('0.3.5', NOTES), NOTES), []);       // the card has them all
});

test('the card shows once: closing it marks the version, and the next update shows only what is new', () => {
  let info = {version: '0.3.4', seen: '0.3.3'};
  const shown = cardToShow(info, 'overview', NOTES);
  assert.deepEqual({current: shown.current, seen: shown.seen, releases: versions(shown.releases)},
    {current: '0.3.4', seen: '0.3.3', releases: ['0.3.4']});
  info = {...info, seen: shown.current};                   // POST /api/whats-new/seen {version: '0.3.4'}
  assert.equal(cardToShow(info, 'overview', NOTES), null);        // a fresh run, or the app window
  assert.deepEqual(versions(cardToShow({version: '0.3.5', seen: info.seen}, 'overview', NOTES).releases), ['0.3.5']);
});

test('first-run setup and a missing answer show no card', () => {
  assert.equal(cardToShow({version: '0.3.5', seen: '0.3.4'}, 'welcome', NOTES), null);
  assert.equal(cardToShow(null, 'overview', NOTES), null);
  assert.equal(cardToShow({}, 'overview', NOTES), null);
});

test('the version rolls over from the last one closed', () => {
  assert.deepEqual(rollSegments('0.3.3', '0.3.4'), [{text: '0', from: null}, {text: '3', from: null}, {text: '4', from: '3'}]);
  // Everything after the first change rolls: 0.3.9 → 0.4.0.
  assert.deepEqual(rollSegments('0.3.9', '0.4.0'), [{text: '0', from: null}, {text: '4', from: '3'}, {text: '0', from: '9'}]);
  // Unknown start: the last segment rolls in from blank rather than from a guessed version.
  assert.deepEqual(rollSegments(null, '0.3.4').map(s => s.from), [null, null, '']);
  assert.deepEqual(rollSegments('0.3', '0.3.1').map(s => s.from), [null, null, '']);
  assert.deepEqual(rollSegments('0.3.4', '0.3.4').map(s => s.from), [null, null, null]);
});

test('the card escapes notes, links rows that have a place, and labels each release when there are several', () => {
  const notes = [{version: '0.3.5', date: '2026-10-20', items: [
    {icon: 'mail', title: 'Letters <b>', text: 'Fish & chips', link: '#/settings?tab=letters'},
    {icon: 'file', title: 'Plain', text: 'No link here.'},
  ]}, release('0.3.4')];
  const html = cardMarkup({current: '0.3.5', seen: '0.3.3', releases: notes});
  assert.match(html, /role="dialog" aria-modal="false" aria-labelledby="wn-title"/);
  // The rolling digit's old value is CSS content, so the heading's text is just the version.
  assert.equal(html.match(/<h2[^>]*>(.*?)<\/h2>/s)[1].replace(/<[^>]+>/g, ''), 'What’s new in Foothold 0.3.5');
  assert.match(html, /data-from="3"/);
  assert.match(html, /Letters &lt;b&gt;/);
  assert.match(html, /Fish &amp; chips/);
  assert.match(html, /<a class="wn-item" href="#\/settings\?tab=letters">/);
  assert.match(html, /<div class="wn-item">.*Plain/s);
  assert.equal((html.match(/class="wn-release-v"/g) || []).length, 2);
  assert.match(html, /New since 0\.3\.3/);
  assert.match(html, /class="wn-roll"/);
  assert.match(html, /Find it again in Settings › System/);
  assert.equal((html.match(/data-wn-close/g) || []).length, 2);      // the × and "Got it"
});

test('reopened on purpose: no roll, no hint, one release unlabelled with its date', () => {
  const html = cardMarkup({current: '0.3.4', seen: '0.3.4', releases: [release('0.3.4')], manual: true});
  assert.doesNotMatch(html, /class="wn-roll"/);
  assert.doesNotMatch(html, /Find it again/);
  assert.doesNotMatch(html, /wn-release-v/);
  assert.match(html, /Released /);
});

test('“All updates” is a button after this release that unfolds the earlier ones, each with its version and date', () => {
  const earlier = [release('0.3.5'), {...release('0.3.4'), date: '2026-09-28'}];
  const html = cardMarkup({current: '0.3.6', seen: '0.3.6', releases: [release('0.3.6')], earlier, manual: true});
  const button = html.match(/<button([^>]*data-wn-more[^>]*)>(.*?)<\/button>/s);
  assert.ok(button, 'a real button');
  assert.match(button[1], /type="button"/);
  assert.match(button[1], /aria-expanded="false" aria-controls="wn-earlier"/);
  assert.match(button[2], /All updates/);
  assert.match(button[2], />2 earlier</);
  const region = html.slice(html.indexOf('id="wn-earlier"'));
  assert.ok(html.indexOf('data-wn-more') < html.indexOf('id="wn-earlier"'), 'the list follows its button');
  assert.match(region, /^id="wn-earlier" inert>/);       // folded: out of the tab order and screen readers
  assert.doesNotMatch(region, /0\.3\.6 change/);
  assert.match(region, /0\.3\.5 change 1.*0\.3\.4 change 1/s);
  assert.match(region, /<h3 class="wn-release-v">0\.3\.4 <time datetime="2026-09-28">/);
  assert.equal((html.match(/class="wn-release-v"/g) || []).length, 2);      // this release is the title
  // Nothing earlier, nothing to unfold.
  assert.doesNotMatch(cardMarkup({current: '0.3.6', releases: [release('0.3.6')]}), /data-wn-more|wn-earlier/);
});

test('release notes follow the rules for the card', () => {
  const parse = v => /^\d+\.\d+\.\d+$/.test(v);
  const blank = icon('no-such-icon');
  RELEASE_NOTES.forEach((r, i) => {
    assert.ok(parse(r.version), `${r.version}: versions are like 0.3.5`);
    if (i) assert.equal(compareVersions(RELEASE_NOTES[i - 1].version, r.version), 1, `${r.version}: newest first, one entry each`);
    assert.ok(!r.date || /^\d{4}-\d{2}-\d{2}$/.test(r.date), `${r.version}: date is YYYY-MM-DD`);
    assert.ok(r.items.length >= 2 && r.items.length <= 4, `${r.version}: 2 to 4 items`);
    for (const item of r.items) {
      assert.ok(item.title && item.title.length <= 40, `${r.version}: “${item.title}” is a title of at most 40 characters`);
      assert.ok(item.text && item.text.length <= 90, `${r.version}: “${item.text}” is a line of at most 90 characters`);
      assert.notEqual(icon(item.icon), blank, `${r.version}: icon “${item.icon}” is in web/js/ui.js`);
      assert.ok(!item.link || /^#\/[a-z]/.test(item.link), `${r.version}: links are routes like #/settings?tab=letters`);
    }
  });
});

test('the running version has release notes', () => {
  const version = readFileSync(new URL('../../version.py', import.meta.url), 'utf8').match(/APP_VERSION\s*=\s*"([^"]+)"/)[1];
  assert.ok(RELEASE_NOTES.some(r => r.version === version),
    `version.py is ${version}: add its entry to web/js/release-notes.js so the What’s new card has something to show`);
});
