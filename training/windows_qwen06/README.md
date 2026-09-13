# TRAIN-03 Windows Qwen3 0.6B

Tooling bảo vệ cho phép thử LoRA CPU local. Chạy `python -m training.windows_qwen06.preflight`
trước mọi tải model. Exit 2 nghĩa là dừng; không hạ ngưỡng. Môi trường train phải là
`.venv-train-qwen06`, tách khỏi `.venv` ứng dụng. Chưa có lock vì máy chỉ có Python
3.14, stack train chưa được cài/kiểm và RAM gate chưa đạt; không ghi một lock giả.

Export phải tạo mới từ snapshot đã duyệt, sau đó kiểm đúng checksum issue #53.
Checkpoint ghi thư mục tạm, băm file rồi mới publish; resume phải đọc manifest và
trạng thái optimizer/scheduler/RNG do backend ghi. Module không upload hoặc gọi cloud.

Trainer model thật chưa được kích hoạt: chỉ bổ sung guard/data/checkpoint primitives.
Sau khi có Python/backend tương thích và RAM >= 4 GiB, gói tiếp theo phải pin model
revision, dependency lock, kiểm token/mask bằng tokenizer thật rồi mới chạy 1 step.
