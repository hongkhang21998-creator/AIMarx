# G-TEST-01 / #46 — tiếp quản và hoàn thiện kiểm split

Base main `380ebb41b2d79b00aeddb23e3e17639db61b99f4`, 13/09/2026.
Anh Khang giao rõ trong hội thoại: “Có, tiếp quản và hoàn thiện #46”. Đã ghi claim
trên issue #46 trước code; không có PR/module bàn giao trên main khi tiếp quản.
AI của tác vụ Codex này thực hiện; không giả nhận là sản phẩm Gemini hoặc khởi chạy Gemini.

## Ba file #46

- `evals/training/split_audit.py`: hàm thuần audit_splits; không file/env/network/log/DB.
- `tests/test_split_audit.py`: 67 ca hợp đồng + 1 oracle 300 lô + 7 mutation.
- `docs/handoffs/G-TEST-01-result.md`: bàn giao này.

Phần tích hợp/approval TRAIN-02 thuộc #49, được ghi riêng trong TRAIN-02-human-approval.md;
không giả rằng toàn PR chỉ có ba file, vì anh đã giao cả hai phạm vi.

## Hợp đồng và giới hạn

Kiểm đúng list/dict và đúng năm khóa, kiểu string, ID không rỗng sau strip,
split chính xác train/validation/test, hash 64 lowercase hex. Mọi input được kiểm
trước khi trả finding; lỗi luôn ValueError với thông điệp cố định không có record.
Chuẩn hóa ID trên bản sao. Bốn loại finding, group/key/splits/sample_ids sắp xếp,
không lặp; không alias list output với input hoặc giữa các finding.

Đây là kiểm trùng ID/family/template/exact hash; không bắt mọi paraphrase và không
cấp quyền train/export. Near-duplicate/receipt vẫn ở TRAIN-02.

## Kiểm chứng

`python -m pytest -q tests/test_split_audit.py tests/test_train02_data_review.py`:
**147 passed**. Trong đó #46 có 75, TRAIN-02 có 72. Toàn bộ ca hợp đồng chạy thật.

Oracle dùng so sánh từng cặp thay vì nhóm như production, seed 490046, 300 lô
0–8 record có ID whitespace/trùng và ba split. Kết quả khớp implementation.
7/7 mutation bị oracle/ca âm phát hiện: bỏ cross-split; bỏ duplicate cùng ID;
bỏ strip; bỏ sort; sai code; bỏ hash check nhóm; nhận thừa khóa. Script thử độc lập
ban đầu được chuyển vào tests để tái lập, không chỉ lưu một tuyên bố đã chạy.

Hash source chuẩn hóa CRLF→LF:
`3740ea36f36ec787eb64284ac50ac7c339d4e09a13f15c3178e8cce2ee1da04a`.
TRAIN-02 pin hash này; thiếu hoặc khác hash bị chặn. Có test CRLF Windows và thay
nội dung làm pin không khớp. Module và pin cùng PR để được anh merge đồng thời;
không triển khai production trước merge.

Full Linux ngoài sandbox: **807 passed, 2 skipped**, 69,96 giây, một cảnh báo AnyIO
cũ. CI Ubuntu/Windows được cập nhật trong PR tại đúng head. Người dùng merge.
Rollback revert PR; không migration/DB hoặc quyền provider cần thu hồi.
