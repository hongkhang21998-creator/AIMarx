#!/usr/bin/env bash
# ASUS deployment. Run with bash; no API keys or shell-sourced .env files.
set -euo pipefail
aimarx_repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
aimarx_common=$(git -C "$aimarx_repo" rev-parse --path-format=absolute --git-common-dir)
aimarx_install=$(dirname -- "$aimarx_common")
aimarx_python="$aimarx_install/.venv/bin/python"
aimarx_ollama="$aimarx_install/.runtime/ollama/bin/ollama"
aimarx_mount=/run/media/asus/Data1000
aimarx_model=qwen2.5:3b-instruct-q3_K_M
aimarx_open=0

case "${1:-start}" in
    status)
        systemctl --user --no-pager status aimarx-ollama aimarx-local
        exit ;;
    stop)
        systemctl --user stop aimarx-local aimarx-ollama
        exit ;;
    start) ;;
    open) aimarx_open=1 ;;
    *) echo "Usage: bash scripts/asus-local-agent.sh [start|open|stop|status]" >&2; exit 2 ;;
esac

if ! mountpoint -q "$aimarx_mount"; then
    udisksctl mount -b /dev/disk/by-label/Data1000
fi
mountpoint -q "$aimarx_mount" || { echo "Data1000 chưa gắn đúng vị trí; dừng." >&2; exit 1; }
[[ -x "$aimarx_python" && -x "$aimarx_ollama" ]] || { echo "Thiếu Python venv hoặc Ollama." >&2; exit 1; }

if ! systemctl --user is-active --quiet aimarx-ollama; then
    systemd-run --user --unit=aimarx-ollama --collect \
        --property=Restart=on-failure --property=RestartSec=5 \
        --setenv=OLLAMA_HOST=127.0.0.1:11434 --setenv=OLLAMA_NO_CLOUD=1 \
        --setenv=OLLAMA_NUM_PARALLEL=1 --setenv=OLLAMA_MAX_LOADED_MODELS=1 \
        --setenv=OLLAMA_CONTEXT_LENGTH=2048 \
        --setenv="OLLAMA_MODELS=$aimarx_mount/AIMarx/models" "$aimarx_ollama" serve
fi
"$aimarx_python" - "$aimarx_model" <<'PY'
import json, sys, time, urllib.request
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
for attempt in range(15):
    try:
        with opener.open("http://127.0.0.1:11434/api/version", timeout=2):
            break
    except OSError:
        time.sleep(1)
else:
    sys.exit("Ollama chưa sẵn sàng.")
request = urllib.request.Request("http://127.0.0.1:11434/api/show",
    data=json.dumps({"model": sys.argv[1]}).encode(), headers={"Content-Type": "application/json"})
try:
    with opener.open(request, timeout=10) as response:
        info = json.load(response)
    if info.get("details", {}).get("quantization_level") != "Q3_K_M":
        sys.exit("Model không đúng Q3_K_M; dừng.")
except OSError:
    sys.exit("Chưa có model Qwen Q3_K_M trong Ollama. Cần hoàn tất cài model trước.")
PY

if ! systemctl --user is-active --quiet aimarx-local; then
    systemd-run --user --unit=aimarx-local --collect \
        --property="WorkingDirectory=$aimarx_repo" \
        --property=Restart=on-failure --property=RestartSec=5 \
        --setenv="PYTHONPATH=$aimarx_repo/src" \
        --setenv="TLVB_DATA=$aimarx_mount/AIMarx/workspace/data" \
        --setenv="TLVB_REQUIRED_MOUNT=$aimarx_mount" \
        --setenv=TLVB_MODE=ollama --setenv="TLVB_MODEL=$aimarx_model" \
        --setenv=TLVB_LOCAL_ONLY=1 --setenv=TLVB_PORT=8765 \
        "$aimarx_python" -m tro_ly_van_ban.web
fi
"$aimarx_python" - "$aimarx_model" <<'PY'
import json, sys, time, urllib.request
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
for attempt in range(20):
    try:
        with opener.open("http://127.0.0.1:8765/v1/providers", timeout=2) as response:
            providers = json.load(response)["providers"]
        local = next(item for item in providers if item["id"] == "local-qwen")
        if local["model"] != sys.argv[1]:
            sys.exit("Ứng dụng đang chạy model khác; dùng stop rồi start để nạp cấu hình mới.")
        break
    except OSError:
        time.sleep(1)
else:
    sys.exit("Ứng dụng chưa sẵn sàng; xem systemctl --user status aimarx-local.")
PY
echo "AIMarx: http://127.0.0.1:8765/agent — Q3_K_M, context tối đa 2048, cloud khóa."
if [[ "$aimarx_open" == 1 ]]; then
    xdg-open http://127.0.0.1:8765/agent
fi
