"""Windows notifications for new short-list roles and the morning summary.

Shown through Windows' own PowerShell, so nothing is added to the app. The words of a notification are
passed in the environment and never become part of a command: a posting's title is not trusted text.
"""
import os
import subprocess
import sys
import time
from urllib.parse import quote
from xml.sax.saxutils import escape, quoteattr

# The person at this PC, in subscribers.json (the entry Settings writes when Discord is connected).
OWNER = "desktop"
OWNER_DEFAULTS = {"companies": ["all"], "alert_mode": "fit", "finance_only": False, "reminders": True,
                  "saved_search_alerts": True, "match_alerts": True}
APP_ID = "Foothold.Desktop"
APP_NAME = "Foothold"
TIMEOUT = 20
STATE_SECONDS = 60          # how long an answer about Windows' own switch is kept

# Registers the name Windows shows above the notification (under the user's own registry, no admin rights),
# then shows it or, with FOOTHOLD_TOAST_XML unset, only says whether Windows will show notifications.
SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$id = $env:FOOTHOLD_TOAST_APP
$key = "HKCU:\Software\Classes\AppUserModelId\$id"
if (-not (Test-Path $key)) { New-Item -Path $key -Force | Out-Null }
Set-ItemProperty -Path $key -Name DisplayName -Value $env:FOOTHOLD_TOAST_NAME
[void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
[void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]
$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($id)
if ($env:FOOTHOLD_TOAST_XML) {
  $doc = New-Object Windows.Data.Xml.Dom.XmlDocument
  $doc.LoadXml($env:FOOTHOLD_TOAST_XML)
  $notifier.Show((New-Object Windows.UI.Notifications.ToastNotification $doc))
}
Write-Output "setting=$($notifier.Setting)"
"""

_state = {"at": 0.0, "value": ""}


def powershell():
    """Windows' own PowerShell by its full path (never whatever is first on PATH), or '' when there is none."""
    if sys.platform != "win32":
        return ""
    path = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0",
                        "powershell.exe")
    return path if os.path.exists(path) else ""


def supported():
    return bool(powershell())


def enabled(entry):
    """Whether the person's entry asks for Windows notifications: what they chose in Settings, else on
    when Discord isn't connected (so alerts reach someone who set nothing up) and off when it is."""
    entry = entry or {}
    return bool(entry.get("desktop_notifications", not entry.get("discord_webhook")))


def toast_xml(title, lines=(), url=""):
    """The notification: a title, up to two more lines, and the page a click opens."""
    texts = "".join(f"<text>{escape(str(text)[:200])}</text>" for text in (title, *list(lines)[:2]) if text)
    launch = f" activationType=\"protocol\" launch={quoteattr(url)}" if url.startswith(("http://", "https://")) else ""
    return f"<toast{launch}><visual><binding template=\"ToastGeneric\">{texts}</binding></visual></toast>"


def _run(xml=""):
    """Windows' answer ('Enabled', 'DisabledForUser', ...), or '' when it could not be asked."""
    exe = powershell()
    if not exe:
        return ""
    env = {**os.environ, "FOOTHOLD_TOAST_APP": APP_ID, "FOOTHOLD_TOAST_NAME": APP_NAME}
    env.pop("FOOTHOLD_TOAST_XML", None)
    if xml:
        env["FOOTHOLD_TOAST_XML"] = xml
    try:
        done = subprocess.run(
            [exe, "-NoProfile", "-NonInteractive", "-Command", SCRIPT], env=env, capture_output=True, text=True,
            timeout=TIMEOUT, stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return ""
    if done.returncode != 0:
        return ""
    for line in (done.stdout or "").splitlines():
        if line.startswith("setting="):
            value = line.partition("=")[2].strip()
            _state.update(at=time.time(), value=value)
            return value
    return ""


def windows_state(fresh=False):
    """'on' when Windows will show Foothold's notifications, 'off' when the person has them switched off
    in Windows, 'unknown' when Windows could not be asked."""
    if not supported():
        return "unknown"
    if fresh or time.time() - _state["at"] > STATE_SECONDS:
        _run()
    value = _state["value"]
    return "on" if value == "Enabled" else "off" if value.startswith("Disabled") else "unknown"


def show(title, lines=(), url=""):
    """Show one notification. True when Windows took it and has notifications on. Never raises."""
    return _run(toast_xml(title, lines, url)) == "Enabled"


def roles_notice(roles, dashboard_url=""):
    """(title, lines, url) for the roles one poll found: ``roles`` are (company, title, place, key), best first."""
    base = (dashboard_url or "").rstrip("/")
    if len(roles) == 1:
        company, title, place, key = roles[0]
        return (f"New on your short list: {company}", [title, place],
                f"{base}/#/opportunities?job={quote(key, safe=':')}" if base else "")
    lines = [f"{company}: {title}" for company, title, _, _ in roles[:2]]
    if len(roles) > 2:
        lines[1] += f", and {len(roles) - 2} more"
    return f"{len(roles)} new roles on your short list", lines, f"{base}/#/opportunities" if base else ""
