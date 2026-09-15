# Nguyên tắc workflow và dữ liệu huấn luyện cho 8 agent

## Ranh giới hệ thống

Localhost là vùng tin cậy: nhận và giữ Word/PDF gốc, trích xuất/OCR, quản lý
nguồn, công cụ, trạng thái, audit và quyền duyệt. Colab hoặc GPU server chỉ là
worker suy luận không tin cậy; worker không nhận đường dẫn local, file nhị phân,
khóa API, quyền công cụ hoặc trường phê duyệt.

```text
Word/PDF → localhost ingest/parse → agent workflow → model gateway
                                              ↓ HTTPS, text tối thiểu
                                      Colab Qwen 3B + adapter
                                              ↓ JSON chưa tin cậy
                localhost kiểm schema/nguồn → người duyệt → xuất kết quả
```

Mọi agent dùng chung model profile đã pin nhưng có prompt version, schema đầu ra
và quyền công cụ riêng. Agent không gọi thẳng endpoint model; chỉ gửi
`InferencePacket` qua gateway. URL và token endpoint do gateway giữ, không nằm
trong packet hoặc dữ liệu huấn luyện.

## Tám vai trò và thứ tự

1. `intake`: phân loại yêu cầu và phát hiện dữ liệu thiếu.
2. `research`: đề xuất truy vấn; công cụ local lấy và xác minh nguồn.
3. `analysis`: tách dữ kiện, thẩm quyền, thời hạn và vấn đề.
4. `drafting`: tạo dự thảo có dẫn `source_id`.
5. `format_review`: kiểm tra thể thức và trường bắt buộc.
6. `evidence_review`: đối chiếu từng nhận định với nguồn local.
7. `risk_review`: tìm mâu thuẫn, vượt quyền và rủi ro.
8. `finalizer`: hợp nhất đề xuất; không có quyền phê duyệt.

Ba agent review chạy sau drafting và có thể song song. Finalizer chỉ sẵn sàng
khi cả ba hoàn tất. Điểm kết thúc luôn là `human_review`, không phải `approved`.

## Hợp đồng gửi model

- File gốc không rời localhost. Packet chỉ chứa tối đa 20 đoạn text, mỗi đoạn
  gắn document hash, version, fragment ID và trang nếu có.
- Evidence phải `verified=true`, quote phải xuất hiện nguyên văn trong fragment,
  `source_id` không được trùng.
- Model trả đề xuất; mọi finding phải dẫn ít nhất một `source_id` tồn tại trong
  packet. Schema cấm trường `approved` và mọi trường lạ.
- Không tự retry vô hạn, đổi endpoint/model hoặc gọi công cụ. Timeout/retry,
  idempotency, consent, ngân sách và audit thuộc gateway hiện hữu theo PSC-01.

## Điều kiện một mẫu được dùng để train agent

Kết quả model hoặc audit log không tự trở thành gold. Mẫu chỉ đủ điều kiện khi:

1. `human_status == approved` trên đúng task, agent và phiên bản;
2. người dùng cấp riêng `training_approved=true`;
3. người dùng cấp riêng `export_approved=true`;
4. packet đã qua kiểm nguồn và result đã qua kiểm citation;
5. tập train/validation/test được tách theo họ hồ sơ, không rò đáp án kín.

Quyền duyệt văn bản, quyền gửi inference và quyền xuất dữ liệu train là ba quyền
khác nhau. Adapter chung học năng lực nghiệp vụ; prompt, công cụ, bộ nhớ và quyền
của từng agent vẫn tách riêng.

## Phạm vi PR này

`agent_workflow.py` và pytest khóa hợp đồng, graph tám vai trò, binding nguồn và
điều kiện xuất mẫu train. PR này chưa mở tunnel Colab, chưa gửi dữ liệu, chưa
thêm route UI/API và chưa thay luồng MVP đang dùng Ollama. PR tích hợp kế tiếp
phải dùng chính hợp đồng này, dữ liệu synthetic trước và cổng PSC-01 hiện có.
