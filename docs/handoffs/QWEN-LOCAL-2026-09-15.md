# Qwen local — bàn giao 15/09/2026

## Checkout và trách nhiệm

- Một agent, nhánh `codex/qwen-local-agent`, base `30da026` (main sau khi anh Khang merge #81).
- Checkout chạy trên ASUS: `/home/asus/Documents/ChatGPT/AI-agent for me/.worktrees/qwen-local-agent`.
- Phạm vi: local agent, cấu hình Q3/2048, UI/API/MCP, khóa cloud khi triển khai, script mở ứng dụng và test. Giữ nguyên checkout gốc `dc36b5d`, worktree Claude và dữ liệu nghiệp vụ.
- Anh Khang đã cấp quyền **tự merge và deploy** trong phiên này. Merge sau CI; receipt triển khai ghi commit merge thực tế. Không dùng các số đo dưới đây để tuyên bố cloud/provider production đã được nghiệm thu.

## Runtime đã cài

- Ollama **0.33.3** có sẵn tại `.runtime/ollama/bin/ollama` của checkout gốc; trước đó không nằm trong PATH.
- Model: `qwen2.5:3b-instruct-q3_K_M`, GGUF **Q3_K_M**, khoảng 1,6 GB. Nguồn: [tag chính thức Ollama](https://ollama.com/library/qwen2.5:3b-instruct-q3_K_M). Đã pull và Ollama xác minh SHA-256.
- Kho model: `/run/media/asus/Data1000/AIMarx/models`.
- **Không phải checkpoint QLoRA step40**. Adapter trong Downloads vẫn giữ nguyên; chưa có phép đo phân loại step40 trong đợt này.
- `MAX_LOCAL_CONTEXT=2048`. Chat/agent luôn gửi 2048; trích xuất mặc định 2048 và từ chối tham số lớn hơn trước khi gọi mạng. Không có tham số HTTP/MCP cho phép tăng context.
- `OLLAMA_CONTEXT_LENGTH=2048`, `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NO_CLOUD=1`. API `/api/ps` đã xác nhận context đang nạp **2048**, CPU, `size_vram=0`.
- Hai dịch vụ user: `aimarx-ollama` nghe `127.0.0.1:11434`, `aimarx-local` nghe `127.0.0.1:8765`. `TLVB_LOCAL_ONLY=1` chặn cả gọi cloud lẫn kiểm tra credential trước khi lấy key/gọi mạng.

## Dùng trên ASUS

Mở **AIMarx Local** trong menu ứng dụng. Shortcut khởi động dịch vụ và mở `/agent` trong trình duyệt. Đây là lối mở thủ công sau đăng nhập, không phải dịch vụ tự chạy lúc boot.

Trong checkout đang triển khai:

```bash
bash scripts/asus-local-agent.sh start
bash scripts/asus-local-agent.sh status
bash scripts/asus-local-agent.sh stop
```

Script gắn lại volume nhãn Data1000 khi cần; kiểm mount trước khi dùng dữ liệu; kiểm đúng quantization Q3_K_M trước khi mở app. Nếu máy vừa reboot, chạy script/shortcut để khởi động lại. Dịch vụ user độc lập với terminal và tồn tại đến khi dừng, đăng xuất hoặc reboot. Không tải model tự động trong script khởi chạy.

Dữ liệu: `/run/media/asus/Data1000/AIMarx/workspace/data`. Đã backup SQLite bằng SQLite backup API trước khởi động:

`/run/media/asus/Data1000/AIMarx/backups/state-before-qwen-q3-20260915-194316.sqlite3`

Backup `quick_check=ok`, giữ 2 tài liệu hiện có. Không đưa hồ sơ thật vào smoke/huấn luyện, không đưa nội dung hồ sơ hoặc key vào báo cáo này.

## Agent làm được gì

1. Qwen chọn một action theo schema kín. Bước này chỉ phân loại, tối đa 48 token đầu ra.
2. Backend thực hiện tối đa **một công cụ đọc**: liệt kê tài liệu, đọc tài liệu người dùng chọn, xem usage hoặc liệt kê model.
3. Kết quả liệt kê/thống kê lấy trực tiếp từ backend. Đọc tài liệu có thêm một lượt Qwen trả lời từ nguồn; giao diện cho xem các đoạn nguồn để đối chiếu. Trò chuyện dùng một lượt trả lời riêng sau phân loại.

Tối đa 2 lượt suy luận, không retry tự động, không lặp vô hạn. Trong một instance, yêu cầu chồng nhau nhận `LOCAL_BUSY`; Ollama chỉ nạp một model và xử lý tuần tự giữa các instance. Model không có shell, đường dẫn tệp tùy ý, công cụ sửa/xóa hay quyền duyệt nghiệp vụ. ID tài liệu do caller chọn, không lấy từ output model.

Đọc tài liệu giới hạn phần đầu: tối đa 20 đoạn/3500 ký tự nguồn. API trả `truncated`, UI báo khi chỉ đọc một phần. Giới hạn ký tự là giới hạn dữ liệu gửi, không phải phép đếm token. `num_ctx=2048` vẫn là giới hạn context của model; tóm tắt dài không được xem như đã đọc toàn bộ hồ sơ. Câu trả lời và diễn giải nguồn vẫn cần người dùng kiểm tra.

Lập phiếu, tải DOCX và duyệt phiên bản dùng luồng Kho tài liệu đã có. Agent không tự duyệt phiếu.

## API và MCP

```http
POST /v1/agent
Content-Type: application/json

{"message":"Liệt kê các tài liệu hiện có trong kho."}
```

Để đọc: gửi thêm `document_id` đã đăng ký. Không nhận tham số key, provider, đường dẫn, context hoặc tên công cụ. Plain chat vẫn ở `POST /v1/chat`. UI `/agent` dùng form có CSRF; JSON API từ chối content type đơn giản và Origin khác. Ứng dụng chỉ phục vụ máy local; không thiết kế như máy chủ công khai.

MCP vẫn đúng 5 tool: `ask_aimarx`, `list_models`, `get_usage`, `read_document`, `get_evidence`. `ask_aimarx` mặc định chạy agent; dùng `agentic=false` khi muốn chat thuần. MCP không có thao tác credential/consent.

Chạy MCP stdio trên ASUS:

```bash
bash scripts/asus-mcp.sh
```

Cấu hình client dùng command `bash`, arguments chứa đường dẫn tuyệt đối tới script trên. Script chọn đúng model Q3, Data1000 và chế độ local-only như HTTP. Đã kiểm handshake, tools/list và list_models bằng tiến trình MCP thật. Chưa tự thay cấu hình MCP toàn cục của Codex.

## Kiểm chứng và giới hạn số đo

- Regression cuối: **900 passed, 2 skipped**, 78,65 giây; warning deprecation Starlette/AnyIO có sẵn.
- [Kết quả Qwen thật](../../evals/local_agent/results/asus-q3-2026-09-15.json): 6/6 smoke giả lập. Planner chỉ chọn tool cho lượt đơn giản mất khoảng 3–5 giây; đọc và trả lời nguồn 29,04 giây; trò chuyện 38,51 giây trong lượt cuối.
- Trước khi sửa prompt, lượt đầu đạt 4/6, lượt kế tiếp 5/6; đã dùng các ca này để sửa. **6/6 không phải accuracy trên bộ test mù**, không đại diện toàn bộ hồ sơ hành chính hay chất lượng step40.
- ASUS i3-8130U, 2 core/4 thread, RAM hệ điều hành báo 7,1 GiB. Một lần đo runner RSS khoảng **1,65 GiB**, cả máy còn khoảng **1,9 GiB available**. Đây là một quan sát khi chạy, không phải cam kết RAM đỉnh hoặc p95. Ollama báo model loaded size 1.747.147.816 byte gồm bộ nhớ runtime liên quan.
- Test kiểm schema sai, chọn công cụ ngoài allowlist, đọc thiếu scope, nội dung nguồn chứa lệnh, chạy đồng thời, endpoint metadata bị sửa, cloud lock trước khi đọc key, context vượt 2048 và API/MCP không nhận key.

## Tiếp quản / hoàn tác

- Giữ checkout đang chạy cho đến khi chuyển dịch vụ sang main sau merge. Không xóa worktree khi shortcut và service còn trỏ vào đó.
- Dừng bằng script `stop` trước khi đổi checkout/config. Khởi động bằng script `start` ở checkout muốn dùng; kiểm `/agent`, model và cloud lock.
- Không tự phục hồi backup đè lên dữ liệu mới. Chỉ phục hồi khi có lỗi dữ liệu được xác minh và đã bảo toàn dữ liệu phát sinh sau backup.
- Model Q4 tải dở trước chỉ đạo đổi sang Q3 không được nạp. Không sửa hoặc xóa checkpoint step40.
