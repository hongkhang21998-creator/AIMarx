$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
# Windows dung cp1252 khi stdout bi chuyen huong -> tieng Viet lam hong tien trinh.
$env:PYTHONUTF8 = "1"
# Cau hinh rieng may trong .env (khong commit): chi nhan dong TLVB_*=gia_tri, khong chay nhu ma.
# Bien da dat san truoc khi chay script thang gia tri trong .env.
if (Test-Path ".env") {
    foreach ($line in Get-Content ".env" -Encoding UTF8) {
        if ($line -match '^(TLVB_[A-Z_]+)=(.*)$' -and -not (Test-Path "env:$($Matches[1])")) {
            Set-Item "env:$($Matches[1])" $Matches[2]
        }
    }
}
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Chưa có .venv. Xem mục Windows trong README."
}
& .\.venv\Scripts\python.exe -m tro_ly_van_ban.web
