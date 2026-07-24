; RadarCL Inno Setup Script
;
; Wizard text is Spanish because it is user-facing, per the language rule
; in CLAUDE.md. Directives, comments and identifiers stay English.
;
; AppVersion tracks pyproject.toml. Bump both together — Windows uses
; AppVersion to decide whether an install is an upgrade.
;
; Requirements:
;   - Inno Setup 6.x (https://jrsoftware.org/isinfo.php)
;   - dist\RadarCL.exe must exist (run pyinstaller first; no .spec is
;     committed, it is gitignored)
;
; Build:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" RadarCL.iss
;   Output: installer\RadarCL-v0.3.5-Setup.exe (gitignored — attach it to
;   a GitHub Release rather than committing it)

#define AppName "RadarCL"
#define AppVersion "0.3.5"
#define AppPublisher "Felipe Carvajal Brown"
#define AppURL "https://github.com/fcarvajalbrown/RadarCL"
#define AppExeName "RadarCL.exe"
#define AppDescription "Descubrimiento y verificacion de correos .cl"

[Setup]
AppId={{B4F2A1C3-9E87-4D56-A023-FC1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} v{#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
AppComments={#AppDescription}

; Installation directory
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes

; Output
OutputDir=installer
OutputBaseFilename=RadarCL-v{#AppVersion}-Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}

; Compression
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Appearance
; WizardResizable is not set: it is obsolete and ignored in current Inno
; Setup 6.x, which makes the wizard resizable unconditionally.
WizardStyle=modern
ShowLanguageDialog=no
LanguageDetectionMethod=none

; Windows version requirement (Windows 10+)
MinVersion=10.0

; Privileges
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Restart
DisableWelcomePage=no
DisableReadyPage=no
DisableFinishedPage=no

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon";   Description: "Crear un acceso directo en el &Escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked
Name: "startmenuicon"; Description: "Crear un acceso directo en el &menú Inicio"; GroupDescription: "Accesos directos:";

[Files]
; Main executable
Source: "dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Assets
Source: "assets\icon.ico"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "assets\icon.svg"; DestDir: "{app}\assets"; Flags: ignoreversion

; License / readme
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
; Start Menu
Name: "{group}\{#AppName}";              Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\assets\icon.ico"
Name: "{group}\Desinstalar {#AppName}";  Filename: "{uninstallexe}"

; Desktop (optional)
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\assets\icon.ico"; Tasks: desktopicon

[Run]
; Offer to launch after install
Filename: "{app}\{#AppExeName}"; \
    Description: "Abrir {#AppName} ahora"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up session database on uninstall
Type: filesandordirs; Name: "{userappdata}\.radarcl"

[Messages]
WelcomeLabel2=Se instalará [name/ver] en tu computador.%n%nRadarCL busca y verifica contactos de correo público en sitios web chilenos (.cl). Desarrollado por Felipe Carvajal Brown.%n%nPulsa Siguiente para continuar.
FinishedLabel=RadarCL quedó instalado.%n%nLo encontrarás en el menú Inicio, o puedes abrirlo ahora marcando la casilla de abajo.
