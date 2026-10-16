# Rename the outside of the Windows app to Foothold

The interface already says Foothold (2026-10-16). This plan renames what people see
outside the browser: the installer wizard, Settings > Apps entry, Start menu and desktop
shortcuts, the ZIP launcher, the icon file, window and message-box titles, READ ME FIRST,
the README and the GitHub release title/notes.

## What changes

| Surface | Before | After |
|---|---|---|
| Installer wizard, Settings > Apps name and publisher | Jobwatch | Foothold |
| Start menu / desktop shortcut | `Jobwatch.lnk` | `Foothold.lnk`; the old `Jobwatch.lnk` is removed on upgrade |
| Shortcut and installer icon | `web/jobwatch.ico` | `web/foothold.ico` (a copy is still installed as `jobwatch.ico`, see risks) |
| ZIP launcher | `Start Jobwatch.bat`, window title Jobwatch | `Start Foothold.bat`, window title Foothold |
| Locally built ZIP | `Jobwatch-Windows.zip`, root folder `Jobwatch/` | `Foothold-Windows.zip`, root folder `Foothold/` |
| Startup error box, launcher console text | Jobwatch | Foothold |
| READ ME FIRST.txt, README.md | Jobwatch | Foothold; folder and file names that stay are named literally |
| GitHub release title and notes | Jobwatch vX | Foothold vX |
| UI hints (`startHint`, offline message, update banner) | "Jobwatch from the Start menu" / "it" | "Foothold from the Start menu" / `Start Foothold.bat` |

## What deliberately stays Jobwatch (internal identifiers)

| Identifier | Why it stays |
|---|---|
| Installer AppId `{1AE8ADC1-…}` | Windows finds the installed copy by it. A new AppId would install a second copy. |
| Setup file name `Jobwatch-Setup-<version>.exe` | **Update channel contract.** Installed copies up to 0.2.5 accept only an installer matching `Jobwatch-Setup-\d+(\.\d+){1,3}\.exe` in the signed manifest (`updater.INSTALLER_NAME`). A `Foothold-Setup-…` file would fail on every existing install with "the update manifest is malformed". |
| `jobwatch-update.json` / `.sig` release assets | Same: old copies look for these exact names. |
| Data folder `%LOCALAPPDATA%\Jobwatch`, `jobwatch.db`, `jobwatch.log` | Left as is (no migration). The running server holds the database, the sign-in start command embeds `--data-dir`, the updater downloads into `<data>\updates`, and the uninstaller offers to delete this exact folder. A migration would touch all four for no visible gain. |
| Install folder `%LOCALAPPDATA%\Programs\Jobwatch` | Upgrades reuse the previous folder anyway; changing the default would only split fresh installs from upgraded ones. It is never shown (no folder page). |
| Sign-in start registry value `HKCU\…\Run\Jobwatch` | Renaming needs a migration in both the app and the uninstaller; shown only in Task Manager's Startup list. Candidate follow-up. |
| `JOBWATCH_*` environment variables and secrets, Python class names | Developer-only. |

## Risks

1. **Update channel breaks for existing installs** if the setup file or manifest is renamed.
   Mitigation: names kept; a new test pins the setup file name to the updater's pattern and the AppId.
   Renaming the setup file later would first need an updater that accepts both names, and copies that
   never update past 0.2.5 would still be stranded.
2. **Duplicate Start menu entries** after upgrade (old `Jobwatch.lnk` plus new `Foothold.lnk`).
   Mitigation: `[InstallDelete]` removes `{autoprograms}\Jobwatch.lnk`, and the desktop `Jobwatch.lnk`
   only when the desktop-shortcut task is selected (that is, only when a Foothold one replaces it).
3. **Start menu pins disappear.** A Windows 11 Start pin of "Jobwatch" points at the removed shortcut.
   Unavoidable with a rename; users re-pin Foothold. Start search for "Jobwatch" no longer finds it.
4. **Taskbar pins lose their icon.** A pinned copy of the old shortcut keeps pointing at
   `app\web\jobwatch.ico`, which the upgrade deletes. Mitigation: the installer also installs
   `foothold.ico` under the old name.
5. **AppId must not change.** Pinned by the new test; the `.iss` comment already says so.
6. **The 0.2.0 ZIP on GitHub is still `Jobwatch-Windows.zip` with `Start Jobwatch.bat`.**
   README keeps those literal names where it describes that published file.
7. **No local Inno Setup.** The installer itself can only be compiled and verified in CI
   (`verify_windows_installer.py`, `verify_windows_update.py`). Locally: ZIP build plus
   `verify_windows_bundle.py`, unit tests, JS tests.

## Steps

1. Tests first: stage contains `Start Foothold.bat`; installer script keeps AppId, keeps the
   setup name the updater accepts, names Foothold, removes the old shortcut, uses `foothold.ico`.
2. Rename `Start Jobwatch.bat` → `Start Foothold.bat`, `web/jobwatch.ico` → `web/foothold.ico`.
3. `tools/jobwatch.iss`: display names, shortcuts, icon paths, old-shortcut cleanup, messages.
4. `tools/build_windows.py`: launcher name, ZIP name and root folder, READ ME FIRST text.
5. `portable_start.py`: message-box title and console text.
6. Verifiers and CI: icon path, ZIP name, release title and notes.
7. README.md.
8. UI strings: `settings.js` `startHint`, `collection-status.js` offline message, `app.js` banners.
9. Verify: Python tests, JS tests, `watcher.py --check`, ZIP build dry run and `verify_windows_bundle.py`.

## Result (2026-10-16, not committed)

- Python: 354 tests pass (`python -m unittest discover`), including 5 new `InstallerScriptTests`
  that pin the AppId, the setup file name the updater accepts, the Foothold names, the old-shortcut
  cleanup and the icon path.
- JS: 30 of 30 tracked tests pass, including the new offline-message assertion. The untracked
  `web/tests/posting-scan.test.js` (dated 2026-10-10) fails on its own: it imports a missing
  `web/js/posting-scan.js`.
- `watcher.py --check`: config ok. `actionlint` on build-windows.yml: ok.
- Build dry run: `tools/build_windows.py` (ZIP only, since no local Inno Setup) built
  `Foothold-Windows.zip` (17.0 MB), with root folder `Foothold/`, `Start Foothold.bat` and `app/web/foothold.ico`.
  `tools/verify_windows_bundle.py` passed on it: the batch file started the app with no window, and polling,
  resume matching and restart persistence all worked.
- Not verified locally: compiling the installer and the installer and update verifiers. CI runs them,
  and `verify_windows_installer.py` now also checks that `Foothold.lnk` replaces `Jobwatch.lnk` and that
  the uninstall removes it.

## Out of scope (follow-ups)

- `dashboard.py` strings that still say Jobwatch: the Discord test/connect messages, the
  "Stop this copy of Jobwatch…" API error shown in Settings, and the console banner and `--help` text.
- Renaming the sign-in start registry value, with migration.
- `docs/ARCHITECTURE.md` and `PRODUCT.md` still describe the product as Jobwatch.
