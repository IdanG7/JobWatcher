// The posting panel's three tabs: the role itself, applying to it, and tracking the application.
// The header and the tabs stay put; only the selected tab's panel scrolls.
export const TABS = [
  {key: 'role', label: 'Role', icon: 'file'},
  {key: 'apply', label: 'Apply', icon: 'edit'},
  {key: 'track', label: 'Track', icon: 'kanban'},
];

/** `icon(name, size)` draws each tab's icon (ui.js); without it the tabs are words alone. */
export function tabsHtml(active, icon = () => '') {
  return `<div class="dr-tabs" role="tablist" aria-label="Posting sections">${TABS.map(({key, label, icon: name}) => {
    const on = key === active;
    return `<button type="button" role="tab" class="dr-tab" id="dr-tab-${key}" data-tab="${key}" aria-controls="dr-panel-${key}" aria-selected="${on}" tabindex="${on ? 0 : -1}">${icon(name, 14)}${label}</button>`;
  }).join('')}</div>`;
}

export function panelHtml(key, active, html) {
  return `<div class="dr-panel" role="tabpanel" id="dr-panel-${key}" aria-labelledby="dr-tab-${key}"${key === active ? '' : ' hidden'}>${html}</div>`;
}

/** The tab an arrow, Home or End key moves to from `active`; null for any other key. */
export function nextTab(active, key) {
  const keys = TABS.map(t => t.key);
  const i = keys.indexOf(active);
  const to = {ArrowRight: (i + 1) % keys.length, ArrowLeft: (i + keys.length - 1) % keys.length, Home: 0, End: keys.length - 1}[key];
  return to === undefined ? null : keys[to];
}
