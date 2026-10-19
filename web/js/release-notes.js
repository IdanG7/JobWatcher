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
  {version: '0.3.6', date: '2026-10-19', items: [
    {icon: 'spark', title: 'Pages load up to 8× faster',
      text: 'Today, Opportunities and Analytics are kept ready, so moving between them is instant.'},
    {icon: 'monitor', title: 'Opens in your default browser',
      text: 'Foothold’s window uses your usual browser: no new profile, banners or sign-ins.'},
  ]},
  {version: '0.3.5', date: '2026-10-19', items: [
    {icon: 'monitor', title: 'Foothold in its own window',
      text: 'No browser tab or address bar; links to postings still open in your usual browser.'},
    {icon: 'edit', title: 'Letters write in the background',
      text: 'A bar shows each step; keep browsing and Foothold tells you when it’s ready.'},
    {icon: 'clock', title: 'Faster letters after the first', link: '#/settings?tab=letters',
      text: 'Your corrected past letter is kept, so later letters start writing straight away.'},
    {icon: 'file', title: 'More full LinkedIn descriptions', link: '#/opportunities',
      text: 'Top LinkedIn matches get their full text in the background, for truer fit and pay.'},
  ]},

  {version: '0.3.4', date: '2026-10-18', items: [
    {icon: 'mail', title: 'Cover letters from your resume', link: '#/settings?tab=letters',
      text: 'A past letter sets your voice; your resume adds your current roles and credentials.'},
    {icon: 'check', title: 'See what a letter covers',
      text: 'It marks which of the posting’s asks it answers, and finds who to address it to.'},
    {icon: 'file', title: 'Full descriptions on open', link: '#/opportunities',
      text: 'Opening a LinkedIn or career-page listing fetches its full text, laid out to read.'},
  ]},
];
