; ============================================================
;  8AI - Inno Setup script
;
;  Normal installer ......... ISCC 8ai.iss
;  Portable self-extractor .. ISCC /DPortable 8ai.iss
;
;  (build.py runs both automatically; you can also open this
;   file in the Inno Setup IDE and press F9.)
;
;  Expects the PyInstaller output in  dist\8AI\
;  Optional files next to this script:
;     icon.ico   -> used as installer icon
;     Farsi.isl  -> adds a Persian language to the installer
; ============================================================

#define MyAppName "8AI"
#ifndef MyAppVersion
  #define MyAppVersion "2.8.0"
#endif
#define MyAppPublisher "Clubapp"
#define MyAppURL "https://t.me/Clubapp8"
#define MyAppExeName "8AI.exe"
#ifndef SourceDir
  #define SourceDir "dist\8AI"
#endif

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
VersionInfoVersion={#MyAppVersion}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=output
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
#if FileExists("icon.ico")
SetupIconFile=icon.ico
#endif

#ifdef Portable
; ---- Portable: just unpacks into a folder, no registry, no uninstaller
AppId={{A2F6D0B1-93C4-4E57-8B1E-6D7C40F5A912}
OutputBaseFilename={#MyAppName}-{#MyAppVersion}-Portable
DefaultDirName={userdocs}\{#MyAppName}-Portable
UsePreviousAppDir=no
PrivilegesRequired=lowest
Uninstallable=no
CreateUninstallRegKey=no
#else
; ---- Normal installer (per-user or all-users, the user chooses)
AppId={{7D3C9E52-4B1A-4F8E-A6D0-2C5B91E7F304}
OutputBaseFilename={#MyAppName}-{#MyAppVersion}-Setup
DefaultDirName={autopf}\{#MyAppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
#if FileExists("Farsi.isl")
Name: "persian"; MessagesFile: "Farsi.isl"
#endif

#ifndef Portable
[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
#endif

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

#ifdef Portable
[Code]
// Portable mode: this flag makes 8AI keep its settings and chats in <app>\data
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    SaveStringToFile(ExpandConstant('{app}\portable.flag'), '8AI portable mode', False);
end;
#endif
