# TRAIN-05 — kết quả Qwen2.5-3B QLoRA step 5

Ngày chạy: 2026-09-14. PR cấu hình #71 được merge tại
`ef4120d13b6ef4291b45c430f4794c83a65ba4a9`; Colab checkout detached đúng
merge commit này. Phiên chạy là Tesla T4 miễn phí, không dùng compute trả phí,
không mount Drive và không push model lên Hub.

Token audit bằng tokenizer Qwen2.5-3B đo mẫu dài nhất cần 2.398 token. Context
2.048 đã dừng trước tải trọng số/optimizer; context 2.560 giữ nguyên toàn bộ gold
và chạy thành công. Cấu hình còn lại: QLoRA 4-bit NF4 double quantization, LoRA
rank 8/alpha 16, microbatch 1, gradient accumulation 4.

Checkpoint-1 được tạo trước và kiểm manifest, sau đó resume chính checkpoint này
đến checkpoint-5. Manifest step 5:

- model: `Qwen/Qwen2.5-3B-Instruct`
- revision: `aa8e72537993ba99e69dfaafa59ed015b17504d1`
- train SHA-256: `1062862c5db0c466de2b2ac20c3f217edabfcaa84ea34304c28c46a9758e4a2b`
- validation SHA-256: `8d3c43d3d69df8c7c58cba9733e76b1619d77629a144fae946468c8c56ad1741`
- adapter SHA-256: `cc9fe878570549cd5d177ace51981fb33eb0127a8e67f59db0f82937d7f40820`

Đánh giá 20 validation, 8.803 completion token, FP16 trên Tesla T4:

- base loss `0.521681446602815`, perplexity `1.6848582684765687`
- adapter loss `0.47600713589239374`, perplexity `1.609634502096055`
- adapter trừ base loss: `-0.04567431071042127`
- trạng thái: `adapter_better_on_validation`

Gói `/content/AIMarx-Qwen2.5-3B-QLoRA-step5.zip` có 38 entry,
340.626.010 byte, SHA-256
`9df4fc4770ca010c7ed2c0b3e56273735a96e3f02db3fa1d8e7764c3cef8fbdf`.
Gói hiện chỉ tồn tại trong runtime Colab; chưa ghi nhận backup local.

Đây là smoke kỹ thuật 5 optimizer step, không phải nghiệm thu chuyên ngành và
không cho phép suy rộng rằng 3B đã sẵn sàng sản xuất. Chưa chạy 20 step hoặc A/B
kín; nghiệm thu cuối vẫn cần bộ kín độc lập tối thiểu 120 ca.
