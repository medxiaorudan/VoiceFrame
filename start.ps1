$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 scripts/bootstrap.py @args
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python scripts/bootstrap.py @args
} else {
    Write-Error "Install Python 3.11+ and enable Add Python to PATH. See README."
}
exit $LASTEXITCODE
