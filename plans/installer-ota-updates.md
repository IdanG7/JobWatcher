# Windows installer and over-the-air updates — plan (2026-10-12)

## Decisions (from the user)
- **No code-signing certificate for now.** The first install shows SmartScreen ("More info → Run anyway").
  Updates are verified with Jobwatch's own ed25519 key, so they stay safe without a certificate.
  A certificate (e.g. Azure Trusted Signing) can be added later in CI without changing the design.
- **Updates download quietly in the background.** The banner says "Jobwatch X is ready — Restart to update".
  One click installs it, and the open tab reconnects by itself.
- **Retire the ZIP after one bridge release.** That release ships both the ZIP and the installer. A ZIP copy
  that runs it updates itself into the installed app. After that, only the installer is published.
  (0.1.13 and older can't update themselves: their existing banner links to the release page, where
  the installer is the first download.)

## What exists already (no change needed)
- Data lives in `%LOCALAPPDATA%\Jobwatch`, separate from the app files, so replacing the app never touches it.
- The launcher replaces an older running version, and the server holds `running.lock`.
- The sign-in start moves to whichever copy serves the same data folder (`should_repoint_autostart`).
- `/api/update` already checks GitHub's latest release every 6 hours.

## Phase 1 — installed app

1. **Windowless start.** Shortcuts run `runtime\pythonw.exe app\portable_start.py`. Under pythonw
   there is no console, so the launcher writes nothing to stdout and shows startup errors in a
   Windows message box (ctypes `MessageBoxW`).
   *Accept:* starting from the shortcut flashes no window; a forced startup error shows a message box.
2. **Stable port.** The server first tries the port it used last time (saved in the data folder)
   and falls back to a free port. Without this, the browser tab dies on every restart: the origin
   check needs the exact host and port. *Accept:* restart → same URL; port taken → new URL, still starts.
3. **`portable_start.py --stop`.** Reads `instance.json`, POSTs `/api/shutdown` with the right Origin,
   and waits for `running.lock` to be released (capped at 30 s). The installer and uninstaller use it.
   *Accept:* test stops a running server; a no-op when nothing is running.
4. **Inno Setup script `tools/jobwatch.iss`**, built by `build_windows.py` from the same staged folder as the ZIP.
   - Per user, no admin (`PrivilegesRequired=lowest`), installs to `%LOCALAPPDATA%\Programs\Jobwatch`.
   - Fixed AppId. Start menu shortcut; optional desktop shortcut. "Open Jobwatch" checkbox on the last page.
   - App icon: `web/favicon.svg` converted to `.ico` at build time.
   - Before copying files it runs `--stop`, so a running copy never locks them.
   - Uninstall: stops Jobwatch, removes the sign-in start only if it points into the install folder,
     and asks whether to delete the data (default **keep**).
   *Accept:* in CI, a silent install into a temp folder → start → `/api/status` 200 → uninstall → app files gone, data kept.
5. **CI.** Download a pinned Inno Setup with a SHA-256 check (don't rely on the runner image), build
   `Jobwatch-Setup-<version>.exe`, run the install/uninstall check from step 4, and keep the
   existing ZIP verification during the bridge.

## Phase 2 — over-the-air updates

6. **Signing key.** An ed25519 key pair. The public key is committed in `update_key.py`; the private key
   is the GitHub secret `JOBWATCH_UPDATE_KEY` and is never in the repo. `tools/sign_release.py` writes
   `jobwatch-update.json` (version, installer name, size, sha256, notes) and `jobwatch-update.json.sig`.
   Adds the dependency `cryptography` (binary abi3 wheel; ~5 MB in the bundle).
7. **`updater.py`** (state: idle / downloading / ready / failed):
   - Reads the latest release from GitHub and downloads the two manifest files. Accepts only HTTPS
     from `github.com` / `objects.githubusercontent.com`, with size caps.
   - Checks the signature against the built-in key, then that the manifest version equals the
     release tag and is newer than the running version (blocks downgrade and replay).
   - Downloads the installer to `%LOCALAPPDATA%\Jobwatch\updates\` (`.part` → rename), then checks
     its size and sha256. Old downloads are cleaned up; a verified one is reused after a restart.
   - Runs at startup and every 6 hours; network failures stay quiet and are retried later.
8. **API.** `GET /api/update` returns that state. `POST /api/update/apply` re-checks the installer's
   hash, starts it detached (`/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /RELAUNCH`) and shuts the
   server down. The installer stops any leftover copy, replaces the files and relaunches with
   `--no-browser`. Same port, so the tab reconnects.
9. **UI.** The update banner shows "Downloading…", then "Restart to update". After the click, an
   overlay polls `/api/status` until the version changes, then reloads the page. On failure it shows
   the reason and a link to the release page.
10. **Bridge for ZIP copies.** The same updater runs in the ZIP build. Its installer installs to
    Programs, the installed copy takes over the sign-in start (existing repoint rule, same data folder),
    and the first start after the update tells them the old ZIP folder can be deleted.
11. **Release workflow.** Publish the Setup exe, the manifest and its signature; the ZIP only in the
    bridge release. Release notes describe the installer and SmartScreen.

*Testing:* unit tests for the signature (valid, tampered, wrong key), version checks (downgrade, tag
mismatch), host allowlist, size caps and hash mismatch, using fake HTTP. CI end-to-end: build version N
and N+1 with a **test** key built in (`build_windows.py --update-key-file`), install N, point it at a
local feed (`JOBWATCH_UPDATE_FEED`, only honoured in that test build), apply → N+1 serves the same
data on the same port.

## Phase 3 — docs and cleanup
12. README / READ ME FIRST describe the installer; error and update texts stop mentioning `Start Jobwatch.bat`
    for installed copies; after the bridge, CI stops building the ZIP.

## Risks
- Unsigned installers that run silently can trip Windows Defender's heuristics. If that shows up in
  testing, the certificate decision comes back.
- GitHub's unauthenticated API limit (60/hour) is ample at one check every 6 hours.
- The user must create the key once: I generate it locally to a file outside the repo, and they add it as a GitHub secret.

## Release
Version **0.2.0** is the bridge release (installer + ZIP). 0.2.1 onward: installer only.

## Phase 3 implementation (2026-10-12)
- `version.py` is set to **0.2.0**. README, packaged READ ME FIRST and release notes
  explain the installer, SmartScreen, automatic downloads, restart, data preservation,
  uninstall and manual migration from 0.1.13 or earlier.
- Settings uses the Start menu instruction for an installed copy and the batch
  instruction for a ZIP copy. Connection errors use instructions that work for both.
- CI includes and verifies the ZIP only when `APP_VERSION == "0.2.0"`; all later
  versions build with `--no-zip` and publish the installer and signed update files.
- Before tagging a public release, configure the `JOBWATCH_UPDATE_KEY` repository
  secret using the existing private key and retain a secure backup. A main-branch
  push runs the full build and update checks without publishing a release.
