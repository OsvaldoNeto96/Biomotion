; ============================================================
;  BioMotion - Script de Instalação (Inno Setup 6)
;  Gera: installer\BioMotion_Instalador_v2.2.exe
; ============================================================

#define AppName      "BioMotion"
#define AppVersion   "2.2"
#define AppPublisher "BioMotion Clinico"
#define AppExeName   "BioMotion.exe"
#define AppSourceDir "dist\BioMotion"

[Setup]
AppId={{B10M0T10-CL1N-4B10-M3CA-N1CA000000001}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} v{#AppVersion}
AppPublisher={#AppPublisher}

DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}

PrivilegesRequired=admin
MinVersion=10.0

OutputDir=installer
OutputBaseFilename=BioMotion_Instalador_v{#AppVersion}

Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

WizardStyle=modern
WizardSizePercent=120
SetupIconFile=assets\icon.ico

UninstallDisplayName={#AppName} v{#AppVersion}
UninstallDisplayIcon={app}\{#AppExeName}

VersionInfoVersion={#AppVersion}.0.0
VersionInfoDescription=Instalador do {#AppName}
VersionInfoProductName={#AppName}

; Ficheiro exibido antes da instalação comecar (info sobre Kinect)
InfoBeforeFile=KINECT_INFO.txt

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon";   Description: "Criar atalho na Area de Trabalho"; GroupDescription: "Atalhos:"
Name: "startmenuicon"; Description: "Criar atalho no Menu Iniciar";     GroupDescription: "Atalhos:"

[Files]
Source: "{#AppSourceDir}\*"; \
    DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{app}\Analises_Salvas"; Permissions: users-full

[Icons]
Name: "{group}\{#AppName}";             Filename: "{app}\{#AppExeName}"; \
    Comment: "Painel Clinico de Biomecanica"; Tasks: startmenuicon
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}";      Tasks: startmenuicon
Name: "{commondesktop}\{#AppName}";     Filename: "{app}\{#AppExeName}"; \
    Comment: "Painel Clinico de Biomecanica"; Tasks: desktopicon

[Registry]
Root: HKLM; Subkey: "Software\{#AppPublisher}\{#AppName}"; \
    ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\{#AppPublisher}\{#AppName}"; \
    ValueType: string; ValueName: "Version"; ValueData: "{#AppVersion}"

[Run]
; Abre o BioMotion após instalação (opcional)
Filename: "{app}\{#AppExeName}"; \
    Description: "Abrir o BioMotion agora"; \
    Flags: nowait postinstall skipifsilent unchecked

; Abre página de download do driver Kinect (opcional, na página final)
Filename: "https://www.microsoft.com/en-us/download/details.aspx?id=44561"; \
    Description: "Baixar driver Kinect for Windows SDK"; \
    Flags: shellexec nowait postinstall skipifsilent unchecked

[UninstallDelete]
Type: filesandordirs; Name: "{app}\Analises_Salvas"
