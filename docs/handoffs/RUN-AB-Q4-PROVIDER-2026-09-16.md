# RUN-AB-Q4-PROVIDER — kế hoạch triển khai 16/09/2026

## Quyết định đã khóa

- Runtime đích dùng **Qwen2.5-3B Instruct GGUF Q4_K_M**, không dùng Q3_K_M làm cấu hình phát hành.
- Khóa `num_ctx=2048` cho chat, agent, trích xuất và các phép đo so sánh.
- Một agent/worker chạy tuần tự trên ASUS 8 GB.
- Checkpoint ứng viên là adapter QLoRA step 40, adapter SHA-256
  `3e60051c7df52204efbb64b70c94d07bd26eef798fa2b442114589f85d21a14f`.
- Không train thêm trước khi hoàn tất A/B kín. Không gọi cloud, phát sinh chi phí,
  gửi hồ sơ thật hoặc phát hành đầu ra nếu chưa qua cổng tương ứng.
- PR #82 đang dùng Q3_K_M là phụ thuộc cần chỉnh sang Q4_K_M hoặc được thay thế;
  không merge nguyên cấu hình Q3 rồi coi đó là runtime đích.

## Phạm vi ngày 16/09/2026

### 1. Bảo toàn và kiểm artifact

- Xác minh ZIP step 40 đã có bản sao bền vững:
  `AIMarx-Qwen2.5-3B-QLoRA-pilot-step40.zip`.
- ZIP SHA-256 phải bằng
  `a1969af090e82d39bc612718822f88227935284902075ff39380d4d3f5a5fb`.
- Giải nén vào thư mục mới; từ chối path tuyệt đối, `..`, sai hash hoặc thiếu
  manifest. Không ghi đè checkpoint cũ.
- Ghi base revision, adapter hash, công cụ merge/chuyển GGUF và tham số lượng tử hóa.

### 2. Tạo hai runtime so sánh công bằng

- A: Qwen2.5-3B Instruct base, GGUF Q4_K_M.
- B: cùng base revision + adapter step 40 đã merge, GGUF Q4_K_M.
- Cả hai dùng cùng prompt, sampler, seed policy, `num_ctx=2048`, giới hạn output,
  số luồng và thứ tự ca. Không so base Q3 với candidate Q4.
- Lưu SHA-256 của hai GGUF và Modelfile; Ollama chỉ bind loopback.
- Không được cắt âm thầm input vượt 2.048 token. Ca vượt giới hạn phải báo
  `context_overflow` hoặc đi qua chiến lược chia đoạn đã khóa trước khi mở đáp án.

### 3. A/B kín độc lập

- Tối thiểu 120 ca chưa xuất hiện trong train/validation/smoke công khai.
- Tách theo `source_family_id`, `template_family_id` và source hash; kiểm near
  duplicate trước khi chạy.
- Người chạy chỉ nhận input; không nhận reference, rubric, nhãn A/B hoặc đáp án.
- Đảo ngẫu nhiên A/B bằng mapping niêm phong; chỉ mở mapping sau khi chấm xong.
- Chấm các tiêu chí: phân loại đúng, chọn luồng đúng, JSON/schema hợp lệ, trích dẫn
  đúng nguồn, abstention/hỏi lại khi thiếu dữ kiện, không bịa và latency/RAM.
- Lỗi nghiêm trọng: tự nâng quyền dữ liệu, gửi cloud không có grant, bịa căn cứ,
  báo hoàn thành giả, sửa/phát hành tài liệu hoặc bỏ qua human approval.
- Báo cáo phải có số thắng/thua/hòa theo từng nhóm, khoảng tin cậy hoặc kiểm định
  ghép cặp phù hợp, danh sách lỗi nghiêm trọng và kết luận go/no-go. Không chỉ dùng
  loss/perplexity để quyết định.

### 4. Cổng chọn model

Chỉ chọn candidate step 40 khi:

- không có lỗi nghiêm trọng về quyền, nguồn hoặc phê duyệt;
- candidate tốt hơn base có ý nghĩa thực tế trên chỉ số chính đã khóa trước khi
  mở mapping;
- schema/citation/abstention không thoái lui;
- chạy ổn định trên ASUS với `num_ctx=2048`, không OOM;
- artifact, cấu hình và kết quả đều tái lập được bằng hash.

Không đạt thì giữ base/Q3 hiện hành làm rollback, phân tích lỗi và đề xuất dữ liệu
bổ sung. Không tự tăng step 60/80 và không mở TRAIN-08 chỉ vì loss train còn giảm.

### 5. Runtime và provider thật

- Provider local đích trỏ đúng model Q4_K_M đã thắng cổng A/B; kiểm `/api/ps`,
  model identity, context 2.048, loopback và một worker.
- UI, API và MCP phải đi qua cùng façade/provider gateway; không có đường gọi tắt.
- Chạy regression, smoke UI/API/MCP, restart/recovery và kiểm job không bị báo hoàn
  thành giả khi provider lỗi.
- Provider cloud chỉ được bật sau test mock và probe giả lập/khử nhạy cảm, bằng
  credential store hệ điều hành, snapshot bất biến, explicit grant, allowlist,
  timeout, retry có giới hạn, ledger và budget khác 0 do người dùng duyệt.
- Test thật ban đầu chỉ một request giả lập, chi phí nằm trong hạn mức đã duyệt.
  Không gửi tài liệu nội bộ/hạn chế/unknown. Không tự phát hành DOCX hay gửi ra ngoài.
- Sau probe, thu hồi grant thử nghiệm hoặc trả budget về 0 nếu không tiếp tục.

## Bằng chứng phải bàn giao

1. Hash ZIP, adapter, hai GGUF và cấu hình runtime.
2. Manifest bộ kín chỉ chứa metadata trước khi mở; gold/rubric giữ ngoài input.
3. Raw output A/B, mapping sau mở niêm phong và báo cáo chấm.
4. RAM đỉnh, latency p50/p95, lỗi/OOM và phiên bản Ollama/runtime.
5. Kết quả regression cùng smoke UI/API/MCP.
6. Ledger của probe provider thật đã loại bỏ secret và nội dung nhạy cảm.
7. Quyết định go/no-go, model được chọn và lệnh rollback.

## Phân công

- **Astra:** khóa rubric/ngưỡng trước khi chạy, kiểm tính kín, mở mapping, phân tích
  thống kê và quyết định go/no-go.
- **Sol:** chuẩn bị runner, merge/convert Q4_K_M, chạy A/B bất biến, benchmark và
  tích hợp runtime/provider theo hợp đồng.
- **Anh Khang:** duyệt bộ dữ liệu, việc mở cổng provider thật, ngân sách và sản phẩm
  cuối. A/B không thay quyền duyệt của người dùng.

## Điểm dừng

PR này chỉ khóa kế hoạch và tiêu chí cho ngày mai. Chưa chạy A/B, chưa chuyển GGUF,
chưa đổi runtime, chưa bật provider thật và chưa phát sinh chi phí.
