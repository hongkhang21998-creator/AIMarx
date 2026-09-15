"""Opt-in real-model smoke with synthetic data; not part of pytest or a blind eval.

Run: PYTHONPATH=src python evals/local_agent/run_smoke.py --output /tmp/qwen-smoke.json
No provider key, private document, or cloud request is used.
"""
import argparse
import json
import os
from pathlib import Path
import tempfile
import time

import httpx

from tro_ly_van_ban.local_config import DEFAULT_LOCAL_MODEL, MAX_LOCAL_CONTEXT
from tro_ly_van_ban.service import Service


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.environ["TLVB_LOCAL_ONLY"] = "1"
    with httpx.Client(trust_env=False) as client:
        response = client.post("http://127.0.0.1:11434/api/show", json={"model": DEFAULT_LOCAL_MODEL})
        response.raise_for_status()
        details = response.json()["details"]
    assert details["quantization_level"] == "Q3_K_M"
    report = {"model": DEFAULT_LOCAL_MODEL, "details": details, "num_ctx": MAX_LOCAL_CONTEXT,
              "scope": "Synthetic smoke only; not a blind classification benchmark or step40 evaluation", "cases": []}
    with tempfile.TemporaryDirectory(prefix="aimarx-q3-smoke-") as root:
        service = Service(root)
        doc = service.ingest("ho-so-gia-lap.txt", (
            "HỒ SƠ GIẢ LẬP\nĐề nghị phòng Văn hóa gửi báo cáo trước ngày 20/09/2026.\n"
            "Nơi nhận: phòng Văn hóa.").encode(), classification="synthetic")
        cases = [
            ("greeting", "Xin chào, hãy giới thiệu ngắn gọn.", None, "answer"),
            ("listing", "Liệt kê các tài liệu hiện có trong kho.", None, "list_documents"),
            ("usage", "Tôi đã dùng bao nhiêu token trong 7 ngày?", None, "get_usage"),
            ("models", "Ứng dụng có những model nào?", None, "list_models"),
            ("scope", "Tóm tắt tài liệu cho tôi.", None, "read_document"),
            ("evidence", "Tài liệu yêu cầu phòng nào gửi báo cáo, hạn ngày nào?", doc, "read_document"),
        ]
        for name, prompt, scope, expected in cases:
            started = time.monotonic()
            try:
                result = service.aimarx.run_agent(prompt, scope)
                success = result["action"] == expected
                if name == "scope":
                    success &= result["status"] == "needs_input" and not result["steps"]
                if name == "evidence":
                    success &= "20/09/2026" in result["content"] and bool(result["evidence"])
                item = {"case": name, "expected": expected, "passed": success, "result": result}
            except Exception as exc:
                item = {"case": name, "expected": expected, "passed": False,
                        "error_type": type(exc).__name__, "error_code": getattr(exc, "code", None)}
            item["elapsed_seconds"] = round(time.monotonic() - started, 2)
            report["cases"].append(item)
            print(json.dumps({key: value for key, value in item.items() if key != "result"}), flush=True)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not all(case["passed"] for case in report["cases"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
