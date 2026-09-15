# TRAIN-07 — kết quả Qwen2.5-3B tiếp tục đến step 40

Ngày chạy: 2026-09-15 (Asia/Ho_Chi_Minh)

## Phạm vi và tái lập

- Notebook: `notebooks/TRAIN_07_Qwen2_5_3B_Continue40_Colab.ipynb`.
- Runner bất biến: `6c9bc1d116ba8383ee86dbbf3f6739a5192237a3`.
- Base model: `Qwen/Qwen2.5-3B-Instruct`, revision
  `aa8e72537993ba99e69dfaafa59ed015b17504d1`.
- Tesla T4 miễn phí; QLoRA 4-bit NF4, microbatch 1, gradient accumulation 4,
  context 2.560. Không Drive, Hub hoặc compute trả phí.
- Vì artifact step-20 trước chưa có backup local bền vững, phiên này tái lập
  tuần tự step 1 → 5 → 20 rồi mở cổng cuối và train đến step 40.
- Tổng 40 optimizer steps = hai effective epoch trên 80 mẫu train đã duyệt.

## Checkpoint 40

- `global_step`: 40.
- Train SHA-256:
  `1062862c5db0c466de2b2ac20c3f217edabfcaa84ea34304c28c46a9758e4a2b`.
- Validation SHA-256:
  `8d3c43d3d69df8c7c58cba9733e76b1619d77629a144fae946468c8c56ad1741`.
- Adapter SHA-256:
  `3e60051c7df52204efbb64b70c94d07bd26eef798fa2b442114589f85d21a14f`.
- Checkpoint step-20 tái lập trong phiên có adapter SHA-256
  `05e35da028dc07c1b6b84e666b0208003da011ea48215497839b97e14ef79b76`.
- Ba gate hoàn tất, không OOM hoặc ngắt runtime.

## Validation đối chứng

Evaluator dùng 20 mẫu validation và 8.803 completion token, dtype
`torch.float16`, trên Tesla T4:

| Mô hình | Loss | Perplexity |
| --- | ---: | ---: |
| Base | 0.521681446602815 | 1.6848582684765687 |
| Adapter step 40 | 0.291682452109 | 1.3386778558084047 |

`adapter_minus_base_loss = -0.229998994493815`; evaluator trả trạng thái
`adapter_better_on_validation`.

## Gói artifact

- Tên: `AIMarx-Qwen2.5-3B-QLoRA-pilot-step40.zip`.
- Kích thước: 340.473.661 byte.
- Số entry: 40; kiểm tra path tuyệt đối và `..` đều đạt.
- ZIP SHA-256:
  `a1969af090e82d39bc612718822f88227935284902075ff39380d4d4d3f5a5fb`.
- Colab đã tạo và kích hoạt tải ZIP xuống trình duyệt; chưa xác nhận backup
  local bền vững nếu chưa thấy file trong thư mục tải xuống.

## Kết luận và giới hạn

Step-40 là pilot kỹ thuật tốt hơn base trên validation hiện tại. Đây chưa phải
nghiệm thu chuyên ngành hoặc production-ready: validation chỉ 20 ca và không mù.
Trước khi dùng adapter chung cho tám agent, cần A/B kín độc lập tối thiểu 120 ca,
kiểm citation/abstention theo vai trò và giữ human approval ở đầu ra cuối.
