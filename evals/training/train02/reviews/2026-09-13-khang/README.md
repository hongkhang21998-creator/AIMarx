# TRAIN-02 — snapshot đã được Nguyen Hong Khang duyệt

Nguồn xác nhận: hội thoại Codex `01a09881-af5a-7bc1-a569-7e3093bec69f`,
ngày 13/09/2026. Anh Khang xác nhận sau khi merge PR #50:

> đã merge và tôi duyệt 120 mẫu thống nhất, triển khai

Sau khi được hỏi riêng quyền train/export local không gồm cloud/GPU:

> có cấp quyền với điều kiện khong phát sinh thêm chi phí

Anh cũng giao tiếp quản #46. Toàn bộ quyết định, phạm vi và hash xuất nằm trong
[authorization.json](authorization.json). Đây là bản ghi lại lời duyệt thật của
người dùng, không phải AI tự chấm thay người hoặc chữ ký số.

## Trạng thái

- 120/120 approved; quyền training_approved=true, export_approved=true.
- Mỗi ca có hai receipt: duyệt chất lượng ban đầu, sau đó cấp hai quyền local.
- 120 content hashes, input, reference, rubric, family và split giữ nguyên so với
  bộ đã được anh xem ở PR #50 (`6d8dbc3`). Draft gốc không bị ghi đè.
- Giữ 80 train / 20 validation / 20 smoke-test. Smoke-test đã công khai, không là test mù.
- Không cấp quyền upload cloud, thuê GPU hoặc phát sinh chi phí. Chưa chạy training.

```bash
python -m evals.training.train02.cli check --data evals/training/train02/reviews/2026-09-13-khang
python -m evals.training.train02.cli export --data evals/training/train02/reviews/2026-09-13-khang --split train --output /tmp/approved-train.jsonl
python -m evals.training.train02.cli export --data evals/training/train02/reviews/2026-09-13-khang --split validation --output /tmp/approved-validation.jsonl
```

Chọn file output mới; không ghi đè file đã có. Export thật đã tạo local 80/20 dòng
và checksum trong authorization. File JSONL xuất không đưa thêm vào repo; tái tạo
được bằng lệnh trên. 20 smoke-test không được xuất thành dữ liệu huấn luyện.

Model prompt chỉ có id/input/instruction/output_schema; completion chứa reference
riêng. Cần kiểm tokenizer/context/loss-mask ở TRAIN-03 trước bất kỳ job train nào;
đủ quyền dữ liệu không chứng minh model đã tốt hoặc GPU đã sẵn sàng.

Nếu sửa nội dung, dùng luồng refresh/duyệt mới; không sửa receipt để giữ quyền.
Condition không chi phí/cloud được ghi trong authorization và reason của receipt;
CLI chỉ ghi local, không quản lý chi phí của chương trình bên ngoài dùng file sau này.
