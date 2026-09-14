$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$env:OLLAMA_NO_CLOUD = "1"
$env:OLLAMA_HOST = "127.0.0.1:11434"
$env:OLLAMA_NUM_PARALLEL = "1"
$env:OLLAMA_MAX_LOADED_MODELS = "1"

# Native Ollama for Windows uses %USERPROFILE%\.ollama\models by default.
# Keep an explicit caller override, but do not silently point a fresh Windows
# installation at the Linux-oriented repository runtime directory.
if ([string]::IsNullOrWhiteSpace($env:OLLAMA_MODELS)) {
    $env:OLLAMA_MODELS = Join-Path $env:USERPROFILE ".ollama\models"
}

$ollamaCommand = Get-Command ollama -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
$ollamaPath = $null
if ($ollamaCommand) {
    $ollamaPath = $ollamaCommand.Source
}

if (-not $ollamaPath) {
    $candidates = @(
        (Join-Path $PWD ".runtime\ollama\ollama.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe")
    )
    $ollamaPath = $candidates |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
        Select-Object -First 1
}

if (-not $ollamaPath) {
    throw "Chưa cài Ollama cho Windows. Gói .tar.zst trong .runtime/downloads là bản Linux, không dùng được ở đây."
}

# The native Windows app may already have started the loopback server. Reuse
# it instead of launching a second server on the same port.
try {
    $version = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/version" -Method Get -TimeoutSec 2
    Write-Host ("Ollama đang chạy (version {0}) tại 127.0.0.1:11434." -f $version.version)
    exit 0
}
catch {
    # No server is listening yet; start the discovered executable below.
}

& $ollamaPath serve
