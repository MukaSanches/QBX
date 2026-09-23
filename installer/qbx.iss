#define MyAppName "QBX"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "QBX Project"
#define MyAppExeName "QBX.exe"

[Setup]
AppId={{D58ED585-8AEC-4A02-BA9D-6D877E45B9C6}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\QBX
DefaultGroupName=QBX
DisableProgramGroupPage=yes
OutputDir=..\installer_output
OutputBaseFilename=QBX-Setup-2.0.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayIcon={app}\QBX.exe
ChangesAssociations=yes

[Files]
Source: "..\dist\QBX.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\qbx-cli.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\QBX"; Filename: "{app}\QBX.exe"
Name: "{group}\QBX Command Line"; Filename: "{cmd}"; Parameters: "/K ""{app}\qbx-cli.exe"" --help"
Name: "{autodesktop}\QBX"; Filename: "{app}\QBX.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Registry]
Root: HKCR; Subkey: ".qbx"; ValueType: string; ValueName: ""; ValueData: "QBXArchive"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "QBXArchive"; ValueType: string; ValueName: ""; ValueData: "QBX Archive"; Flags: uninsdeletekey
Root: HKCR; Subkey: "QBXArchive\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\QBX.exe"",0"
Root: HKCR; Subkey: "QBXArchive\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\QBX.exe"" ""%1"""

[Run]
Filename: "{app}\QBX.exe"; Description: "Abrir QBX"; Flags: nowait postinstall skipifsilent
