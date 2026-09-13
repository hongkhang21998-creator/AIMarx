# TRAIN-03 — Colab Qwen3-0.6B smoke

Ngày 13/09/2026. Base `7e82cb384e2d0ac07f87fae180f032dd8c7f6b83`,
issue #53, nhánh `codex/train03-colab-qwen06`. Không dùng subagent.

Anh Nguyen Hong Khang chuyển nơi train từ Windows sang Google Colab và cho phép
dùng bộ synthetic đã duyệt ở đó, với điều kiện không phát sinh chi phí. Kiểm tra
trực tiếp trang Colab cho thấy không có compute units; do đó gói hiện có không
được coi là Colab Pro. Notebook chỉ chạy khi free tier cấp GPU và không có thao
tác mua tài nguyên.

Phạm vi này không sửa tooling Windows đang được tác vụ khác tiếp tục. Notebook
khóa `Qwen/Qwen3-0.6B` revision
`c1899de289a04d12100db370d81485cdf75e47ca`, non-thinking, LoRA r=8/alpha=16,
batch 1, context 4.096 và tối đa 5 optimizer steps. Lần chạy T4 phát hiện một
mẫu cần 2.381 token, nên context được tăng trong cấu hình Colab; mọi mẫu vẫn được
audit token thật và job dừng nếu có mẫu vượt giới hạn, không truncation.

Dữ liệu được export trong Colab từ snapshot approved; chỉ 80 train và 20
validation với checksum đã nghiệm thu. 20 smoke-test không được export. Phase 1
chạy một process tới step 1. Phase 2 là process mới, phục hồi checkpoint Trainer
gồm adapter, optimizer, scheduler và RNG rồi chạy tới tổng step 5. Checkpoint cuối
có manifest/hash và được tải ZIP về máy; không push model lên Hugging Face hoặc
mount Drive.

Tại thời điểm tạo PR, code và test local có thể được nghiệm thu nhưng GPU smoke
chỉ được gọi là thành công khi notebook thực tế sinh `checkpoint-5` và manifest
`global_step=5`. Kết quả năm bước không chứng minh chất lượng nghiệp vụ tăng.

## Kết quả chạy Colab thực tế

Ngày 13/09/2026, phiên Colab free cấp Tesla T4. PyTorch báo 14,563 GiB VRAM;
job dùng FP16. Lượt token audit đầu tiên dừng đúng cổng vì một mẫu cần 2.381
token với context 2.048. Sau khi tăng riêng cấu hình Colab lên 4.096, audit 100
mẫu đạt minimum 1.496, maximum 2.448, mean 1.878,56 và `over_limit=0`.

Process đầu chạy một optimizer step trong 11,69 giây và tạo `checkpoint-1`.
Process mới nạp checkpoint đó, phục hồi state và chạy tới `checkpoint-5` trong
37,72 giây; loss smoke cuối là 0,578054. Manifest giữ SHA train
`1062862c5db0c466de2b2ac20c3f217edabfcaa84ea34304c28c46a9758e4a2b`, validation
`8d3c43d3d69df8c7c58cba9733e76b1619d77629a144fae946468c8c56ad1741` và hash
từng file checkpoint. ZIP `AIMarx-Qwen3-0.6B-LoRA-smoke-step5.zip` đã được tải
xuống từ Colab. Đây là bằng chứng pipeline chạy được, chưa phải đánh giá chất
lượng nghiệp vụ hoặc bản triển khai production.
