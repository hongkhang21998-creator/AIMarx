# TRAIN-06 — kết quả Qwen2.5-3B pilot step 20

Ngày chạy: 2026-09-15 (Asia/Ho_Chi_Minh)

## Phạm vi đã thực hiện

- Notebook: `notebooks/TRAIN_06_Qwen2_5_3B_Pilot20_Colab.ipynb`.
- Runner bất biến: `03bd6c91b3f84960bd7365f382ee13c72d15730f`.
- Base model: `Qwen/Qwen2.5-3B-Instruct` tại revision
  `aa8e72537993ba99e69dfaafa59ed015b17504d1`.
- Tesla T4 miễn phí; QLoRA 4-bit NF4, microbatch 1, gradient accumulation 4,
  context 2.560. Không dùng Drive, Hub hoặc compute trả phí.
- Tái lập tuần tự checkpoint 1, checkpoint 5 rồi checkpoint 20. Step 20 tương
  ứng một effective epoch trên 80 mẫu train đã duyệt.

## Bằng chứng checkpoint 20

- `global_step`: 20.
- Train SHA-256:
  `1062862c5db0c466de2b2ac20c3f217edabfcaa84ea34304c28c46a9758e4a2b`.
- Validation SHA-256:
  `8d3c43d3d69df8c7c58cba9733e76b1619d77629a144fae946468c8c56ad1741`.
- Adapter SHA-256:
  `bfc5ac16eb3181acc28eb939539cb78f6a83be5dcbe21144d1e94dce5acc5212`.
- Không có OOM hoặc ngắt runtime trong ba cổng.

## Đánh giá validation

Đánh giá dùng 20 mẫu validation, tổng 8.803 completion token, dtype
`torch.float16`, trên Tesla T4:

| Mô hình | Loss | Perplexity |
| --- | ---: | ---: |
| Base | 0.521681446602815 | 1.6848582684765687 |
| Adapter step 20 | 0.37688171956994976 | 1.4577318780203696 |

`adapter_minus_base_loss = -0.14479972703286526`; evaluator trả trạng thái
`adapter_better_on_validation`.

## Gói artifact

- Tên: `AIMarx-Qwen2.5-3B-QLoRA-pilot-step20.zip`.
- Kích thước: 339.853.534 byte.
- Số entry: 39; kiểm tra đường dẫn tuyệt đối và `..` đều đạt.
- ZIP SHA-256:
  `b2650bb49c5f27b2f651f351f48ffcc1b3edba5699e83ff450a1574d43bacc15`.
- Colab đã tạo và bắt đầu tải ZIP xuống trình duyệt. Chưa coi là có bản sao
  local bền vững cho tới khi file tải xuống được xác minh độc lập.

## Kết luận và giới hạn

Pilot kỹ thuật một epoch đã hoàn tất và adapter tốt hơn base trên tập validation
hiện tại. Đây chưa phải nghiệm thu chuyên ngành hoặc bằng chứng production-ready:
20 mẫu không mù có thể gần dữ liệu train. Trước khi dùng chung cho tám agent cần
A/B kín độc lập tối thiểu 120 ca, kiểm citation/abstention theo vai trò và giữ
human approval ở đầu ra cuối.
