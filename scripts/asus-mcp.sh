#!/usr/bin/env bash
# Stdio must contain only MCP protocol output. Share the deployed local data/model.
set -euo pipefail
aimarx_repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
aimarx_common=$(git -C "$aimarx_repo" rev-parse --path-format=absolute --git-common-dir)
aimarx_install=$(dirname -- "$aimarx_common")
export PYTHONPATH="$aimarx_repo/src"
export TLVB_DATA=/run/media/asus/Data1000/AIMarx/workspace/data
export TLVB_REQUIRED_MOUNT=/run/media/asus/Data1000
export TLVB_MODE=ollama
export TLVB_MODEL=qwen2.5:3b-instruct-q3_K_M
export TLVB_LOCAL_ONLY=1
exec "$aimarx_install/.venv/bin/python" -m tro_ly_van_ban.mcp_server
