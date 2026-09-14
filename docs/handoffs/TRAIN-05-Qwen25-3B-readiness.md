# TRAIN-05 — Qwen2.5-3B QLoRA readiness

Issue #68, nhánh `codex/qwen25-3b-qlora`. Chọn
`Qwen/Qwen2.5-3B-Instruct` revision
`aa8e72537993ba99e69dfaafa59ed015b17504d1` vì đây là model Qwen chính
thức trong dải 2,5–3 tỷ tham số. Đây là baseline mới, không resume hoặc
so sánh loss trực tiếp với checkpoint Qwen3-0.6B.

Runner tách riêng dùng QLoRA 4-bit NF4 double quantization, LoRA rank 8,
context 1.024, microbatch 1 và gradient accumulation 4. Cổng Colab yêu cầu
ít nhất 14 GiB VRAM và 20 GiB disk trống; dữ liệu vượt context bị chặn,
không cắt gold.

Notebook dừng bắt buộc sau checkpoint-1. Chỉ sau khi kiểm manifest, OOM và
tài nguyên mới đổi cờ duyệt để resume tới checkpoint-5. Chưa có quyền
chạy 20 step, smoke A/B, Drive, Hub push hoặc compute trả phí.

Trạng thái: code/notebook chỉ được kiểm tra local; chưa tải model, chưa
chạy Colab và chưa phát sinh chi phí.
