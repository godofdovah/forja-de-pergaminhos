; Instalador do Windows (Inno Setup) da Forja de Pergaminhos
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
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=saida
OutputBaseFilename=Instalar-Forja-de-Pergaminhos
SetupIconFile=icone.ico
UninstallDisplayIcon={app}\{#AppName}.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "atalho"; Description: "Criar ícone na Área de Trabalho"; GroupDescription: "Ícones:"

[Files]
Source: "dist\{#AppName}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppName}.exe"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppName}.exe"; Tasks: atalho

[Run]
Filename: "{app}\{#AppName}.exe"; Description: "Abrir a Forja de Pergaminhos agora"; Flags: nowait postinstall skipifsilent
