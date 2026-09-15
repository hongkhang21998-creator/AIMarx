# AIMarx

## Triển khai local 15/09/2026 — Qwen Q3, context tối đa 2048

Bản ASUS dùng **Qwen2.5 3B Instruct Q3_K_M**, một agent local có công cụ đọc, UI/API/MCP chung backend. `num_ctx` bị khóa tối đa **2048** trong cả chat và trích xuất; cấu hình triển khai khóa cloud. Đây là model gốc, chưa nạp adapter step40.

- Mở **AIMarx Local** trong menu ứng dụng, hoặc chạy `bash scripts/asus-local-agent.sh start` trên ASUS; giao diện tại <http://127.0.0.1:8765/agent>.
- Hướng dẫn vận hành, phạm vi công cụ và bằng chứng: [bàn giao Qwen local](docs/handoffs/QWEN-LOCAL-2026-09-15.md).
- Cấu hình Q3 và context 2048 ở mục này thay ưu tiên 4-bit trong quyết định ngày 14/09 bên dưới.

## Quyết định mới nhất 14/09/2026 — một agent, SLM khoảng 3B + API

Theo quyết định của anh Khang: **AIMarx có đúng một agent điều phối, dùng một SLM local khoảng 3 tỷ tham số; chức năng chính là phân loại và chọn luồng cố định. LLM lớn xử lý văn bản qua API; chương trình kiểm tra và đóng gói để anh duyệt.** Số tham số thuộc model, không phải toàn bộ agent.

Luồng đích: nhập/đọc nguồn → SLM phân loại → backend kiểm quyền và chọn API đã cấu hình → LLM xử lý văn bản → kiểm kết quả → đóng gói DOCX/phiếu và trình duyệt.

- Một worker xử lý tuần tự; API là dịch vụ được gọi, không phải agent tự trị. Không xây swarm, Big Mark cùng các agent Văn/Kiểm/Gói/Tìm/Tri/Huấn, mailbox liên-agent hoặc hội đồng bỏ phiếu.
- Kiểm tra và đóng gói là các bước phần mềm trong cùng workflow. Quy tắc kiểm schema, nguồn, trường bắt buộc, phiên bản và hash là hàng rào chính; SLM chỉ bổ sung nhận xét. Kiểm nguồn chữ không chứng minh đúng ngữ nghĩa; ca khó cần người duyệt hoặc lời gọi API kiểm tra có giới hạn.
- Backend giữ trạng thái SQLite, checkpoint nghiệp vụ, quyền dữ liệu, ngân sách, timeout và retry có giới hạn. SLM không tự cấp quyền hoặc mở agent mới. Lỗi API phải giữ tác vụ để tiếp tục, không báo hoàn thành giả.
- Quyết định kiến trúc cho phép thiết kế đường API, không tự gửi hồ sơ thật hoặc phát sinh chi phí. Tái sử dụng hợp đồng PSC-01 và quyền đã cấp đúng phạm vi; duyệt sản phẩm cuối vẫn tách khỏi quyền gửi dữ liệu.
- Mục tiêu local khoảng 3B, ưu tiên lượng tử hóa 4-bit và context ngắn đủ phân loại; chưa cam kết hiệu năng ASUS trước benchmark RAM đỉnh, p50/p95 và chất lượng. Máy local chạy suy luận; không đặt yêu cầu train 3B trên máy yếu.

Mục này thay các chỉ đạo kiến trúc swarm/biểu quyết và giới hạn chỉ 0.6B trong ghi chép cũ bên dưới. Các mục có ngày trước quyết định này được giữ để truy vết, không phải backlog bắt buộc. Đây là quyết định thiết kế; chưa tuyên bố runtime API/3B đã triển khai.

## Trạng thái đối chiếu ngày 14/09/2026

Mốc nhận việc: main `85d7e97`. **Đã có MVP xử lý văn bản, bộ 120 mẫu được anh Khang duyệt và pilot LoRA Qwen3-0.6B trên Colab T4 tới step 20. Validation loss giảm từ 0,6563 (base) xuống 0,4265 (adapter), nhưng chưa có nghiệm thu nghiệp vụ hoặc hệ thống multi-agent Đồng chí Mark hoàn chỉnh.**

- PR #50/#52: công cụ duyệt/export và snapshot 120 approved, chia 80 train / 20 validation / 20 smoke-test. Quyền train/export được cấp riêng; 20 smoke đã biết không phải test mù.
- PR #55–#58 và #64 đã merge tooling, lượt smoke, cổng reload/evaluation và pilot. Pilot một effective epoch (80 train, 20 optimizer step) đã chạy miễn phí trên T4; artifact và số đo được ghi trong handoff.
- TRAIN-04 / issue #65 chuẩn bị so sánh đầu ra base–adapter theo A/B ẩn danh. 20 smoke công khai chỉ làm hồi quy cố định; nghiệm thu chuyên ngành cần bộ kín độc lập N≥120.
- Tài liệu Word mới định nghĩa Big Mark, 5 vai trò bỏ phiếu và Mark Huấn. Hiện chưa có mailbox, hàng đợi bền vững, biểu quyết tuần tự hoặc phục hồi workflow này.

