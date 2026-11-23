#ifndef Versao
  #define Versao "0.0.0"
#endif

[Setup]
AppId={{472802C4-4B04-404F-8464-D51FB132CBA4}
AppName=Nexo
AppVersion={#Versao}
AppVerName=Nexo {#Versao}
AppPublisher=ravelroot
AppPublisherURL=https://github.com/ravelroot/Retrieval-Augmented-QA-System
AppSupportURL=https://github.com/ravelroot/Retrieval-Augmented-QA-System/issues
AppUpdatesURL=https://github.com/ravelroot/Retrieval-Augmented-QA-System/releases
VersionInfoVersion={#Versao}
VersionInfoProductName=Nexo
VersionInfoDescription=Instalador do Nexo
DefaultDirName={autopf}\Nexo
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=saida
OutputBaseFilename=Nexo-Setup-{#Versao}
SetupIconFile=nexo.ico
UninstallDisplayIcon={app}\Nexo.exe
UninstallDisplayName=Nexo
LicenseFile=..\LICENSE
WizardStyle=modern
Compression=lzma2/ultra64
SolidCompression=yes
LZMANumBlockThreads=4
CloseApplications=yes
RestartApplications=no
ShowLanguageDialog=no

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "atalho"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\Nexo\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Nexo"; Filename: "{app}\Nexo.exe"; WorkingDir: "{app}"; AppUserModelID: "Ravelroot.Nexo"; Comment: "Agentes de IA que respondem com os seus documentos"
Name: "{autodesktop}\Nexo"; Filename: "{app}\Nexo.exe"; WorkingDir: "{app}"; AppUserModelID: "Ravelroot.Nexo"; Comment: "Agentes de IA que respondem com os seus documentos"; Tasks: atalho

[Registry]
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\Nexo.exe"; ValueType: string; ValueName: ""; ValueData: "{app}\Nexo.exe"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\Nexo.exe"; ValueType: string; ValueName: "Path"; ValueData: "{app}"

[Run]
Filename: "{app}\Nexo.exe"; Description: "{cm:LaunchProgram,Nexo}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Dados: String;
begin
  if (CurUninstallStep = usPostUninstall) and not UninstallSilent then
  begin
    Dados := ExpandConstant('{localappdata}\Nexo');
    if DirExists(Dados) and (MsgBox('Apagar também os dados do Nexo (bases, documentos, conversas, contas e backups) em ' + Dados + '?' + #13#10#13#10 + 'Escolha Não para manter tudo e usar de novo se instalar o Nexo outra vez.', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES) then
      DelTree(Dados, True, True, True);
  end;
end;
