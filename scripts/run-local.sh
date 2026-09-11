#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
# Cau hinh rieng may trong .env (khong commit): chi nhan dong TLVB_*=gia_tri, khong chay nhu ma.
# Bien da dat san o dong lenh thang gia tri trong .env.
if [[ -f .env ]]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
        line=${line%$'\r'}
        if [[ "$line" =~ ^(TLVB_[A-Z_]+)=(.*)$ ]] && [[ -z "${!BASH_REMATCH[1]+x}" ]]; then
            export "${BASH_REMATCH[1]}=${BASH_REMATCH[2]}"
        fi
    done < .env
fi
exec .venv/bin/tro-ly-van-ban
