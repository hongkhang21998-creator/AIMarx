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
batch 1, context 2.048 và tối đa 5 optimizer steps. Context 2.048 phù hợp hơn môi
trường GPU; mọi mẫu vẫn được audit token thật và job dừng nếu có mẫu vượt giới
hạn, không truncation.

Dữ liệu được export trong Colab từ snapshot approved; chỉ 80 train và 20
validation với checksum đã nghiệm thu. 20 smoke-test không được export. Phase 1
chạy một process tới step 1. Phase 2 là process mới, phục hồi checkpoint Trainer
gồm adapter, optimizer, scheduler và RNG rồi chạy tới tổng step 5. Checkpoint cuối
có manifest/hash và được tải ZIP về máy; không push model lên Hugging Face hoặc
mount Drive.

Tại thời điểm tạo PR, code và test local có thể được nghiệm thu nhưng GPU smoke
chỉ được gọi là thành công khi notebook thực tế sinh `checkpoint-5` và manifest
`global_step=5`. Kết quả năm bước không chứng minh chất lượng nghiệp vụ tăng.

