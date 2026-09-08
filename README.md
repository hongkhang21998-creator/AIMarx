# Trợ lý văn bản local

Bản thử nghiệm một người dùng: nhập PDF có chữ, DOCX hoặc TXT → đọc nguồn qua FastMCP → LangGraph trích xuất và kiểm tra → phiếu xử lý, việc đề xuất và dự thảo DOCX → người dùng sửa và duyệt đúng phiên bản. Dữ liệu ở máy local, model dùng Ollama tại `127.0.0.1:11434`; không có fallback cloud.

## Chạy

Python 3.12. Cài dependency từ bản khóa đã kiểm thử:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/pip install --no-deps --no-build-isolation -e .
TLVB_MODE=demo scripts/run-local.sh
```

Mở http://127.0.0.1:8765. Demo được gắn nhãn rõ, chỉ tạo phiếu rỗng có chỗ cần bổ sung; **không giả kết quả trích xuất AI**. Nhập một TXT UTF-8, bấm trích xuất rồi điền trường và chọn đoạn nguồn. Dữ kiện phải được chép nguyên văn từ đoạn đã chọn. Lưu tạo phiên bản mới; xác nhận/từ chối áp dụng cho phiên bản và hash hiện tại. Tải DOCX để kiểm tra bố cục.

Dùng model thật sau khi đã cài Ollama và tải model phù hợp RAM:

```bash
TLVB_MODE=ollama TLVB_MODEL=qwen3:0.6b scripts/run-local.sh
```

Tên model là cấu hình, không phải khuyến nghị chất lượng nghiệp vụ. Model nhỏ cần đánh giá riêng tiếng Việt. Khi không có Ollama/model, tài liệu ghi trạng thái `model_unavailable`; người dùng có thể thử lại. Không suy diễn hạn từ “khẩn” hay số ngày tương đối, không chuẩn hóa ngày tự động.

| Biến | Mặc định |
|---|---|
| `TLVB_DATA` | `data` tính từ thư mục chạy |
| `TLVB_MODE` | `ollama` (`demo` để thử không model) |
| `TLVB_MODEL` | `qwen3:0.6b` |
| `TLVB_PORT` | `8765` |

Chỉ chạy **một tiến trình UI, một worker**, giữ DB trên đĩa local. CLI luôn bind loopback. Không đưa qua reverse proxy hoặc mạng LAN: MVP dùng quyền tài khoản máy và token chống CSRF, chưa có đăng nhập nhiều người. `scripts/run-ollama.sh` dành cho bộ Ollama đã cài tại `.runtime/ollama/bin/ollama`, bật `OLLAMA_NO_CLOUD=1` và lưu model ở `.runtime/models`. Xem [vận hành](docs/DEPLOYMENT.md).

## Dữ liệu và kiểm soát

- SHA-256 chống trùng nội dung dù đổi tên; bản gốc được tạo độc quyền, đặt chỉ đọc. File thay đổi là tài liệu mới. Đây không phải kho WORM chống quản trị viên sửa.
- SQLite giữ tài liệu, nguồn, tất cả phiên bản, chế độ/model và lịch sử duyệt. Sổ việc lấy từ phiên bản mới nhất; chỉ `approved` là đã xác nhận. Không có việc/lịch tự gửi ra ngoài.
- Trường quan trọng dùng `value`, `block_id`, `quote`; mã kiểm tra quote tồn tại trong đúng nguồn và value nằm trong quote. Kiểm tra này chứng minh xuất xứ chữ, **chưa chứng minh model phân loại đúng ý nghĩa**; người dùng phải đối chiếu.
- Dự thảo luôn mang nhãn chờ kiểm tra; mẫu phiếu kỹ thuật chưa được xác nhận là mẫu hành chính. Việc duyệt không biến DOCX thành văn bản phát hành.
- Mỗi lần sửa hoặc trích xuất tạo phiên bản mới và cần duyệt lại. Trang cũ không duyệt/lưu đè được phiên bản mới. Lịch sử lưu lý do, thời gian SQLite UTC; người duyệt ngầm là người dùng tài khoản local, chưa quản lý danh tính nhiều người.
- Luồng dùng FastMCP Client in-memory gọi `read_document`, sau đó LangGraph `extract → validate`. Công cụ MCP chỉ đọc (`list_documents`, `read_document`, `get_evidence`), không có approve/shell/SQL/đường dẫn tùy ý. Chạy MCP độc lập bằng `.venv/bin/tro-ly-mcp` qua stdio.

## Giới hạn và phần chưa triển khai

Giới hạn file 10 MB, PDF 100 trang, tổng chữ 60.000 ký tự; nguồn gửi model tối đa 5.000 ký tự kể cả cấu trúc JSON, context 8.192 và đầu ra 2.048 token. Tài liệu lớn bị từ chối thay vì cắt âm thầm. Chưa chia đoạn rồi tổng hợp. Chưa có sandbox parser riêng hoặc kiểm soát thời gian/đỉnh RAM cứng: chỉ thử file tin cậy đã khử nhạy cảm trong giai đoạn này.

PDF có trang không đọc ra chữ chuyển `needs_ocr` và không chạy model. OCR/Docling còn hoãn cho cấu hình máy nhỏ và cần bộ mẫu kiểm thử; không coi PDF scan đã được hỗ trợ đầy đủ. DOCX đọc đoạn thân và bảng; chưa đọc ảnh, textbox, header/footer hoặc chú thích. File DOC cũ/mật khẩu chưa hỗ trợ.

SQLite lưu mốc nghiệp vụ sau mỗi thao tác; LangGraph **chưa có durable checkpointer/interrupt**, chưa resume giữa một lời gọi model. Nếu dừng khi xử lý, nguồn vẫn còn và người dùng bấm thử lại. Ghi draft qua file tạm rồi đổi tên; crash trước commit có thể để lại draft mồ côi, chưa có reconciler tự động. Các tác vụ được tuần tự hóa trong một Service; không chạy nhiều UI cùng kho.

Các giai đoạn tiếp theo còn gồm: mẫu hành chính do người dùng xác nhận; OCR/Docling và đánh giá 30–50 mẫu; trường người phụ trách, hồ sơ liên quan, tìm kiếm; checkpoint/lease/retry và đối soát file; watcher; lịch/outbox; quy trình backup/restore đã diễn tập; benchmark chất lượng và bảo mật trước dữ liệu nghiệp vụ thật.

## Kiểm thử

```bash
.venv/bin/pytest -q
```

Bộ test dùng dữ liệu tổng hợp: chống trùng, khởi động lại và lịch sử, nguồn bịa, duyệt/lưu phiên bản cũ, model vắng, demo, scan cần OCR, upload CSRF/origin và FastMCP Client thực. Test model vắng dùng mock mạng; không thay thế thử nghiệm trích xuất model thực.
