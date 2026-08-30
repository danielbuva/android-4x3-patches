$ErrorActionPreference = "Stop"

$Repository = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Repository

$VenvPython = Join-Path $Repository ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    & $VenvPython (Join-Path $Repository "patch.py") @args
} else {
    & py -3 (Join-Path $Repository "patch.py") @args
}
exit $LASTEXITCODE
