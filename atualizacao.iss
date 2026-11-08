; Instalador de ATUALIZAÇÃO da Forja de Pergaminhos: só troca os arquivos que mudaram.
#define AppName "Forja de Pergaminhos"
#ifndef AppVersion
  #define AppVersion "1.0"
#endif

[Setup]
AppId={{6E0B7C1A-3F55-4E5B-9A51-F0A9E1C2D7B3}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Cleiton
DefaultDirName={localappdata}\Programs\{#AppName}
UsePreviousAppDir=yes
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
OutputDir=saida
OutputBaseFilename=Atualizar-Forja-de-Pergaminhos
SetupIconFile=icone.ico
UninstallDisplayIcon={app}\{#AppName}.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Messages]
WelcomeLabel2=Isto vai atualizar a sua Forja de Pergaminhos para a versão {#AppVersion}.%n%nFeche o programa antes de continuar.

[Files]
#include "atualizacao_arquivos.iss"

[Run]
Filename: "{app}\{#AppName}.exe"; Description: "Abrir a Forja de Pergaminhos agora"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
begin
  Result := RegKeyExists(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{6E0B7C1A-3F55-4E5B-9A51-F0A9E1C2D7B3}_is1');
  if not Result then
    MsgBox('A Forja de Pergaminhos não está instalada neste computador.' + #13#10 + #13#10 +
           'Baixe e use o instalador completo (Instalar-Forja-de-Pergaminhos.exe).', mbInformation, MB_OK);
end;
