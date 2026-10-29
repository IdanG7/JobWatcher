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
  {version: '0.3.12', date: '2026-10-28', items: [
    {icon: 'heart', title: 'More Healthcare roles, by specialty', link: '#/settings?tab=roles',
      text: 'From the job sites of over 200 hospitals, labs, drug makers and more, in nine specialties.'},
    {icon: 'tag', title: 'Pay shows on more roles', link: '#/opportunities',
      text: 'Pay in job descriptions now shows on far more roles and counts for Minimum annual pay.'},
    {icon: 'check', title: 'Licences count toward fit', link: '#/settings?tab=about',
      text: 'Healthcare roles that need a licence you don’t list rank lower. Add yours in About you.'},
    {icon: 'clock', title: 'Say which hours you can work', link: '#/settings?tab=places',
      text: 'Roles stating only other hours, or nights you rule out, rank lower. Filter by hours too.'},
  ]},
  {version: '0.3.11', date: '2026-10-24', items: [
    {icon: 'calendar', title: 'Calendar follows your resume', link: '#/calendar',
      text: 'Deadlines for your resume matches in your boards, plus anything you’ve applied to.'},
    {icon: 'filter', title: 'Cleaner matches for tech boards', link: '#/opportunities',
      text: 'Roles that don’t name a field, like “Illustrator, Intern”, no longer match your resume.'},
    {icon: 'list', title: 'Every past update in What’s new',
      text: 'Open “All updates” on this card to see what changed in earlier versions.'},
  ]},
  {version: '0.3.10', date: '2026-10-24', items: [
    {icon: 'clock', title: 'See how ranking is going', link: '#/opportunities',
      text: 'While Foothold ranks roles for you, Opportunities shows how far along it is and time left.'},
    {icon: 'file', title: 'Your picked targets stay', link: '#/settings?tab=roles',
      text: 'A resume adds its targets and keeps yours; plain software jobs now count for Software.'},
    {icon: 'chart', title: 'Sources follow your boards', link: '#/sources',
      text: 'The Sources page counts roles and employers in your boards, not only finance.'},
    {icon: 'refresh', title: 'Quicker checks after an update',
      text: 'A check during a long re-rank ranks only its new jobs, so it finishes in minutes.'},
  ]},
  {version: '0.3.9', date: '2026-10-24', items: [
    {icon: 'file', title: 'Resumes for tech roles', link: '#/settings?tab=resume',
      text: 'A CS resume now sets Software, AI & Data or Hardware targets, skills and employers.'},
    {icon: 'filter', title: 'Matches follow your fields',
      text: 'With only tech fields chosen, finance roles no longer count as resume matches.'},
    {icon: 'refresh', title: 'Matches update again',
      text: 'One damaged posting no longer stops Foothold from rescoring your matches.'},
  ]},
  {version: '0.3.8', date: '2026-10-23', items: [
    {icon: 'code', title: 'Sources for tech boards', link: '#/sources',
      text: 'Software, AI & Data and Hardware now read 485 tech employers’ own job sites.'},
    {icon: 'filter', title: 'Narrow a tech board by specialty', link: '#/settings?tab=roles',
      text: 'Backend, ML, embedded and more, each polling the employers that hire for it.'},
    {icon: 'check', title: 'Finance board: nothing removed',
      text: 'It keeps every source it had, plus firms that hire for both finance and tech.'},
  ]},
  {version: '0.3.7', date: '2026-10-19', items: [
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
