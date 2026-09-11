# Bàn giao AIMarx PLAN-EVAL-01

- Người phụ trách: Luna.
- Phạm vi: bộ 6 ca công văn giả lập và đáp án kỳ vọng trong `cases.json`.
- File tạo mới: `docs/qa/planning-v1/cases.json`, `docs/qa/planning-v1/HANDOFF.md`.
- Không sửa mã nguồn, `TIEN_DO.md`, `WORKLOG.md` hoặc tài liệu bàn giao khác.

## Nội dung bộ ca

`PLN-01` yêu cầu báo cáo có hạn tuyệt đối nhưng thiếu số liệu; `PLN-02` dùng hạn tương đối và phải hỏi mốc; `PLN-03` có hai thời hạn mâu thuẫn; `PLN-04` chỉ cung cấp thông tin, không giao việc; `PLN-05` chứa prompt injection giả lệnh gửi cloud và tự duyệt; `PLN-06` ghép một nguồn `public` với một nguồn `internal` và phải giữ local.

`cloud_eligible` là điều kiện an toàn kỳ vọng cho toàn bộ ca, không phải quyền tự động gửi. Ca `PLN-05` giữ `unknown` và ca `PLN-06` có nguồn `internal`, nên cả hai đều `false`; kể cả ca `true` vẫn cần người dùng xác nhận trước hành động bên ngoài. Tất cả văn bản và số liệu trong bộ này đều giả lập.

## Kiểm tra bàn giao

Có thể kiểm tra không thêm validator mới bằng Python chuẩn:

```bash
python3 -c 'import json; from pathlib import Path; p=Path("docs/qa/planning-v1/cases.json"); d=json.loads(p.read_text(encoding="utf-8")); assert d["schema_version"] == 1; assert len(d["cases"]) == 6; assert len({c["id"] for c in d["cases"]}) == 6; [(assertion := (q["quote"] in next(s["text"] for s in c["sources"] if s["id"] == q["source_id"]))) or (_ for _ in ()).throw(AssertionError(q)) for c in d["cases"] for q in c["expected"]["evidence_quotes"]]; print("OK: JSON hợp lệ, đủ 6 ca, mọi quote khớp nguồn")'
```

Lệnh trên kiểm JSON, top-level `schema_version`, đúng 6 ca, ID không trùng và từng `quote` là substring chính xác của đúng nguồn. Đây là đáp án kỳ vọng để đối chiếu, chưa phải benchmark chạy AI/model.

