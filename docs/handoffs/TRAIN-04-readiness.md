# TRAIN-04 — sẵn sàng đánh giá đầu ra sau pilot

Base main `d3aa1eb217c43b45feb875c4b9728a45ec8bcd4b`, issue #65, nhánh
`codex/train03-domain-eval`. Công cụ được notebook pin tại commit
`5b0f4330ac5aa3ecd9394de50c504d0fbe464147`.

20 smoke-test đã duyệt được xuất thành input inference với đúng bốn trường `id`,
`input`, `instruction`, `output_schema`; SHA-256 file input là
`b6dd7f287abdd6e37a2854f2994c2c212ffb5c0da8392bc17a31a735412eb719`.
Reference/rubric nằm trong file tách riêng và không được đưa vào model. Tập này đã
công khai trong repo, nên chỉ là hồi quy cố định chứ không phải test mù.

Notebook yêu cầu checkpoint-20 trong cùng runtime Colab T4, xác minh manifest và
identity rồi sinh base/adapter tuần tự bằng greedy decoding. Gói review tráo A/B
theo seed cố định; mapping và gold nằm trong ZIP riêng chỉ mở sau khi người duyệt
đã lưu và hash nhận xét. Scorer tự động chỉ kiểm JSON/schema/worker/nguồn/quote;
không tự quyết định chất lượng nghiệp vụ.

Kiểm thử local TRAIN-03 + TRAIN-04 đạt 23 ca. Chưa chạy 40 lượt inference và chưa
có nhận xét của anh Khang. Không train/tune, không dùng Drive, không upload model,
không phát sinh chi phí. Nghiệm thu chuyên ngành cuối vẫn cần bộ kín độc lập tối
thiểu 120 ca được duyệt và cấp quyền riêng.
