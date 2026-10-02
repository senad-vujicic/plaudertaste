; Inno-Setup-Skript für den Plaudertaste-Installer. Aufruf über packaging/build.py,
; das AppVersion und ModelRepos (Hugging-Face-Ordner, mit ";" getrennt) übergibt.

#ifndef AppVersion
  #error AppVersion fehlt – bitte über packaging/build.py bauen
#endif

[Setup]
AppId={{6F2C1B7E-4E7A-4C55-9C1E-5D3B8A6F2B10}
AppName=Plaudertaste
AppVersion={#AppVersion}
AppPublisher=Senad Vujicic
AppPublisherURL=https://github.com/senad-vujicic/plaudertaste
; Nur für den aktuellen Benutzer: keine Admin-Rechte, {autopf} = %LOCALAPPDATA%\Programs
PrivilegesRequired=lowest
DefaultDirName={autopf}\Plaudertaste
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\build\plaudertaste.ico
UninstallDisplayIcon={app}\Plaudertaste.exe
; Eigener Ordner mit genau der einen Datei, die auf GitHub hochgeladen wird. Der Name bleibt
; immer gleich, damit der Download-Link im README stets die neueste Version liefert.
OutputDir=..\release
OutputBaseFilename=Plaudertaste-Setup
Compression=lzma2/max
SolidCompression=yes
LZMANumBlockThreads=4
WizardStyle=modern
; Laufende Plaudertaste beenden wir selbst (StopRunningApp) – ohne Rückfrage-Dialog.
CloseApplications=no
VersionInfoVersion={#AppVersion}

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\Plaudertaste\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"

[Icons]
Name: "{autoprograms}\Plaudertaste"; Filename: "{app}\Plaudertaste.exe"
Name: "{autodesktop}\Plaudertaste"; Filename: "{app}\Plaudertaste.exe"; Tasks: desktopicon

[Registry]
; Legt nichts an – entfernt aber beim Deinstallieren den Autostart-Eintrag der App.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "Plaudertaste"; Flags: dontcreatekey uninsdeletevalue

[Run]
Filename: "{app}\Plaudertaste.exe"; Description: "{cm:LaunchProgram,Plaudertaste}"; Flags: nowait postinstall skipifsilent

[Code]
{ Beendet Plaudertaste samt Download-Prozess, damit keine Datei gesperrt bleibt.
  Kein Datenverlust: Einstellungen und Wörterbuch sind sofort gespeichert. }
procedure StopRunningApp();
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM Plaudertaste.exe', '', SW_HIDE,
    ewWaitUntilTerminated, ResultCode);
  Sleep(500);  { Windows gibt die Dateien kurz nach Prozessende frei }
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopRunningApp();
  Result := '';
end;

function ModelCacheDir(): String;
begin
  Result := GetEnv('HF_HUB_CACHE');
  if Result = '' then
  begin
    Result := GetEnv('HF_HOME');
    if Result <> '' then
      Result := Result + '\hub'
    else
      Result := ExpandConstant('{%USERPROFILE}') + '\.cache\huggingface\hub';
  end;
end;

{ Löscht nur die Ordner unserer Modelle, nicht den restlichen Hugging-Face-Cache. }
procedure DeleteOurModels();
var
  Repos, Repo: String;
  Split: Integer;
begin
  Repos := '{#ModelRepos}' + ';';
  while Repos <> '' do
  begin
    Split := Pos(';', Repos);
    Repo := Copy(Repos, 1, Split - 1);
    Delete(Repos, 1, Split);
    if Repo <> '' then
    begin
      StringChangeEx(Repo, '/', '--', True);
      DelTree(ModelCacheDir() + '\models--' + Repo, True, True, True);
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then  { nach der Bestätigung, vor dem Löschen }
    StopRunningApp();
  if CurUninstallStep = usPostUninstall then
    if SuppressibleMsgBox('Auch Einstellungen, Wörterbuch, Statistik und die heruntergeladenen ' +
         'Sprachmodelle löschen?' + #13#10#13#10 + 'Wähle "Nein", wenn du Plaudertaste später ' +
         'wieder installieren möchtest.', mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES then
    begin
      DelTree(ExpandConstant('{userappdata}\Plaudertaste'), True, True, True);
      DelTree(ExpandConstant('{localappdata}\Plaudertaste'), True, True, True);
      DeleteOurModels();
    end;
end;
