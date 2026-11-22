$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$project = Join-Path $root 'src/GranTorino.PrintService/GranTorino.PrintService.csproj'
$publish = Join-Path $root 'publish/win-x64'
$artifacts = Join-Path $root 'artifacts'
$installerScript = Join-Path $root 'installer/GranTorinoPrintService.iss'
$installerOutput = Join-Path $artifacts 'GranTorinoPrintService-Setup.exe'

New-Item -Path $artifacts -ItemType Directory -Force | Out-Null
Remove-Item $publish -Recurse -Force -ErrorAction SilentlyContinue
New-Item -Path $publish -ItemType Directory -Force | Out-Null
Remove-Item $installerOutput -Force -ErrorAction SilentlyContinue

dotnet restore $project
dotnet publish $project -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -o $publish

$isccCandidates = @()
if ($env:ISCC_PATH) { $isccCandidates += $env:ISCC_PATH }
$isccCommand = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if ($isccCommand) { $isccCandidates += $isccCommand.Source }
if ($env:ChocolateyInstall) {
    $isccCandidates += (Join-Path $env:ChocolateyInstall 'bin/ISCC.exe')
    $isccCandidates += (Join-Path $env:ChocolateyInstall 'lib/innosetup/tools/ISCC.exe')
}
$isccCandidates += 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
$isccCandidates += 'C:\Program Files\Inno Setup 6\ISCC.exe'
$isccPath = $isccCandidates |
    Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } |
    Select-Object -First 1

Write-Host "Publish directory: $publish"
Get-ChildItem -LiteralPath $publish -Force |
    Select-Object FullName, Length, LastWriteTime |
    Format-Table -AutoSize

if (-not $isccPath) {
    Write-Error "ISCC.exe nao encontrado. Verificados PATH, ISCC_PATH, Chocolatey e Program Files. Candidates: $($isccCandidates -join '; ')"
    exit 1
}

Write-Host "Using Inno Setup compiler: $isccPath"
& $isccPath $installerScript
if ($LASTEXITCODE -ne 0) {
    Write-Error "ISCC.exe falhou com exit code $LASTEXITCODE. Esperado: $installerOutput"
    exit $LASTEXITCODE
}

Write-Host "Artifacts directory: $artifacts"
Get-ChildItem -LiteralPath $artifacts -Force |
    Select-Object FullName, Length, LastWriteTime |
    Format-Table -AutoSize
if (-not (Test-Path -LiteralPath $installerOutput -PathType Leaf)) {
    $artifactList = (Get-ChildItem -LiteralPath $artifacts -Force |
        Select-Object -ExpandProperty FullName) -join '; '
    Write-Error "Instalador nao foi produzido em $installerOutput. Conteudo de artifacts: $artifactList"
    exit 1
}
