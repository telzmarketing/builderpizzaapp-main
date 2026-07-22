$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$migrationPath = Join-Path $root "backend/migrations/versions/20260801_tenant_marketing_crm_whatsapp_expand.py"
$helperPath = Join-Path $root "backend/core/wave6_tenant_orm.py"
$migration = Get-Content $migrationPath -Raw
$helper = Get-Content $helperPath -Raw

$newBlock = [regex]::Match(
    $migration,
    'NEW_TENANT_COLUMNS = \((?<body>[\s\S]*?)\)\r?\n\r?\nEXISTING_TENANT_COLUMNS'
).Groups['body'].Value
$existingBlock = [regex]::Match(
    $migration,
    'EXISTING_TENANT_COLUMNS = \((?<body>[\s\S]*?)\)\r?\n\r?\nTABLES'
).Groups['body'].Value
$tables = [regex]::Matches($newBlock + $existingBlock, '"([a-z0-9_]+)"') |
    ForEach-Object { $_.Groups[1].Value }

if ($tables.Count -ne 83) {
    throw "Wave 6 migration inventory drift: expected 83 tables, found $($tables.Count)"
}

$sources = Get-ChildItem (Join-Path $root "backend/models"), (Join-Path $root "backend/routes") -Filter "*.py" -File
foreach ($table in $tables) {
    $expected = 'tenant_id = wave6_tenant_column("' + $table + '")'
    $matches = @($sources | Where-Object { (Get-Content $_.FullName -Raw).Contains($expected) })
    if ($matches.Count -ne 1) {
        throw "ORM ownership mapping for $table must occur exactly once; found $($matches.Count)"
    }
    if (-not $helper.Contains('"' + $table + '"')) {
        throw "Wave 6 helper inventory is missing $table"
    }
}

$uniqueBlock = [regex]::Match(
    $migration,
    'SCOPED_UNIQUES = \((?<body>[\s\S]*?)\)\r?\n\r?\nCOMPOSITE_FKS'
).Groups['body'].Value
$uniqueNames = [regex]::Matches($uniqueBlock, '\("(uq_mt_[a-z0-9_]+)"') |
    ForEach-Object { $_.Groups[1].Value }
if ($uniqueNames.Count -ne 22) {
    throw "Wave 6 unique inventory drift: expected 22, found $($uniqueNames.Count)"
}
foreach ($name in $uniqueNames) {
    if (-not $helper.Contains('"' + $name + '"')) {
        throw "Wave 6 helper is missing scoped unique $name"
    }
}

Write-Output "Wave 6 ORM audit passed: 83 tables, 83 nullable ownership mappings, 22 scoped uniques."
