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

Tên model là cấu hình, không phải khuyến nghị chất lượng nghiệp vụ. Model nhỏ cần đánh giá riêng tiếng Việt. Khi không có Ollama/model, lỗi được ghi vào `error`/`error_kind` của tài liệu; người dùng có thể thử lại. Tài liệu **chưa có phiên bản nào** thì trạng thái chuyển thành `model_unavailable`. Tài liệu **đã có phiên bản** thì giữ nguyên trạng thái duyệt (`awaiting_review`/`approved`/`rejected`): một lần trích xuất hỏng không tạo phiên bản mới nên cũng không được thu hồi xác nhận đã có. Chỉ lần chạy thành công mới tạo bản chờ duyệt mới. Không suy diễn hạn từ “khẩn” hay số ngày tương đối, không chuẩn hóa ngày tự động.

| Biến | Mặc định |
|---|---|
| `TLVB_DATA` | `data` tính từ thư mục chạy |
| `TLVB_MODE` | `ollama` (`demo` để thử không model) |
| `TLVB_MODEL` | `qwen3:0.6b` |
| `TLVB_PORT` | `8765` |

Chỉ chạy **một tiến trình UI, một worker**, giữ DB trên đĩa local. CLI luôn bind loopback. Không đưa qua reverse proxy hoặc mạng LAN: MVP dùng quyền tài khoản máy và token chống CSRF, chưa có đăng nhập nhiều người. `scripts/run-ollama.sh` dành cho bộ Ollama đã cài tại `.runtime/ollama/bin/ollama`, bật `OLLAMA_NO_CLOUD=1` và lưu model ở `.runtime/models`. Xem [vận hành](docs/DEPLOYMENT.md).

## Chạy trên Windows

Cùng codebase, chạy **độc lập**, dữ liệu riêng, vẫn bind `127.0.0.1`. Đã chạy thật trên Windows 11 với Python 3.14 và `requirements.lock` hiện tại (`pip check` sạch).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
$env:TLVB_MODE = "demo"
powershell -ExecutionPolicy Bypass -File scripts\run-local.ps1
```

Khác biệt so với Linux, đã xử lý trong mã:

- `mkdir(mode=0o700)` **không có hiệu lực** trên Windows. Nếu `TLVB_DATA` nằm ngoài thư mục hồ sơ người dùng, giao diện hiện cảnh báo ngay đầu trang. Mã **không tự đổi ACL**: chạy sai `icacls /inheritance:r` có thể khóa mất quyền truy cập chính thư mục dữ liệu, nên đây là việc người dùng làm thủ công có chủ đích.
- Thuộc tính read-only của Windows chặn cả `os.replace` lẫn `os.remove`; `fsguard.thaw()` gỡ trước khi ghi đè hoặc xóa.
- Connection SQLite phải `close()`: `with conn` chỉ commit. Không đóng thì Windows giữ file handle, khóa DB và chặn xóa tệp.
- `PYTHONUTF8=1` là **bắt buộc** khi stdout bị chuyển hướng ra file hoặc chạy dưới dạng dịch vụ, nếu không tiếng Việt gây `UnicodeEncodeError` (cp1252). `run-local.ps1` đã đặt sẵn.
- Tạo symlink cần quyền `SeCreateSymbolicLinkPrivilege` nên test symlink tự bỏ qua; test junction thay thế để vẫn phủ hàng rào chặn thoát thư mục.

Ollama cho Windows phải cài riêng: gói `.tar.zst` trong `.runtime/downloads` là **bản Linux**. Model GGUF dùng chung được giữa hai hệ — sao chép `.runtime/models` sang là đủ, không cần tải lại.

## Dữ liệu và kiểm soát

- SHA-256 chống trùng nội dung dù đổi tên; bản gốc được tạo độc quyền, đặt chỉ đọc. File thay đổi là tài liệu mới. Đây không phải kho WORM chống quản trị viên sửa.
- SQLite giữ tài liệu, nguồn, tất cả phiên bản, chế độ/model và lịch sử duyệt. Sổ việc lấy từ phiên bản mới nhất; chỉ `approved` là đã xác nhận. Không có việc/lịch tự gửi ra ngoài.
- **Số ký hiệu, cơ quan ban hành, ngày ban hành lấy bằng quy tắc thể thức** (`header.py`), không lấy từ model: đo trên bộ chấm, model 0,6B bỏ trống hoặc bịa phần này. Quy tắc cắt nguyên văn từ nguồn; không khớp thì để trống cho người dùng điền, không đoán.
- **Model chỉ đề xuất việc.** Khung sinh dùng khoá tiếng Việt (khoá `number` tiếng Anh làm model điền `"1"`); model chỉ trả giá trị và mã đoạn, mã tự lấy `quote` từ đúng đoạn nguồn và chỉ nắn lệch hoa-thường/khoảng trắng. Không dùng ví dụ mẫu: model nhỏ chép nó sang văn bản khác. Đổi prompt thì phải chạy lại `evals/extraction/run_eval.py` — số đo và giới hạn ở `evals/extraction/BAO_CAO_2026-09-11.md`.
- Trường quan trọng dùng `value`, `block_id`, `quote`; mã kiểm tra quote tồn tại trong đúng nguồn và value nằm trong quote. Kiểm tra này chứng minh xuất xứ chữ, **chưa chứng minh model phân loại đúng ý nghĩa**; người dùng phải đối chiếu.
- Dự thảo luôn mang nhãn chờ kiểm tra; mẫu phiếu kỹ thuật chưa được xác nhận là mẫu hành chính. Việc duyệt không biến DOCX thành văn bản phát hành.
- Xác nhận đòi **bytes DOCX trên đĩa khớp `draft_hash`** đã lưu, không chỉ khớp hash nội dung JSON: người dùng xác nhận cái họ đọc trong DOCX. Dự thảo bị sửa hoặc mất tệp thì không xác nhận được, nhưng **vẫn từ chối được** — nếu chặn cả từ chối thì bản bị sửa sẽ kẹt ở `awaiting_review` vĩnh viễn.
- Phiên bản tạo trước khi có cột `draft_hash` mang hash rỗng và được coi là **chưa xác minh**, không phải đã xác minh: không tải và không xác nhận được, giao diện nói rõ. Cố ý **không** backfill bằng cách băm tệp đang nằm trên đĩa — băm sau sự việc chỉ đóng dấu lên đúng những byte tình cờ ở đó, kể cả byte đã bị sửa.
- Tài liệu `needs_ocr` bị chặn ở **tầng service**, tại `Service.save` — cửa ghi duy nhất mà run/manual/edit/save đều đi qua. Ẩn nút trên giao diện là việc của trải nghiệm, không phải hàng rào: các route vẫn nhận POST trực tiếp. Điều kiện cần OCR suy ra từ `blocks`/`warnings` chốt lúc nhập, không đọc cột `state` vì state bị ghi đè.
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

Trên Windows:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Bộ test dùng dữ liệu tổng hợp: chống trùng, khởi động lại và lịch sử, nguồn bịa, duyệt/lưu phiên bản cũ, model vắng, demo, scan cần OCR, upload CSRF/origin, FastMCP Client thực, dự thảo bị sửa/mất tệp, hash rỗng không được coi là đã xác minh, và chặn `needs_ocr` ở tầng service qua cả bốn cửa ghi. Test model vắng dùng mock mạng; không thay thế thử nghiệm trích xuất model thực.
