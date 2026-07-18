[CmdletBinding()]
param(
    [string]$PythonLauncher = "py",
    [string]$PythonVersion = "3.13",
    [string]$VenvPath = ".venv-offline"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\")).Path
$wheelDir = Join-Path $root "offline\wheels"
$requirements = Join-Path $root "requirements-paddle.txt"
$venv = Join-Path $root $VenvPath
$python = Join-Path $venv "Scripts\python.exe"

if (!(Test-Path $wheelDir)) {
    throw "Offline wheel directory is missing: $wheelDir"
}
if (!(Test-Path $requirements)) {
    throw "Requirements file is missing: $requirements"
}

if ($PythonLauncher -eq "py") {
    $pyCommand = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($pyCommand) {
        $pythonExecutable = $pyCommand.Source
        $pythonSelectorArgs = @("-$PythonVersion")
    } else {
        $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
        if (!$pythonCommand) {
            throw "Python 3.13 was not found. Run the offline installer first: $(Join-Path $root 'offline\python-3.13.14-amd64.exe')"
        }
        $version = (& $pythonCommand.Source --version 2>&1) -join " "
        if ($version -notmatch "Python $([regex]::Escape($PythonVersion))(\.|$)") {
            throw "The current Python is not $PythonVersion. Run the offline installer first: $(Join-Path $root 'offline\python-3.13.14-amd64.exe')"
        }
        $pythonExecutable = $pythonCommand.Source
        $pythonSelectorArgs = @()
    }
} else {
    $customPython = Get-Command $PythonLauncher -ErrorAction SilentlyContinue
    if (!$customPython) {
        throw "The requested Python launcher was not found: $PythonLauncher"
    }
    $pythonExecutable = $customPython.Source
    $pythonSelectorArgs = @()
}

if (!(Test-Path $python)) {
    Write-Host "Creating Python $PythonVersion virtual environment: $venv"
    & $pythonExecutable @pythonSelectorArgs -m venv $venv
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the Python virtual environment. Install Python $PythonVersion x64 first."
    }
}

Push-Location $root
try {
    & $python -m pip install --no-index --find-links $wheelDir -r $requirements
    if ($LASTEXITCODE -ne 0) {
        throw "Offline dependency installation failed"
    }

    & $python -c "import paddle, paddleocr, hyperlpr3, rapidocr; print('offline OCR dependencies: ok')"
    if ($LASTEXITCODE -ne 0) {
        throw "OCR dependency import verification failed"
    }
} finally {
    Pop-Location
}

Write-Host "Offline environment installation completed: $python"
