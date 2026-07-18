[CmdletBinding()]
param(
    [string]$VenvPath = ".venv-offline"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\")).Path
$wheelDir = Join-Path $root "offline\wheels"
$modelRoot = Join-Path $root "models"
$python = Join-Path $root "$VenvPath\Scripts\python.exe"
$pythonInstaller = Join-Path $root "offline\python-3.13.14-amd64.exe"
$pythonInstallerSha256 = "c54d9b9bbb8a36e6489363ddd01139707fd781d72f1f9e90c7ec65d0061368e0"

if (!(Test-Path $pythonInstaller)) {
    throw "Offline Python installer is missing: $pythonInstaller"
}
if ((Get-FileHash -Algorithm SHA256 $pythonInstaller).Hash.ToLower() -ne $pythonInstallerSha256) {
    throw "Offline Python installer SHA256 verification failed: $pythonInstaller"
}

$requiredModels = @(
    "hyperlpr3\.hyperlpr3\20230229\onnx\y5fu_320x_sim.onnx",
    "hyperlpr3\.hyperlpr3\20230229\onnx\y5fu_640x_sim.onnx",
    "hyperlpr3\.hyperlpr3\20230229\onnx\rpv3_mdict_160_r3.onnx",
    "hyperlpr3\.hyperlpr3\20230229\onnx\litemodel_cls_96x_r1.onnx",
    "paddleocr\PP-OCRv6_medium_det_infer\inference.json",
    "paddleocr\PP-OCRv6_medium_det_infer\inference.pdiparams",
    "paddleocr\PP-OCRv6_medium_det_infer\inference.yml",
    "paddleocr\PP-OCRv6_medium_rec_infer\inference.json",
    "paddleocr\PP-OCRv6_medium_rec_infer\inference.pdiparams",
    "paddleocr\PP-OCRv6_medium_rec_infer\inference.yml",
    "paddleocr\PP-LCNet_x1_0_textline_ori_infer\inference.json",
    "paddleocr\PP-LCNet_x1_0_textline_ori_infer\inference.pdiparams",
    "paddleocr\PP-LCNet_x1_0_textline_ori_infer\inference.yml"
)

foreach ($relativePath in $requiredModels) {
    $path = Join-Path $modelRoot $relativePath
    if (!(Test-Path $path) -or (Get-Item $path).Length -le 0) {
        throw "Offline model file is missing: $path"
    }
}

foreach ($pattern in @("paddlepaddle-*.whl", "paddleocr-*.whl", "hyperlpr3-*.whl", "onnxruntime-*.whl")) {
    if (!(Get-ChildItem $wheelDir -Filter $pattern -File -ErrorAction SilentlyContinue)) {
        throw "Offline wheel is missing: $pattern"
    }
}

if (Test-Path $python) {
    & $python -c "import paddle, paddleocr, hyperlpr3, rapidocr; print('installed offline OCR dependencies: ok')"
    if ($LASTEXITCODE -ne 0) {
        throw "Installed environment import verification failed"
    }
}

$wheelCount = (Get-ChildItem $wheelDir -Filter "*.whl" -File).Count
if ($wheelCount -le 0) {
    throw "Offline wheel directory is empty: $wheelDir"
}
Write-Host "Offline assets verified: $wheelCount wheels, $($requiredModels.Count) core model files"
