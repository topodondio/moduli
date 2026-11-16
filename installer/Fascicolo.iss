; Programma di installazione di Fascicolo (Inno Setup 6)
; Si compila da GitHub Actions; in locale: ISCC.exe /DMyAppVersion=0.6.0 installer\Fascicolo.iss

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppName "Fascicolo"
#define MyAppExe "Fascicolo.exe"

[Setup]
AppId={{8E4C2B1A-5F3D-4E7A-9B61-FA5C1C0D2E91}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=topodondio
AppPublisherURL=https://github.com/topodondio/moduli
AppSupportURL=https://github.com/topodondio/moduli
AppUpdatesURL=https://github.com/topodondio/moduli/releases
; installazione per l'utente: non servono i permessi di amministratore e gli aggiornamenti sono silenziosi
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
OutputDir=..\dist
OutputBaseFilename=Fascicolo-Setup-{#MyAppVersion}
SetupIconFile=..\assets\fascicolo.ico
UninstallDisplayIcon={app}\{#MyAppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=force
RestartApplications=no

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "Crea un collegamento sul desktop"; GroupDescription: "Collegamenti:"

[Files]
Source: "..\dist\Fascicolo\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; via le librerie della versione precedente (le pratiche stanno nell'archivio, non qui)
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{group}\Disinstalla {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "Avvia {#MyAppName}"; Flags: nowait postinstall
