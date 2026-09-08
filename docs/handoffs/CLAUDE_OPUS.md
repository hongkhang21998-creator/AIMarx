# Bàn giao cho Claude Opus — dừng phát triển theo yêu cầu người dùng

Ngày: 08/09/2026. Người dùng yêu cầu Codex tạm dừng viết code và để Claude Opus tiếp tục. Codex đã ngắt agent viết code; từ thời điểm đó chỉ kiểm kê, viết tài liệu bàn giao và đưa trạng thái lên draft PR. Chưa gọi hoặc giao trực tiếp cho Claude trong phiên này.

## 1. Đọc trước khi làm

- Repo riêng tư: https://github.com/hongkhang21998-creator/tro-ly-van-ban
- Issue phạm vi: https://github.com/hongkhang21998-creator/tro-ly-van-ban/issues/1
- Nhánh bàn giao: `codex/local-mvp`; base `b57167a54939610bb7f938bbfc793e3f9c49968e` trên `main`.
- Đọc `KE_HOACH_AI_AGENT.md`, `README.md`, `WORKLOG.md`, tài liệu này và diff draft PR.
- Workspace: `/home/asus/Documents/ChatGPT/AI-agent for me`.
- Người dùng: Nguyen Hong Khang; cần thuyết minh trước khi code, làm cẩn thận, không rõ thì hỏi. Agent code/tạo PR, người dùng merge. Ghi lại phạm vi và bàn giao để không giẫm chân tác vụ khác.
- Code hiện tại do GPT-6 Astra mức suy luận low triển khai theo chỉ định trước đó; hiện đã dừng. Claude tiếp quản nhánh này hoặc ghi rõ nhánh phụ thuộc, không tự merge.

## 2. Mục tiêu và quyết định còn hiệu lực

Trợ lý cá nhân: nhận văn bản → xác định việc có căn cứ → soạn dự thảo → người dùng sửa/duyệt → theo dõi xử lý. Laptop làm máy chủ theo yêu cầu mới nhất. Chạy local, không tự gửi văn bản hoặc fallback lên model cloud.

Laptop đã kiểm tra: Linux, i3-8130U, 2 nhân/4 luồng, RAM khoảng 7,1 GiB, SSD còn khoảng 175 GiB trước cài đặt. Máy phụ Windows 11 Home, i3-12100, 8 GB RAM, GT 710 1 GB chưa được kết nối/cài đặt. Không có yêu cầu đổi router/IP, mở LAN, cài SSH hay nâng cấp phần cứng trong tác vụ hiện tại.

Stack bản đầu: Python 3.12, FastAPI, SQLite, LangGraph, FastMCP, Ollama, pypdf, python-docx. OCR Docling chưa cài do cần thử tài nguyên và bộ mẫu. Model thử Qwen3 0.6B chỉ nhằm kiểm tra kỹ thuật, chưa có benchmark nghiệp vụ.

## 3. Code đã có

| File | Nội dung |
|---|---|
| `domain.py` | Schema phiếu, nhiệm vụ, deadline nguyên văn, kiểm tra value/quote/block nguồn |
| `parser.py` | PDF có chữ, DOCX thân/bảng, TXT UTF-8; cảnh báo scan, giới hạn file/text |
| `model.py` | Ollama local JSON schema, think=false, giới hạn đầu vào/đầu ra; demo rõ nhãn |
| `service.py` | Kho bản gốc SHA256, DB tài liệu/phiên bản/duyệt, MCP Client → LangGraph, DOCX |
| `mcp_server.py` | Công cụ chỉ đọc theo document ID, không có approve/shell/SQL tùy ý |
| `web.py` | Upload, xem nguồn, phiếu biểu mẫu, sửa/duyệt theo phiên bản, tải DOCX, sổ việc |
| `tests/test_workflow.py` | 10 test tổng hợp; xem phạm vi và giới hạn kiểm thử bên dưới |
| `scripts/run-local.sh`, `scripts/run-ollama.sh` | Khởi động local, giữ một worker/model, không cloud |
| `requirements.lock`, `pyproject.toml` | Dependency đã cài và thông tin package |
| `.github/workflows/tests.yml` | CI pytest/pip check trên Python 3.12; chưa xác nhận kết quả remote lúc viết bàn giao |

Đây là prototype một phần, không phải toàn bộ kế hoạch đã hoàn tất. DOCX hiện là phiếu xử lý thử nghiệm, chưa phải báo cáo/công văn theo mẫu nghiệp vụ người dùng.

## 4. Kiểm thử đã xác nhận và phần chưa kiểm thử

- Lần chạy xác nhận gần nhất: `timeout 60 .venv/bin/python -m pytest -q`, chạy ngoài sandbox: **10 passed, 1 warning, 2.41s**.
- Warning đến từ Starlette/AnyIO BlockingPortal deprecated, không phải assertion thất bại.
- Phạm vi: chống trùng/khôi phục DB, stale save/approval, nguồn bịa, model vắng (mock), demo/scan, upload CSRF/origin, MCP Client thật, biểu mẫu và từ chối, DOCX/broken parser, chặn đầu vào model quá lớn.
- `pip check`: không có dependency bị hỏng.
- HTTP thật trên laptop: GET `/` 200; upload TXT giả lập qua CSRF 200, trang nguồn hiển thị đúng. Trình duyệt đã mở được giao diện.
- **Sau lần 10 test pass**, agent thêm: lập phiếu thủ công khi chưa có kết quả model; provenance manual/ollama/demo; vô hiệu hóa nút review đã xử lý; cột `draft_hash`, migration nhẹ, draft chỉ đọc và kiểm tra hash khi tải. **Các thay đổi này chưa được chạy lại test trước khi người dùng yêu cầu dừng. Không tuyên bố commit bàn giao đã qua toàn bộ kiểm thử.**
- Chưa thử suy luận thật thành công. Chưa xác nhận chất lượng tiếng Việt hoặc nghiệp vụ. Chưa thử UI trên code mới nhất sau restart.
- Lưu ý môi trường Codex: TestClient/MCP in-memory treo trong sandbox do hạn chế loop/thread; chạy ngoài sandbox thì test qua. Bind localhost cũng cần ngoài sandbox. Không sửa mã để chữa nhầm lỗi môi trường này.

