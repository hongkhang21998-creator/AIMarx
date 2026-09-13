# Bàn giao 43a — TRAIN-01 và bổ sung ledger #43

Ngày 13/09/2026 · Astra · base main `19126b915e36a5d9cc3d451c1e62e8f99e0c02a3`.
Nhánh `codex/train01-43a`. Anh Khang merge; không push thẳng main.

Đã nhận việc và cập nhật phạm vi trước code:
- https://github.com/hongkhang21998-creator/AIMarx/issues/43#issuecomment-5649606274
- https://github.com/hongkhang21998-creator/AIMarx/issues/43#issuecomment-5649608589

## Phạm vi và thay đổi

`evals/planning_v2/` chứa schema Python/JSON, validator nguồn và graph, CLI offline,
36 ca synthetic, manifest/hash, rubric và protocol baseline. Test trong
`tests/test_planning_v2.py`; runner đột biến `tests/train01_mutations.py` chạy trên
bản sao riêng. README của gói mô tả lệnh, ngưỡng, quyền dữ liệu và giới hạn.

Không sửa scorer/fixtures planning-v1, extraction hoặc runtime gọi SLM. Hợp đồng
proposal-v2 chưa là scheduler. Mọi đáp án mẫu chờ người duyệt; chưa train hoặc đo
chất lượng SLM. 12 ca reference giữ lại đã công khai, không gọi là test mù độc lập.

Ledger chỉ sửa nhánh replay của `mark_unresolved` trong `provider_ledger.py`:
- Trước: lần đầu TRANSPORT_TIMEOUT, lần sau USAGE_MISSING bị bỏ qua và trả thành công.
- Sau: cùng lý do trả thành công không thêm event; khác lý do báo
  `LEDGER_UNAVAILABLE / UNRESOLVED_CONFLICT`, rollback clock và giữ bản ghi cũ.
- Không đổi schema DB, public API signature, công thức tiền hoặc cấp thêm quyền.
- `tests/test_ledger_43a.py`: tái hiện lỗi, exact replay, 6 trạng thái × 2 ranh giới
  ngày/tháng, và fault injection khi ghi event để kiểm rollback tiền/clock/snapshot.

## Đối chiếu phần ledger của #43

| Yêu cầu | Bằng chứng hiện có / bổ sung 43a |
|---|---|
| P1 reserve/claim/consume cùng transaction; Reservation bất biến | Giữ implementation và regression #44 trong test_provider_ledger/grants |
| P2 settle/event/lock/finish cùng transaction; public finish không bỏ ledger | Giữ regression #44, kiểm lại toàn bộ; thêm rollback mark_unresolved khi event lỗi |
| Đủ đóng góp 6 trạng thái; tiền số nguyên, mặc định 0 | Bổ sung matrix qua ngày/tháng dùng API thật với rate card synthetic |
| Recovery/unresolved/over-reserve/reconcile idempotent | Sửa phát hiện lý do unresolved mâu thuẫn; giữ recovery/reconcile và provider lock của #44 |
| Mutation/Linux/Windows | Kết quả từng lượt phía dưới; CI theo SHA PR, không dùng kết quả nhánh cũ |

Không làm lại 5 bước đã hoàn thành trong #44. Không thêm adapter thật, giá thật,
quyền reconciliation UI hoặc model tự quyết ngân sách. Lịch giờ UTC truyền từ test
chỉ giả lập backend; chưa kiểm chứng transport/provider production.

## Kiểm tra

| Kiểm tra trên Linux, Python 3.12.14 | Kết quả |
|---|---|
| Tập trung schema/CLI/ledger bổ sung | 73 passed (1,64 giây) |
| Regression toàn bộ phiên bản cuối | 660 passed, 2 skipped (28,14 giây) |
| 7 source mutations TRAIN-01/43a | 7/7 bị bắt, assertion failure, không lỗi collection |
| 15 source mutations ledger #44 | 15/15 bị bắt |
| CLI check, hash, schema xuất, 36 reference | Đạt kiểm cấu trúc; chưa là điểm SLM |

Hai skip: Data1000 chưa bật opt-in trong lượt này; junction chỉ chạy trên Windows.
Không coi lượt này là kiểm NTFS. Có một cảnh báo deprecation AnyIO/Starlette có sẵn.
CI Ubuntu/Windows theo SHA được cập nhật tại Checks và bình luận bàn giao PR.
Lượt Windows đầu ở `91d5e99` lỗi setup/teardown một test: pytest dùng chuỗi 65 KiB
làm parameter ID, khiến PYTEST_CURRENT_TEST vượt giới hạn 32.767 ký tự của Windows.
Đã đặt ID ngắn cho 11 ca JSON lỗi, giữ nguyên payload/assertion; không nới validator.
Chạy lại bộ tập trung và CI trên commit sửa tên ca test trước khi bàn giao.

Lệnh tái hiện:

```bash
python -m pytest -q
python -m evals.planning_v2.cli check
python tests/train01_mutations.py /tmp/train01-mutations.json
python tests/ledger_mutations.py /tmp/ledger-mutations.json
```

Trên Windows chọn đường dẫn tạm hợp lệ của tài khoản. Các mutation chạy trên bản
sao riêng, không chỉnh source checkout hoặc DB production. Kết quả từng đột biến
lưu kèm `TRAIN-01-43a-evidence.json`.

Đã có test đỏ xác minh lỗi replay
trước sửa (`DID NOT RAISE`); một ca fault injection ban đầu bắt sai lớp exception,
đã sửa để kiểm `SnapshotError.reason == DB_ERROR`, không sửa production vì lỗi test.
Lượt regression trong sandbox treo và đã dừng đúng tiến trình; không tính là đạt.
Chạy lại ngoài sandbox bằng interpreter/dependencies khóa của repo.

## Phối hợp và tiếp nối

Không sửa WORKLOG, TIEN_DO, KE_HOACH, SLM_TRAINING_PLAN hoặc PSC-01 đang thuộc PR #47.
Handoff này và bình luận GitHub là nhật ký gói để tránh xung đột; không sửa #46.
Không khởi chạy subagent hay giao thêm việc cho Claude. Đội phụ trách gói sau đối
chiếu PR #47 đã merge trước khi nhận file.

Sau anh merge, TRAIN-02 bắt đầu bằng review nghiệp vụ 36 ca/hợp đồng, ghi duyệt và
chuẩn bị 120 mẫu smoke có phân chia riêng. TRAIN-03 mới đo model và chọn GPU.
Không dùng bản fixture có cờ pending_human làm dữ liệu train được duyệt.

Rollback: revert commit PR này; code đổi duy nhất kiểm replay reason, không migration.
Nếu gặp caller báo lý do khác cho cùng attempt, cần điều tra caller và dùng reconcile
đúng quy trình, không đổi reason cũ để che mâu thuẫn. Không deploy/restart production.
