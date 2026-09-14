# Ollama token dashboard — phạm vi và bàn giao

- Chủ trì: Codex, theo yêu cầu anh Nguyen Hong Khang ngày 14/09/2026.
- Base: `f140d21e1c68e52049d0d86bf324f06a930131e1` (`main`). Nhánh độc lập `codex/ollama-token-dashboard`.
- Checkout riêng: `D:/Claude-cowork/aimarx-token-stats`. Không chỉnh checkout `tro-ly-van-ban` đang có mã CPU training chưa commit.
- Yêu cầu đã chốt: thống kê token của chính AIMarx/Ollama trong UI; lấy UX/UI WhereMyTokens.
- Sở hữu: `src/tro_ly_van_ban/token_usage.py`, `token_dashboard.py`, điểm nối trong `model.py`, `service.py`, `web.py`; `tests/test_token_usage.py`; tài liệu này và `docs/third-party/WhereMyTokens-LICENSE.txt`.
- Không sửa WORKLOG/TIEN_DO đang thuộc các PR khác. Tài liệu riêng này là nhật ký đầy đủ của gói để tránh giẫm chân.
- PR đang mở đã kiểm: #58, #47, #11, #8. #58 head `0122076b2f822742a31316354ee56e1d96b367c4`; không cập nhật hoặc xếp chồng lên các nhánh đó.
- Upstream: https://github.com/jeongwookie/WhereMyTokens tại `40b53ff2d1aadddfeb63f4b9773050df4279d9aa`, v1.24.6, MIT. Chuyển thể màu theme, bố cục thẻ, bộ lọc thời gian, hoạt động và model breakdown sang HTML/CSS local. Không nhúng Electron hoặc bộ đọc tài khoản Claude/Codex.
- Nguồn contract: https://docs.ollama.com/api/chat — prompt_eval_count, eval_count và duration nanosecond.
- Nghiệm thu: số token thực từ response; lỗi/thiếu số liệu không giả 0; lưu qua restart; demo/manual không tính; bảo toàn validation/approval; UI sáng/tối và mobile; regression; PR riêng do anh Khang merge.

## Trạng thái

Đã triển khai qua PR #60, merge vào `main` ngày 14/09/2026 tại commit `158f1c8f6e15cf7fe3163da7f19c4a3b23b45976`. Bản ghi dưới đây được cập nhật sau merge để phản ánh kiểm tra hậu merge.

## Kiểm tra hậu merge — 14/09/2026

- Checkout sạch `D:/Claude-cowork/aimarx-token-stats` đã đưa về đúng `origin/main` tại merge commit `158f1c8f6e15cf7fe3163da7f19c4a3b23b45976`; không chứa thay đổi cục bộ. `git diff --check` đạt.
- Chạy lại toàn bộ bộ test trên Windows từ merge commit: **832 passed, 5 skipped**, 66,87 giây; một cảnh báo deprecation AnyIO/Starlette đã có trong dependency. Đây là lượt kiểm tra độc lập sau merge, khác với số CI trong PR.
- Khởi động tạm UI bằng `TLVB_MODE=demo`, `TLVB_DATA=D:/Claude-cowork/tmp/aimarx-postmerge-verify`, `TLVB_PORT=8877`, `PYTHONPATH=src`; mở `http://127.0.0.1:8877/usage` trả trang `Thống kê token · AIMarx`, hiển thị trạng thái rỗng đúng và giữ CSP. Tiến trình tạm đã dừng, thư mục dữ liệu kiểm tra không phải kho production.
- Kiểm tra thực tế ngày 14/09/2026 từ máy Windows: `127.0.0.1:11434`, `192.168.130.10:11434` và `192.168.1.2:11434` đều không có dịch vụ lắng nghe. Không inference thật, không tạo số liệu thật, không cài Ollama, không khởi động dịch vụ nền và không chạm máy Linux.
- Checkout gốc `D:/Claude-cowork/tro-ly-van-ban` vẫn giữ nguyên nhánh `codex/train03-cpu-backend`, đang có 3 file training sửa và 4 file chưa track như trước; không pull, reset, stash hoặc checkout trên đó.
- Trạng thái hiện tại: code đã merge và verified post-merge; **chưa** xác nhận Ollama runtime trên máy của anh. Bước triển khai còn lại cần chạy trên máy có Ollama thật, bằng `TLVB_DATA` đúng kho dữ liệu, sau khi người dùng chủ động cung cấp/khởi động runtime.

## Kết quả triển khai

