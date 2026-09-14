# TRAIN-03 — pilot Qwen3-0.6B tới step 20 trên Colab T4

Ngày 14/09/2026, từ main `85d7e97b09de2bb5a1f6b4281ea6ce7ce455feb2`,
code commit `ce188aca11c1bbaec8a0929e4172e66261ef2646` được chạy trên Tesla T4
miễn phí. Notebook tái tạo checkpoint-1, resume checkpoint-5 đã kiểm chứng, rồi
resume sang output pilot tới checkpoint-20. Microbatch 1 và gradient accumulation
4 làm 20 optimizer step tương đương đúng 80 mẫu train, tức một effective epoch.

Evaluator xác minh manifest, hash dữ liệu, model revision, adapter base, file
checkpoint và `global_step=20` trước khi nạp. Trên cùng 20 validation với 8.803
completion token, model gốc có loss 0,6562779318 và perplexity 1,9276042909;
adapter có loss 0,4265158024 và perplexity 1,5319107346. Delta adapter trừ base
là -0,2297621294. Adapter SHA-256 là
`fc3e47189d2b4d470a3897867238a401cc4741b603bdbdd03e9bf25e427748ac`.

ZIP `AIMarx-Qwen3-0.6B-LoRA-pilot-step20.zip` có 120.151.781 byte, 37 entry
và SHA-256 `65ca53c0aad203a046adeeb63ecee286798e8b1ccf9bd30c8c31db97277cd024`.
Hash và đường dẫn entry an toàn được kiểm trong chính runtime Colab. Lệnh tải đã
hoàn tất ở giao diện Colab, nhưng in-app browser không đặt file vào thư mục
`/home/asus/Downloads`; vì vậy chưa coi artifact là đã backup local hoặc Data1000.

Không có compute trả phí, Drive mount hay push model. 20 smoke-test không được
dùng để train, tune hoặc đánh giá. Loss validation giảm là cổng kỹ thuật, chưa
chứng minh chất lượng xử lý văn bản hành chính. Trước khi tăng step hoặc đổi model,
cần sinh đầu ra trên tập đánh giá tách biệt và để anh Khang duyệt nghiệp vụ.
