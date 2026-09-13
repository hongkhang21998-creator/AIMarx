# TRAIN-02 — duyệt 120 mẫu, quyền local và tích hợp #46

Ngày 13/09/2026; base `380ebb41b2d79b00aeddb23e3e17639db61b99f4` sau merge PR #50.
Nhánh `codex/train02-human-approval`. Head cuối ghi ở PR/issue, tránh hash tự tham chiếu.

## Quyền người dùng đã xác nhận

Anh Nguyen Hong Khang duyệt thống nhất 120 mẫu đã xem ở PR #50; sau đó cấp thêm
quyền train/export local **không phát sinh thêm chi phí** và giao tiếp quản #46.
Bản ghi nguyên lời và checksum: `evals/training/train02/reviews/2026-09-13-khang/authorization.json`.
Không coi lời duyệt là quyền upload cloud/thuê GPU. Không khởi chạy model/train,
không đổi production/runtime, không subagent. Chi phí thêm: 0.

## Kết quả

- Giữ nguyên draft và authoring. Snapshot mới có 120 approved, hai receipt mỗi ca
  (chất lượng trước, quyền local sau); không đổi 120 content hashes/input/reference/rubric.
- Module #46 được triển khai theo ba file đã giao; xem G-TEST-01-result.md.
- Pin module đã qua test hợp đồng/oracle/mutation; newline normalization hỗ trợ Windows.
- Check báo split_audit=ok, không near-duplicate finding, local export_ready=true.
- Export local thật: train 80 dòng, validation 20 dòng; smoke-test 20 giữ riêng.
- Train JSONL SHA-256: `1062862c5db0c466de2b2ac20c3f217edabfcaa84ea34304c28c46a9758e4a2b`.
- Validation JSONL SHA-256: `8d3c43d3d69df8c7c58cba9733e76b1619d77629a144fae946468c8c56ad1741`.
- Local files nằm tại `artifacts/train02-local-export-20260913/` ở workspace cha;
  không thêm bản JSONL trùng vào Git, lệnh tái tạo có trong README snapshot.

Bản ghi quyền có thể dùng lại với CLI, không cần tự nhận đã train. Prompt và
completion tách biệt; test thật xác minh đúng 80/20 ID và schema envelope, không rò
rubric/reviewer vào prompt. File exported không tự bảo đảm label mask/token budget
cho trainer; TRAIN-03 mới kiểm phần đó. Test exposed không dùng làm test mù.

## Phạm vi và kiểm thử

#46 sở hữu ba file module/tests/handoff. #49 thay core/CLI/README và tests TRAIN-02,
thêm snapshot reviews/2026-09-13-khang và handoff này. Không sửa tài liệu #47,
WORKLOG chung, ledger, runtime, dependencies hoặc baseline. Claim và thay phạm vi
đã ghi trên cả #46/#49 trước code.

Tests tập trung **147 passed** (#46:75, TRAIN-02:72), gồm module thật + CLI export thật,
chặn trùng family/template thật, pin CRLF/sửa nội dung, snapshot giữ nội dung đã duyệt.
Có 300 lô oracle độc lập và 7/7 mutation bị bắt. Full Linux ngoài sandbox đạt
**807 passed, 2 skipped, 1 cảnh báo AnyIO cũ**, 69,96 giây. Hai skip là Data1000 opt-in
và Windows junction trên Linux; không đụng production/Data1000. CI được ghi tại đúng
head trong PR; không suy Windows đạt từ kết quả Linux.

## Bước tiếp và rollback

Anh merge PR chứa module + integration + snapshot cùng lúc. Không tự merge hoặc
đóng issue. Sau merge có thể dùng snapshot cho benchmark/smoke local trong TRAIN-03;
chọn tài nguyên miễn phí và kiểm quyền riêng trước khi gửi dữ liệu ra ngoài.
Không hứa fine-tune được trên laptop hoặc tự thuê GPU.

Rollback bằng revert PR, không ảnh hưởng DB/runtime. Giữ file export/snapshot đã duyệt
để truy vết; muốn thu quyền phải tạo receipt reject hoặc duyệt mới bỏ quyền, không
chỉ sửa tài liệu hướng dẫn. Không có cloud resource/job phát sinh để dừng.
