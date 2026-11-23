#define AppName "Gran Torino Print Service"
#define AppVersion "1.0.0"
#define AppExeName "GranTorino.PrintService.exe"
[Setup]
AppId={{9A6B0A9D-8EE9-4CA0-9B57-AE3AA9C9D7EA}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\Gran Torino\Print Service
OutputDir=..\artifacts
OutputBaseFilename=GranTorinoPrintService-Setup
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
Compression=lzma2
SolidCompression=yes
[Files]
Source: "..\publish\win-x64\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Run]
Filename: "sc.exe"; Parameters: "create GranTorinoPrintService binPath= ""{app}\{#AppExeName}"" start= auto"; Flags: runhidden waituntilterminated
Filename: "sc.exe"; Parameters: "start GranTorinoPrintService"; Flags: runhidden waituntilterminated
[UninstallRun]
Filename: "sc.exe"; Parameters: "stop GranTorinoPrintService"; Flags: runhidden waituntilterminated
Filename: "sc.exe"; Parameters: "delete GranTorinoPrintService"; Flags: runhidden waituntilterminated
