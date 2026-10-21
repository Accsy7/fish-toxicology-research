param(
    [Parameter(Mandatory=$true)][string]$ProjectPath,
    [string]$PythonPath,
    [string]$WorkBuddyHome,
    [string]$CatalogPath,
    [switch]$UpdateTools,
    [switch]$ReplaceManaged
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
$installArgs = @('-X', 'utf8', '-B', (Join-Path $PSScriptRoot 'toolkit/install.py'), '--project', $ProjectPath, '--client', 'workbuddy')
if ($WorkBuddyHome) { $installArgs += @('--workbuddy-home', $WorkBuddyHome) }
if ($CatalogPath) { $installArgs += @('--catalog', $CatalogPath) }
if ($UpdateTools) { $installArgs += '--update-tools' }
if ($ReplaceManaged) { $installArgs += '--replace-managed' }
if ($PythonPath) { & $PythonPath @installArgs }
elseif (Get-Command py -ErrorAction SilentlyContinue) { & py -3 @installArgs }
elseif (Get-Command python -ErrorAction SilentlyContinue) { & python @installArgs }
else { throw 'Python 3.10+ required. Supply -PythonPath with your python.exe path.' }
exit $LASTEXITCODE
