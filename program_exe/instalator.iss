; ====================================================================
;  GeoAI Klasyfikator - skrypt instalatora dla Inno Setup 6
;
;  Buduje się go poleceniem:
;      "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" instalator.iss
;  albo automatycznie przez zbuduj.bat.
;
;  Instalator nie wymaga praw administratora: program ląduje
;  w katalogu użytkownika, tak jak przeglądarki czy komunikatory.
; ====================================================================

#define NazwaProgramu   "GeoAI Klasyfikator"
#define Wersja          "1.0.0"
#define Autor           "Grzegorz Górniak"
#define Strona          "https://github.com/gorniakgrzegorz/geoai_klasyfikator"
#define PlikExe         "GeoAI Klasyfikator.exe"

[Setup]
AppId={{8F3C1E42-7B55-4A19-9D0C-3A7E51C9B204}
AppName={#NazwaProgramu}
AppVersion={#Wersja}
AppVerName={#NazwaProgramu} {#Wersja}
AppPublisher={#Autor}
AppPublisherURL={#Strona}
AppSupportURL={#Strona}/issues
AppUpdatesURL={#Strona}/releases
VersionInfoVersion={#Wersja}
VersionInfoCompany={#Autor}
VersionInfoDescription=Obiektowa klasyfikacja pokrycia terenu

; instalacja dla jednego użytkownika, bez praw administratora
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\GeoAI Klasyfikator
DefaultGroupName=GeoAI Klasyfikator
DisableProgramGroupPage=yes
AllowNoIcons=yes

OutputDir=instalator
OutputBaseFilename=GeoAI_Klasyfikator_Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile=ikona.ico
UninstallDisplayName={#NazwaProgramu}
UninstallDisplayIcon={app}\{#PlikExe}
LicenseFile=..\LICENSE
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "polski"; MessagesFile: "compiler:Languages\Polish.isl"

[CustomMessages]
polski.SkrotNaPulpicie=Utwórz skrót na pulpicie
polski.UruchomPoInstalacji=Uruchom {#NazwaProgramu}
polski.OtworzInstrukcje=Otwórz instrukcję w przeglądarce

[Tasks]
Name: "pulpit"; Description: "{cm:SkrotNaPulpicie}"; \
    GroupDescription: "Skróty:"; Flags: unchecked

[Files]
; cały katalog złożony przez PyInstallera
Source: "dist\GeoAI Klasyfikator\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\NOTICE.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#NazwaProgramu}"; Filename: "{app}\{#PlikExe}"
Name: "{group}\Instrukcja"; Filename: "{#Strona}"
Name: "{group}\Odinstaluj {#NazwaProgramu}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#NazwaProgramu}"; Filename: "{app}\{#PlikExe}"; \
    Tasks: pulpit

[Run]
Filename: "{app}\{#PlikExe}"; Description: "{cm:UruchomPoInstalacji}"; \
    Flags: nowait postinstall skipifsilent
Filename: "{#Strona}"; Description: "{cm:OtworzInstrukcje}"; \
    Flags: nowait postinstall skipifsilent shellexec unchecked

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
