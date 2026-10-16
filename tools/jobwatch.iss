; Foothold per-user installer (no administrator rights).
; Built by tools/build_windows.py --installer, which passes:
;   /DAppVersion=<version.py>  /DStageDir=<staged app folder>  /DOutputDir=<dist>
; Data lives in %LOCALAPPDATA%\Jobwatch, outside the install folder, so
; installing, updating and uninstalling never touch it unless asked.
; Foothold was called Jobwatch. Installed copies still find their data, program
; folder and updates under that name, so only what people see says Foothold.

#ifndef AppVersion
  #error AppVersion is required
#endif
#ifndef StageDir
  #error StageDir is required
#endif
#ifndef OutputDir
  #define OutputDir "."
#endif

#define Pythonw "{app}\runtime\pythonw.exe"
#define Launcher "{app}\app\portable_start.py"

[Setup]
; Never change AppId: Windows uses it to find the installed copy to update.
AppId={{1AE8ADC1-F27E-4DCC-AA4E-691280798458}
AppName=Foothold
AppVersion={#AppVersion}
AppVerName=Foothold {#AppVersion}
AppPublisher=Foothold
AppPublisherURL=https://github.com/IdanG7/JobWatcher
AppUpdatesURL=https://github.com/IdanG7/JobWatcher/releases
VersionInfoVersion={#AppVersion}
PrivilegesRequired=lowest
; The program folder keeps the old name too; upgrades reuse the existing folder.
DefaultDirName={autopf}\Jobwatch
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
UsedUserAreasWarning=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern
SetupIconFile={#StageDir}\app\web\foothold.ico
UninstallDisplayIcon={app}\app\web\foothold.ico
UninstallDisplayName=Foothold
OutputDir={#OutputDir}
; Never rename: installed copies up to 0.2.5 only accept an update named Jobwatch-Setup-<version>.exe.
OutputBaseFilename=Jobwatch-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
; Foothold is stopped by its own --stop below; the Restart Manager would only
; ask about unrelated Python processes.
CloseApplications=no
RestartApplications=no

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked

[InstallDelete]
; Replace the program completely: files a release removed must not linger.
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\runtime"
; The shortcuts were called Jobwatch: replace them instead of adding a second entry.
; The desktop one goes only when a Foothold one replaces it.
Type: files; Name: "{autoprograms}\Jobwatch.lnk"
Type: files; Name: "{autodesktop}\Jobwatch.lnk"; Tasks: desktopicon

[Files]
Source: "{#StageDir}\app\*"; DestDir: "{app}\app"; Flags: recursesubdirs ignoreversion
Source: "{#StageDir}\runtime\*"; DestDir: "{app}\runtime"; Flags: recursesubdirs ignoreversion
Source: "{#StageDir}\manifest.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#StageDir}\READ ME FIRST.txt"; DestDir: "{app}"; Flags: ignoreversion
; Taskbar pins copied from the old Jobwatch shortcut still show the icon by its old name.
Source: "{#StageDir}\app\web\foothold.ico"; DestDir: "{app}\app\web"; DestName: "jobwatch.ico"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Foothold"; Filename: "{#Pythonw}"; Parameters: """{#Launcher}"""; WorkingDir: "{app}"; IconFilename: "{app}\app\web\foothold.ico"; Comment: "Open your Foothold dashboard"
Name: "{autodesktop}\Foothold"; Filename: "{#Pythonw}"; Parameters: """{#Launcher}"""; WorkingDir: "{app}"; IconFilename: "{app}\app\web\foothold.ico"; Comment: "Open your Foothold dashboard"; Tasks: desktopicon

[Run]
Filename: "{#Pythonw}"; Parameters: """{#Launcher}"""; WorkingDir: "{app}"; Description: "Open Foothold"; Flags: postinstall nowait skipifsilent
; An in-app update runs this installer silently with /RELAUNCH: start again without a new browser tab.
Filename: "{#Pythonw}"; Parameters: """{#Launcher}"" --no-browser --after-update"; WorkingDir: "{app}"; Flags: nowait runhidden; Check: RelaunchRequested

[UninstallRun]
Filename: "{#Pythonw}"; Parameters: """{#Launcher}"" --stop"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; RunOnceId: "StopJobwatch"

[UninstallDelete]
; Python writes __pycache__ folders next to the program files.
Type: filesandordirs; Name: "{app}"

[Code]
const
  RunKey = 'Software\Microsoft\Windows\CurrentVersion\Run';

function RelaunchRequested: Boolean;
begin
  Result := ExpandConstant('{param:RELAUNCH|0}') = '1';
end;

// Stop a running copy before its files are replaced.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
begin
  Result := '';
  if FileExists(ExpandConstant('{#Pythonw}')) then
    if not Exec(ExpandConstant('{#Pythonw}'), '"' + ExpandConstant('{#Launcher}') + '" --stop',
                ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, Code) or (Code <> 0) then
      Result := 'Foothold is still running and could not be stopped. Stop it in Settings > Background, then run Setup again.';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Command, Data: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    // Remove the sign-in start only when it belongs to this installation. Its value
    // keeps the old name Jobwatch (dashboard.AUTOSTART_NAME).
    if RegQueryStringValue(HKCU, RunKey, 'Jobwatch', Command) and
       (Pos(Lowercase(ExpandConstant('{app}')), Lowercase(Command)) > 0) then
      RegDeleteValue(HKCU, RunKey, 'Jobwatch');
  end;
  if CurUninstallStep = usPostUninstall then
  begin
    Data := ExpandConstant('{localappdata}\Jobwatch');
    if DirExists(Data) and not UninstallSilent then
      if MsgBox('Also delete your Foothold data?' + #13#10#13#10 +
                'This removes your profile, resume, applications, notes and settings in' + #13#10 +
                Data + #13#10#13#10 +
                'Choose No to keep them for a later reinstall.',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(Data, True, True, True);
  end;
end;
