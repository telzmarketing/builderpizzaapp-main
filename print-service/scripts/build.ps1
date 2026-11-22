$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$project = Join-Path $root 'src/GranTorino.PrintService/GranTorino.PrintService.csproj'
$publish = Join-Path $root 'publish/win-x64'
$artifacts = Join-Path $root 'artifacts'
Remove-Item $publish -Recurse -Force -ErrorAction SilentlyContinue
New-Item $publish -ItemType Directory -Force | Out-Null
dotnet restore $project
dotnet publish $project -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -o $publish
if (Get-Command ISCC.exe -ErrorAction SilentlyContinue) { ISCC.exe (Join-Path $root 'installer/GranTorinoPrintService.iss') } else { Write-Warning 'ISCC.exe não encontrado; o EXE foi publicado, mas o instalador não foi gerado.' }
Get-ChildItem $artifacts -ErrorAction SilentlyContinue