## 5. Dịch vụ và runtime local lúc bàn giao

- UI tại `http://127.0.0.1:8765/`: trả HTTP 200; chạy từ exec session `87230`. **Tiến trình nạp code trước các sửa cuối; không phản ánh đầy đủ working tree mới nhất.** Không có hot reload.
- Ollama API `http://127.0.0.1:11434/api/tags`: HTTP 200; exec session `97222`, version 0.33.3, `OLLAMA_NO_CLOUD=1`, một model, một lời gọi đồng thời.
- Ollama mới chỉ giải nén `bin/ollama` từ gói tải dở trước đó; log khởi động báo **thiếu llama-server binary**. API tags hoạt động không chứng minh inference hoạt động.
- Gói đầy đủ hiện đã tải xong và xác minh: `.runtime/downloads/ollama-verified.tar.zst`, 1.433.825.108 byte; SHA256 `c13cea8f3389db4145f8a6cb88d1747242a48639d7c13e3bda7c1ebdc6eebb2f`, khớp digest GitHub release v0.33.3. **Chưa giải nén gói đầy đủ** vì người dùng yêu cầu dừng.
- `.runtime/downloads/` khoảng 2,9 GB gồm archive và các phần tải; không cần tải lại, không tự xóa trước khi xác nhận đã dùng gói đúng.
- Model đã pull thành công, API xác nhận `qwen3:0.6b`, size 522.653.767 byte, digest `7df6b6e09427a769808717c0a93cadc4ae99ed4eb8bf5ca557c90846becea435`. Kho `.runtime/models/` khoảng 499 MB.
- Ollama tạo khóa mặc định ở `~/.ollama`; không đọc/copy/commit khóa. Runtime/model/DB/.venv bị gitignore.
- Python `.venv/bin/python` 3.12.14; runtime nền tại `/home/asus/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`.
- Systemd user trả `running`, chưa có unit `tro-ly-*`. **Chưa thiết lập tự khởi động sau đăng nhập/reboot**, không có unit hoặc script cài systemd.
- Máy phụ chưa đụng tới. Không có cổng LAN hoặc Calendar đang hoạt động.

Chỉ có dữ liệu tổng hợp trong `data/`: `mau-kiem-thu.txt` với nhãn “TÀI LIỆU GIẢ LẬP KIỂM THỬ — KHÔNG PHẢI CÔNG VĂN THẬT”, document ID `66d9a7786077220398a19573fec38380083cf07230a0a26e49cbeaea9c8b028c`. Không upload công văn thật.

## 6. Việc Claude cần xem xét trước

1. Kiểm kê diff và service đang chạy, không khởi chạy thêm một UI cùng DB. Chạy lại tests sau sửa cuối và bổ sung test manual/provenance/hash/migration.
2. **Còn dang dở:** `Service.review()` kiểm tra hash nội dung JSON nhưng chưa kiểm tra bytes DOCX khớp `draft_hash` lúc duyệt. Download có kiểm tra. Cần chốt ràng buộc phê duyệt và thêm test file bị sửa.
3. Migration cột `draft_hash` đặt chuỗi rỗng cho bản cũ; cần chính sách backfill/đánh dấu chưa xác minh và test. Không coi hash rỗng là đã xác minh.
4. Kiểm tra các cửa ghi `save/manual/edit` có chặn tài liệu `needs_ocr` đầy đủ phía service, không chỉ giao diện; xem lại xử lý lỗi HTTP và giới hạn upload không có Content-Length.
5. Khi tiếp tục triển khai được người dùng giao: giải nén gói Ollama đầy đủ đã xác minh, khởi động lại đúng một Ollama, thử một văn bản giả lập và đo RAM/thời gian. Model nhỏ có thể trả sai nguồn và phải bị chặn, không hạ kiểm tra chỉ để demo thành công.
6. Restart UI để chạy code đã chốt; thử luồng nhập → MCP/model hoặc thủ công → sửa → duyệt → tải DOCX bằng trình duyệt. Sau đó mới xét user systemd nếu cần.
7. Những phần chưa có: durable checkpointer/interrupt, OCR/Docling, hồ sơ/tìm kiếm, mẫu nghiệp vụ, watcher, Calendar/outbox, lease/retry/reconciler, backup/restore diễn tập, fine-tune. Lập PR tiếp theo theo ưu tiên người dùng, không báo hoàn tất kiến trúc toàn bộ.

## 7. Prompt ngắn cho Claude Opus

> Hãy tiếp quản repo riêng tư `hongkhang21998-creator/tro-ly-van-ban`, nhánh `codex/local-mvp`. Đọc `docs/handoffs/CLAUDE_OPUS.md`, `WORKLOG.md`, README và draft PR trước khi sửa. Codex đã dừng theo yêu cầu của tôi. Laptop là máy chủ. Hãy thuyết minh việc sẽ làm, kiểm tra các sửa cuối chưa được test và trạng thái Ollama tải xong nhưng chưa giải nén đủ. Không tải lại model, không chạy trùng dịch vụ, không gửi văn bản thật lên cloud. Bạn code và tạo/cập nhật PR; tôi merge. Ghi lại mọi thay đổi để tránh giẫm chân tác vụ khác.
