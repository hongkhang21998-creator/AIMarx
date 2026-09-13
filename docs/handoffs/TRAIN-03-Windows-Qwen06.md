# TRAIN-03 — Windows Qwen3 0.6B, giai đoạn preflight

Ngày 13/09/2026. Base `ed25387733ee681b838bebb156de1ae86720892c`, issue #53,
nhánh `codex/train03-windows-qwen06-smoke`. Codex thực hiện, không subagent.

## Kết quả

Đã tạo tooling thuần Python trong `training/windows_qwen06`: cấu hình bảo thủ,
preflight RAM/đĩa/stack, chuẩn bị đúng snapshot đã duyệt, kiểm checksum/rò review,
completion mask, watchdog và checkpoint atomic có hash/prune an toàn. Model duy nhất
được pin là `Qwen/Qwen3-0.6B` revision
`c1899de289a04d12100db370d81485cdf75e47ca`; chưa tải model.

Export thật vào thư mục tạm Windows đạt 80 train và 20 validation, đúng SHA-256
`1062862...e4a2b` và `8d3c43...ad1741`. Không xuất/dùng 20 smoke-test.

Preflight thực tế: Windows 11, Python 3.14.6 trong venv ứng dụng, RAM tổng 7,784 GiB,
khả dụng 2,914 GiB, D trống 73,365 GiB; torch/transformers/peft/accelerate chưa có.
Kết quả `ready_to_load_model=false`: RAM gate và stack gate không đạt; disk gate đạt.
Do đó 1-step/resume/5-step là **NOT_RUN** đúng cổng issue. Không cài package,
tạo venv train, tải model, sử dụng GPU/cloud hoặc sinh chi phí. Lock dependency chỉ
được tạo sau khi có Python/backend tương thích đã cài và kiểm; không tạo lock giả.

## Kiểm thử và giới hạn

`python -m pytest -q tests/test_train03_windows.py`: 7 passed. Ca kiểm gồm mask/EOS,
hash/count/leak, checkpoint hỏng/ghi lỗi/prune, timeout, cổng độc lập và model lock.
Kiểm tập trung cùng split/TRAIN-02: **154 passed trong 27,66 giây**. Full Windows:
**811 passed, 5 skipped, 1 warning trong 61,91 giây**; warning deprecation AnyIO
cũ từ Starlette. Các skip không được tính là đã kiểm thành công.
Tooling chưa phải trainer PyTorch; chưa audit token bằng tokenizer thật, chưa baseline,
train, resume, adapter inference, GGUF hoặc backup Data1000. Watchdog trong-process
không bảo vệ giai đoạn import/load trước khi trainer khởi chạy; bước sau cần process
giám sát ngoài và timeout process tree.

Rollback bằng revert PR; không migration/runtime/model artifact. Output tạm không
được commit. Sau khi giải phóng RAM đạt 4 GiB, cài môi trường train riêng đã pin,
chạy lại preflight rồi mới tiếp tục token audit và 1-step. Anh Khang merge PR.