- Thêm `/usage` và liên kết “Thống kê token” trong điều hướng hiện có. Trang riêng chuyển thể từ WhereMyTokens: màu theme sáng/tối, thẻ số liệu, bộ lọc hôm nay/7 ngày/30 ngày/tất cả, biểu đồ cột, heatmap 84 ngày, model breakdown, 50 lượt gần nhất. Bảng dữ liệu từng ngày cho bàn phím/trình đọc màn hình.
- HTML/CSS phía server, không thêm dependency, JavaScript, CDN, Electron, auto-refresh hay request bên ngoài. Làm mới bằng nút; giao diện sáng/tối và khoảng ngày được giữ trong URL.
- Ngày tính theo UTC+7 trên cả Windows/Linux. “7 ngày” và “30 ngày” là các ngày lịch gồm hôm nay. Tất cả cộng toàn lịch sử; heatmap chỉ 84 ngày gần nhất.
- `Service.run` mở context thống kê quanh LangGraph. `model.chat` tạo bản ghi pending ngay trước HTTP, hoàn tất một lần sau nhận response. Các lệnh eval gọi model bên ngoài Service không bị nhập nhầm vào thống kê ứng dụng.
- Bảng `ollama_usage` trong `state.sqlite3`, migration chỉ thêm bảng/index. Lưu request ID, timestamp UTC, model yêu cầu, trạng thái, token vào/ra, thời gian sinh/tổng nanosecond. Không có prompt, nội dung trả lời, tên/ID tài liệu, credentials.
- Missing/invalid metric (âm, bool, float, chuỗi, quá giới hạn) là NULL. Đếm từng phản hồi, không cộng lại khi refresh/restart. Finish lặp cùng request ID không thay kết quả đã chốt. Aggregate có read transaction để thẻ/tổng/model/lịch sử cùng snapshot.
- Lỗi kết nối hoặc envelope JSON sai: failed, số token chưa biết. Envelope nhận được nhưng content không đạt JSON/schema/evidence: vẫn tính token đã nhận, nhãn “Đã nhận phản hồi” không đồng nghĩa nghiệp vụ thành công/được duyệt.
- Dừng đột ngột có thể để pending, hiện “Chưa kết thúc”; không tự retry hoặc đoán đã dùng bao nhiêu token. Ghi DB lỗi sẽ báo lỗi thay vì bỏ qua âm thầm; nếu chưa ghi được pending thì không gọi model. Không có lịch sử trước khi cài và không suy ra từ độ dài văn bản.
- Demo/manual/stale request/nguồn quá giới hạn không gọi model nên không tính lượt. Không thay prompt V5, schema, generation options hoặc hàng rào duyệt.
- Tốc độ chỉ từ các cặp output token/eval duration hợp lệ; không đại diện tốc độ xử lý tài liệu đầu-cuối. Không giả định tiền API, quota tài khoản, chi phí điện hoặc cache.

## Bằng chứng kiểm thử

- Windows, Python trong `.venv` sẵn có của checkout gốc, test chạy với `pythonpath=src` của checkout riêng. Không cài/sửa môi trường gốc.
- Tập trung token/model/workflow: **81 passed, 1 skipped**, 16,88 giây.
- Full suite: **832 passed, 5 skipped**, 68,01 giây. Có cảnh báo deprecation AnyIO/Starlette từ dependency đang có.
- Sau bổ sung read transaction cho summary: toàn bộ **16 ca token passed**, 3,87 giây. Không có thay đổi prompt hoặc mã inference khác sau full suite.
- Bao phủ: LangGraph thực với HTTP giả lập, persistence/restart, retry riêng, lỗi HTTP, thiếu/sai/zero counts, kết quả bị từ chối, demo/manual/stale/oversize, pending/idempotency, UTC+7/filter/future exclusion/limit 50, hai context chạy song song không lẫn kho, XSS, điều hướng và CSP.
- UI mở thực bằng trình duyệt local: dark/light desktop 1265 × 712 và mobile viewport 390 × 844 (vùng nội dung 375 px do scrollbar). Không tràn ngang trang. Đã bấm sáng/tối, Tất cả, mở bảng ngày; đã xem heatmap/model/history ở mobile. Bảng lịch sử cuộn ngang trong khung khi màn hình hẹp.
- Ảnh trong `docs/qa/token-dashboard/` **dùng dữ liệu giả lập**, không phải benchmark/token thật: 28 response + 1 lỗi, hai tên model; dữ liệu nằm ngoài repo tại `D:/Claude-cowork/tmp/aimarx-token-dashboard-qa`.
- `git diff --check` đạt. Remote main và head của #58/#47/#11/#8 đối chiếu vẫn như trước; checkout gốc vẫn ở `codex/train03-cpu-backend` với đúng danh sách 3 file sửa + 4 file chưa track. Không stash/reset/checkout/push trên repo gốc.

## Giới hạn, triển khai, rollback

- Chưa chạy inference Ollama thật trong gói này; contract đã đối chiếu tài liệu chính thức, kiểm bằng response giả lập. Chưa triển khai lên Linux hoặc đổi dịch vụ/DB production. Không có số đo hiệu năng mới.
- Sau khi anh Khang merge: cập nhật bản cài AIMarx và khởi động lại như quy trình hiện tại, vào “Thống kê token”, trích xuất bằng Ollama. Bảng tự tạo trong đúng TLVB_DATA; không cần nhập tài khoản/API key. Endpoint không trả trường count thì UI hiển thị thiếu số liệu.
- Rollback mã bằng revert PR và restart; bảng thống kê có thể giữ lại an toàn trong DB. Không cần xóa hoặc đổi bảng nghiệp vụ. Không tự xoá lịch sử.
- Dữ liệu thống kê được giữ lâu dài, chưa có retention/compaction. Totals/model là aggregate SQL; danh sách request giới hạn 50, activity 84 ngày. Chưa benchmark trên hàng triệu request.
- Nhánh không sửa file thuộc #58/#47/#11/#8; nhật ký và ảnh QA riêng để các task khác có thể đọc trước khi tích hợp. Anh Khang là người merge, không bật auto-merge.
