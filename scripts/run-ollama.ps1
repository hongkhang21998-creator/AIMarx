$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$env:OLLAMA_NO_CLOUD = "1"
$env:OLLAMA_HOST = "127.0.0.1:11434"
$env:OLLAMA_NUM_PARALLEL = "1"
$env:OLLAMA_MAX_LOADED_MODELS = "1"
$env:OLLAMA_MODELS = Join-Path $PWD ".runtime\models"
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    throw "Chưa cài Ollama cho Windows. Gói .tar.zst trong .runtime/downloads là bản Linux, không dùng được ở đây."
}
& $ollama.Source serve
