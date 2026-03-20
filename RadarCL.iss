; RadarCL Inno Setup Script
; Builds a professional Windows installer for RadarCL v1.0
;
; Requirements:
;   - Inno Setup 6.x (https://jrsoftware.org/isinfo.php)
;   - dist\RadarCL.exe must exist (run pyinstaller RadarCL.spec first)
;
; Build:
;   Open this file in Inno Setup Compiler and click Build > Compile
;   Output: installer\RadarCL-v1.0-Setup.exe

#define AppName "RadarCL"
#define AppVersion "1.0"
#define AppPublisher "Instituto Igualdad - Área de Innovación Tecnológica"
#define AppURL "https://github.com/fcarvajalbrown/RadarCL"
#define AppExeName "RadarCL.exe"
#define AppDescription "Chilean email discovery and verification tool"

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
OutputBaseFilename=RadarCL-v1.0-Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}

; Compression
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Appearance
WizardStyle=modern
WizardResizable=yes
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
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";   Description: "Create a &desktop shortcut";    GroupDescription: "Additional icons:"; Flags: unchecked
Name: "startmenuicon"; Description: "Create a &Start Menu shortcut"; GroupDescription: "Additional icons:";

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
Name: "{group}\{#AppName}";           Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\assets\icon.ico"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"

; Desktop (optional)
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\assets\icon.ico"; Tasks: desktopicon

[Run]
; Offer to launch after install
Filename: "{app}\{#AppExeName}"; \
    Description: "Launch {#AppName} now"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up session database on uninstall
Type: filesandordirs; Name: "{userappdata}\.radarcl"

[Messages]
WelcomeLabel2=This will install [name/ver] on your computer.%n%nRadarCL is a professional email discovery and verification tool for Chilean websites, developed by Instituto Igualdad.%n%nClick Next to continue.
FinishedLabel=RadarCL has been installed successfully.%n%nYou can find it in your Start Menu or launch it now using the checkbox below.
