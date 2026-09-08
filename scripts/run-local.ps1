$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
# Windows dung cp1252 khi stdout bi chuyen huong -> tieng Viet lam hong tien trinh.
$env:PYTHONUTF8 = "1"
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Chưa có .venv. Xem mục Windows trong README."
}
& .\.venv\Scripts\python.exe -m tro_ly_van_ban.web
