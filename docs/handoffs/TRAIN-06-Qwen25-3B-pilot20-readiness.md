# TRAIN-06 — Qwen2.5-3B pilot step 20 readiness

Nhánh `codex/qwen25-3b-step20`. Runner giữ QLoRA NF4, rank 8/alpha 16,
microbatch 1, gradient accumulation 4, context 2.560 và dữ liệu approved 80/20.
Trần 20 optimizer step tương ứng một effective epoch; không dùng smoke-test để
train.

Notebook mới tái lập checkpoint-1 và checkpoint-5 trên runtime mới, bắt buộc
kiểm hai cổng trước khi resume đến checkpoint-20. Sau đó đánh giá đúng 20
validation, đóng gói ZIP và kiểm đường dẫn entry. Không Drive, Hub push hoặc
compute trả phí.

Lý do phải tái lập: runtime Colab ngày 14/09 đã đóng; checkpoint-5 chỉ còn hash
và handoff, chưa có bản sao local. Không tuyên bố resume từ artifact không còn.

Đây là pilot kỹ thuật một epoch. Dù validation loss giảm, vẫn cần A/B đầu ra và
nghiệm thu kín độc lập N≥120 trước khi kết luận chất lượng nghiệp vụ/production.
