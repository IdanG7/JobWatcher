// What changed in each release, for the "What's new" card that opens once after an install or
// update (web/js/whats-new.js). Newest first, one entry per release.
//
// Writing an entry at release time:
// - `version` matches APP_VERSION in version.py. An entry for a version that isn't running yet
//   never shows, so it can be written before version.py is bumped.
// - 2 to 4 items, most useful first. `title` names the change in a few words (at most 40
//   characters); `text` says what it means for the user in a line (at most 90, two lines on the card).
// - `icon` is a name from ICONS in web/js/ui.js. `link` is optional: a route such as
//   '#/settings?tab=letters' that opens where the change lives.
// web/tests/whats-new.test.js checks these rules.
export const RELEASE_NOTES = [
  // ---- 0.3.5: write this entry when 0.3.5 is released, in the same shape as 0.3.4 below.

  {version: '0.3.4', date: '2026-10-18', items: [
    {icon: 'mail', title: 'Cover letters from your resume', link: '#/settings?tab=letters',
      text: 'A past letter sets your voice; your resume adds your current roles and credentials.'},
    {icon: 'check', title: 'See what a letter covers',
      text: 'It marks which of the posting’s asks it answers, and finds who to address it to.'},
    {icon: 'file', title: 'Full descriptions on open', link: '#/opportunities',
      text: 'Opening a LinkedIn or career-page listing fetches its full text, laid out to read.'},
  ]},
];