Xem [đối soát Word và bằng chứng](docs/DOI_SOAT_DONG_CHI_MARK_2026-09-14.md), [tiến độ](TIEN_DO.md) và [kế hoạch tiếp theo](KE_HOACH_AI_AGENT.md). Thông tin “chưa train/0 approved” trong ghi chép cũ là trạng thái lịch sử.

Hợp đồng dự kiến cho tám agent dùng chung adapter, ranh giới localhost–GPU và
điều kiện một kết quả được đưa vào dữ liệu học nằm tại
[`docs/AGENT_TRAINING_WORKFLOW.md`](docs/AGENT_TRAINING_WORKFLOW.md). Đây là
nguyên tắc có pytest khóa lại, chưa phải endpoint Colab đang hoạt động.

**AIMarx** là tên chính thức của trợ lý văn bản local này, đặt theo Karl Marx; định hướng lấy cảm hứng từ Marx và Rosa Luxemburg — xem [định hướng AIMarx](docs/AIMARX_DINH_HUONG.md). Repo GitHub đã đổi tên thành [`hongkhang21998-creator/AIMarx`](https://github.com/hongkhang21998-creator/AIMarx); tên cũ `tro-ly-van-ban` được GitHub tự chuyển hướng. Tên gói Python (`tro_ly_van_ban`) và lệnh CLI giữ nguyên để không làm hỏng cài đặt đang có.


Bản thử nghiệm một người dùng: nhập PDF có chữ, DOCX hoặc TXT → đọc nguồn qua FastMCP → LangGraph trích xuất và kiểm tra → phiếu xử lý, việc đề xuất và dự thảo DOCX → người dùng sửa và duyệt đúng phiên bản. Dữ liệu ở máy local, model dùng Ollama tại `127.0.0.1:11434`; không có fallback cloud.

## Máy chủ hiện tại

AIMarx hiện chạy local trên **laptop ASUS của anh Nguyen Hong Khang**, chỉ bind `127.0.0.1`; chưa mở truy cập LAN/Internet. Bản làm việc gốc vẫn ở máy ASUS. Từ ngày 11/09/2026, bản sao đã kiểm tra và khu vực tập kết dữ liệu SLM được đặt trên ổ **Data1000** tại `/run/media/asus/Data1000/AIMarx/`. Thư mục `data-lake/approved/` chỉ nhận mẫu đã được người dùng duyệt riêng cho mục đích học; việc nằm trên ổ Data1000 không tự biến một tài liệu thành dữ liệu huấn luyện.

## Chạy

Python 3.12. Cài dependency từ bản khóa đã kiểm thử:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/pip install --no-deps --no-build-isolation -e .
TLVB_MODE=demo scripts/run-local.sh
```

Mở http://127.0.0.1:8765. Demo được gắn nhãn rõ, chỉ tạo phiếu rỗng có chỗ cần bổ sung; **không giả kết quả trích xuất AI**. Nhập một TXT UTF-8, bấm trích xuất rồi điền trường và chọn đoạn nguồn. Dữ kiện phải được chép nguyên văn từ đoạn đã chọn. Lưu tạo phiên bản mới; xác nhận/từ chối áp dụng cho phiên bản và hash hiện tại. Tải DOCX để kiểm tra bố cục.

Các bề mặt local dùng chung một façade:

- `/chat`: hỏi SLM Ollama trên máy; không tự chuyển sang cloud.
- `/providers`: thêm, thay, kiểm tra, bật/tắt và thu hồi key. Key nằm trong Windows Credential Manager hoặc Linux Secret Service; SQLite chỉ giữ fingerprint.
- `/v1/chat`, `/v1/providers`, `/v1/usage`: API loopback. API và MCP không nhận API key.
- MCP chỉ có `ask_aimarx`, `list_models`, `get_usage`, `read_document`, `get_evidence`.

Cloud chỉ xuất hiện trên `/chat` sau khi key đã được thêm và provider được bật. Mỗi yêu cầu phải qua màn hình xem trước rồi bấm xác nhận; backend mới tiêu thụ grant, giữ ngân sách và gọi adapter. Thiếu rate card/hạn mức riêng máy thì chặn trước network. Không ghi rate card thật hoặc key vào Git.

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
| `TLVB_REQUIRED_MOUNT` | không đặt (không kiểm ổ) |
| `TLVB_PROVIDER_CONFIG` | `provider-config.json` trong `TLVB_DATA` |

**Kho bắt buộc trên ổ ngoài.** Đặt `TLVB_REQUIRED_MOUNT` là điểm gắn ổ thì UI và MCP chỉ khởi động khi `TLVB_DATA` là đường dẫn tuyệt đối nằm trên đúng ổ đó và ổ đang gắn; sai thì dừng với thông báo tiếng Việt và **không tạo kho mới**. Lý do: điểm gắn nằm dưới `/run` (tmpfs), rút ổ rồi khởi động lại có thể dựng một DB rỗng trong RAM. Máy ASUS dùng `TLVB_REQUIRED_MOUNT=/run/media/asus/Data1000` và `TLVB_DATA=/run/media/asus/Data1000/AIMarx/workspace/data`.

`scripts/run-local.sh` và `run-local.ps1` đọc các dòng `TLVB_*=giá_trị` trong `.env` ở gốc repo (file riêng từng máy, không commit; mẫu ở `.env.example`). File chỉ được đọc như dữ liệu, không chạy như mã; biến đã đặt ở dòng lệnh thắng giá trị trong `.env`. MCP chạy qua client riêng nên phải đặt hai biến này trong cấu hình client.

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

Ollama cho Windows phải cài riêng: gói `.tar.zst` trong `.runtime/downloads` là **bản Linux**. Model GGUF dùng chung được giữa hai hệ, nhưng Ollama native trên Windows mặc định lưu model ở `%USERPROFILE%\.ollama\models`. Launcher `scripts/run-ollama.ps1` giữ nguyên biến `OLLAMA_MODELS` nếu anh đã đặt; nếu chưa đặt thì dùng đúng thư mục mặc định này. Chỉ khi muốn lưu model trong thư mục repository mới cần đặt `OLLAMA_MODELS` rõ ràng.

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
1 Kết luận điều hành
Hai thay đổi hợp nhất gần nhất đã chốt kiến trúc một agent dùng SLM local khoảng 3B và lập kế hoạch A0–A7, nhưng chỉ sửa tài liệu. Runtime mới chưa được triển khai. Bước lập trình đầu tiên còn thiếu là A1a: tạo hợp đồng phân loại và bộ định tuyến quy tắc chạy offline.
Giao diện thống kê token lấy cảm hứng từ WhereMyTokens đã có trong repository, có route /usage, lưu số liệu Ollama vào SQLite và có test giao diện. Ảnh QA desktop/mobile đã có, nhưng dùng dữ liệu giả lập. Cần cập nhật bản cài trên ASUS và chạy smoke test với Ollama thật trước khi kết luận giao diện đang hoạt động trong môi trường production.
2 Bảng tiến độ A0 đến A7
Mã	Nội dung	Việc cần làm	Trạng thái	Điều kiện gần nhất
A0	Kiểm kê	Đối chiếu service, MCP, policy, snapshot, grant, ledger và artifact TRAIN-05.	Gần hoàn thành	Xác minh backup/hash TRAIN-05 và ghi bảng bằng chứng.
A1	Phân loại	Schema strict, ba workflow, baseline quy tắc và dữ liệu có nhãn.	Làm ngay	Tạo routing.py và test_routing.py; test offline xanh.
A2	Benchmark 3B	Chạy model 4-bit trên ASUS; đo chất lượng, RAM, p50/p95.	Chưa làm	Macro-F1 ≥ 0,90; workflow ≥ 90%; JSON ≥ 99%; không OOM.
A3	Gateway API	Nối một provider với policy, snapshot, grant, ledger và giới hạn token/chi phí.	Một phần	Adapter mock đầu-cuối; timeout, usage và quyết toán được test.
A4	Vòng soạn	Nối MCP đến gateway và ba workflow cố định; sau A2 mới tự định tuyến bằng SLM.	Chưa làm	Nguồn + mẫu + yêu cầu tạo được dự thảo có source_refs và missing_fields.
A5	Kiểm và Word	Kiểm schema, số liệu, ngày, tên, nguồn, phiên bản; đóng gói DOCX và duyệt.	Đã có nền	Tái sử dụng kiểm nguồn/DOCX/hash và nối vào kết quả API.
A6	Phục hồi	Hàng đợi SQLite, checkpoint, retry an toàn và chống tạo trùng.	Chưa làm	Restart tiếp tục đúng bước; kết quả API không bị gọi lại ngoài ý muốn.
A7	Nghiệm thu ASUS	Ba ca nghiệp vụ và các lỗi mất mạng, thiếu key, hết ngân sách, nguồn đổi.	Chưa làm	Báo cáo chất lượng, RAM, độ trễ, chi phí và backup/restore đạt.

3 Phân biệt tài liệu và chức năng đã kiểm chứng
Hạng mục	Tài liệu	Runtime	Bằng chứng và giới hạn
Kiến trúc một agent khoảng 3B	Có	Chưa	PR #73 chỉ sửa Markdown.
Kế hoạch A0–A7	Có	Chưa	PR #74 chỉ sửa Markdown.
Nhập PDF chữ DOCX TXT	Có	Đã có	Runtime Service và parser hiện hữu.
MCP đọc tài liệu	Có	Đã có	Ba công cụ read-only; chưa có yêu cầu soạn.
Policy snapshot grant ledger	Có	Đã có	Module và test riêng; chưa nối adapter cloud.
Gateway gọi LLM cloud	Có thiết kế	Chưa	Không tìm thấy adapter gửi request provider trong runtime.
Phân loại theo schema A1	Có đặc tả	Chưa	Runtime chưa có document_type, workflow_id, missing_fields.
Kiểm nguồn DOCX duyệt hash	Có	Đã có	Đã nối trong Service hiện tại.

4 Kiểm tra giao diện WhereMyTokens
Nội dung kiểm tra	Kết quả	Nhận định
Mã giao diện	Đã có	src/tro_ly_van_ban/token_dashboard.py
Đường dẫn sử dụng	Đã có	GET /usage trong web.py và liên kết Thống kê token.
Nguồn dữ liệu	Đã có	Bảng ollama_usage trong state.sqlite3; không lưu prompt hoặc nội dung tài liệu.
Số liệu	Đã có	Token vào/ra, số lượt, tốc độ sinh, hoạt động theo ngày và theo model.
Bộ lọc	Đã có	Hôm nay, 7 ngày, 30 ngày và toàn bộ lịch sử.
Giao diện	Đã có	Sáng/tối, desktop/mobile, heatmap 84 ngày và 50 lượt gần nhất.
Nguồn thiết kế	Đã có	Chuyển thể từ WhereMyTokens v1.24.6 theo giấy phép MIT; license đã lưu trong repo.
Test trong repo	Đã có	tests/test_token_usage.py kiểm lưu, restart, thiếu usage, route, theme và bộ lọc.
Ảnh QA	Đã có	Bốn ảnh trong docs/qa/token-dashboard; dữ liệu trong ảnh là giả lập.
Chạy production ASUS	Chưa xác minh production	Cần cập nhật checkout, khởi động lại và chạy một lượt Ollama thật.

5 Nhiệm vụ thực hiện ngay trên ASUS
Nhiệm vụ A1a Runtime routing contract
Mục	Yêu cầu
Phạm vi	Chỉ tạo src/tro_ly_van_ban/routing.py và tests/test_routing.py.
Đầu ra	JSON strict gồm document_type, operation, workflow_id, source_refs, missing_fields, needs_review.
Bảo vệ	Khóa enum, cấm trường thừa, chặn workflow ngoài allowlist và xử lý prompt injection như dữ liệu.
Baseline	Quy tắc offline nhận diện ba workflow chính; ca mơ hồ trả needs_user_choice.
Không làm	Không tải model 3B, không gọi API, không sửa SQLite, UI hoặc MCP.
Nghiệm thu	python -m pytest -q tests/test_routing.py; sau đó python -m pytest -q.

6 Việc kiểm tra giao diện token trên ASUS
1.	Cập nhật checkout AIMarx tới main SHA 9f12633 hoặc phiên bản mới hơn đã được duyệt.
2.	Sao lưu state.sqlite3 và xác nhận TLVB_DATA trỏ đúng kho vận hành.
3.	Khởi động AIMarx và Ollama theo script hiện hành; không mở dịch vụ ra mạng LAN.
4.	Mở http://127.0.0.1:8765/usage và kiểm tra trạng thái rỗng hoặc dữ liệu hiện có.
5.	Chạy một tài liệu thử bằng Ollama; xác nhận lượt gọi, token vào/ra và model xuất hiện sau khi làm mới.
6.	Khởi động lại AIMarx; xác nhận số liệu vẫn còn và thao tác demo/chỉnh sửa thủ công không làm tăng token.
7 Tài liệu đối chiếu trong repository
•	Commit main: https://github.com/hongkhang21998-creator/AIMarx/commit/9f126337db014d2ed5de396dbfd8b14d742b6e4a
•	Kế hoạch: KE_HOACH_AI_AGENT.md; tiến độ: TIEN_DO.md; nhật ký: WORKLOG.md.
•	Token dashboard: src/tro_ly_van_ban/token_dashboard.py; src/tro_ly_van_ban/token_usage.py; src/tro_ly_van_ban/web.py.
•	Kiểm thử: tests/test_token_usage.py; tài liệu bàn giao: docs/handoffs/OLLAMA-TOKEN-DASHBOARD-2026-09-14.md.
•	Ảnh QA: docs/qa/token-dashboard; giấy phép: docs/third-party/WhereMyTokens-LIC
