$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$project = Join-Path $root 'src/GranTorino.PrintService/GranTorino.PrintService.csproj'
$publish = Join-Path $root 'publish/win-x64'
$artifacts = Join-Path $root 'artifacts'
$installerScript = Join-Path $root 'installer/GranTorinoPrintService.iss'
$installerOutput = Join-Path $artifacts 'GranTorinoPrintService-Setup.exe'

$root = (Resolve-Path -LiteralPath $root).Path
$project = (Resolve-Path -LiteralPath $project).Path
$installerScript = (Resolve-Path -LiteralPath $installerScript).Path
$publish = [IO.Path]::GetFullPath($publish)
$artifacts = [IO.Path]::GetFullPath($artifacts)
$installerOutput = [IO.Path]::GetFullPath($installerOutput)

Write-Host 'Preparing Gran Torino Print Service installer package.'
Write-Host "Build root: $root"
Write-Host "Project: $project"
Write-Host "Publish output: $publish"
Write-Host "Artifacts output: $artifacts"
Write-Host "Expected installer: $installerOutput"

if (-not (Test-Path -LiteralPath $project -PathType Leaf)) { throw "Projeto nao encontrado: $project" }
if (-not (Test-Path -LiteralPath $installerScript -PathType Leaf)) { throw "Script Inno Setup nao encontrado: $installerScript" }

New-Item -Path $artifacts -ItemType Directory -Force | Out-Null
Get-ChildItem -LiteralPath $artifacts -Force -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force
Remove-Item $publish -Recurse -Force -ErrorAction SilentlyContinue
New-Item -Path $publish -ItemType Directory -Force | Out-Null

dotnet restore $project
dotnet publish $project -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -o $publish

$isccCandidates = @()
if ($env:ISCC_PATH) { $isccCandidates += $env:ISCC_PATH }
$isccCommand = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if ($isccCommand) { $isccCandidates += $isccCommand.Path; $isccCandidates += $isccCommand.Source }
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
$isccPath = (Resolve-Path -LiteralPath $isccPath).Path
Write-Host "Invoking ISCC with absolute output directory: /O$artifacts"
& $isccPath "/O$artifacts" $installerScript
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
if ((Get-Item -LiteralPath $installerOutput).Length -le 0) {
    throw "Instalador vazio: $installerOutput"
}
Write-Host "Installer ready: $installerOutput ($((Get-Item -LiteralPath $installerOutput).Length) bytes)"
