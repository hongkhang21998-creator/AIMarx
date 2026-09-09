# Nhật ký phối hợp

## 2026-09-08 — codex/local-mvp — dừng, bàn giao Claude Opus

- Yêu cầu: dùng laptop làm máy chủ, GPT-6 Astra mức suy luận low viết code, tạo và mở repo GitHub.
- Repo riêng tư: https://github.com/hongkhang21998-creator/tro-ly-van-ban
- Nhánh: `codex/local-mvp`; base: `origin/main` (README khởi tạo).
- Phạm vi tác vụ: ứng dụng local nhập văn bản → phiếu có nguồn → dự thảo → người dùng duyệt; kiểm thử, tài liệu vận hành.
- Phụ trách source/tests/README: agent `astra_low_code`, GPT-6 Astra / low, được người dùng chỉ định.
- Phụ trách tích hợp, GitHub, triển khai và bàn giao: tác vụ gốc hiện tại.
- Không nhận việc sửa cùng source/schema trên nhánh khác trước khi đọc PR và bàn giao.
- Người dùng merge PR. Không tự merge hoặc bật auto-merge.
- Dữ liệu thật, model, DB, secrets và cấu hình riêng máy nằm ngoài Git.
- Kế hoạch đầy đủ: `KE_HOACH_AI_AGENT.md`; kết quả thực tế được ghi riêng, không coi kế hoạch là tính năng đã làm.
- Người dùng đã yêu cầu dừng Codex viết code và chuyển cho Claude Opus. Agent viết code đã bị ngắt; không tiếp tục triển khai tính năng.
- Bản bàn giao chính: `docs/handoffs/CLAUDE_OPUS.md`. Đọc trước khi nhận phần việc.
- Kiểm thử gần nhất 10 passed trước các sửa manual/provenance/draft_hash cuối; snapshot bàn giao chưa được chạy lại toàn bộ test.
- UI/Ollama API local đang chạy; runtime Ollama đầy đủ đã tải và xác minh nhưng chưa giải nén, chưa xác nhận inference.

## 2026-09-08 — claude/cross-platform — Claude Opus tiếp quản, làm đa nền tảng

- Nhận bàn giao từ `docs/handoffs/CLAUDE_OPUS.md`. Người dùng yêu cầu hệ thống chạy được **độc lập trên cả Windows và Linux**; Linux vẫn là máy chủ chính.
- Nhánh: `claude/cross-platform`, base `89d05ae` trên `main`.
- Phạm vi nhánh này **chỉ là tương thích hệ điều hành**. Cố ý không đụng thiết kế phê duyệt, không làm mục 2–3 bàn giao (`review()` kiểm bytes `draft_hash`, chính sách backfill hash rỗng) — tách PR sau cho dễ soát khi merge.
- **Chưa chạm vào laptop Linux**: chưa SSH, chưa restart dịch vụ, chưa giải nén gói Ollama, chưa thử inference. Máy Linux giữ nguyên trạng thái như `CLAUDE_OPUS.md` mô tả.
- Bản bàn giao ngược cho GPT Astra: `docs/handoffs/GPT_ASTRA.md`.
- CI matrix xanh cả hai (run `34216101884`): `ubuntu-latest` 13 passed 1 skipped, `windows-latest` 14 passed.
- Đã chạy `pytest` **trên chính laptop Linux** (Python 3.12.14, cây làm việc `1d073cc`): 13 passed, 1 skipped; `pip check` sạch. Đây là điều kiện trước merge mà `GPT_ASTRA.md` mục 6 nêu, nay đã đóng.
- Ba lỗ hổng toàn vẹn phê duyệt (mục 2–4 `CLAUDE_OPUS.md`) đã được **tái hiện bằng thực nghiệm**, không còn là nghi ngờ trên giấy. Xem PR tiếp theo.

## 2026-09-08 — claude/approval-integrity — toàn vẹn phê duyệt

- Nhánh: `claude/approval-integrity`, base `b0ea96c` trên `claude/cross-platform`. **PR xếp chồng** trên PR #3; #3 phải merge trước.
- Đóng mục 2–4 của `docs/handoffs/CLAUDE_OPUS.md`. Cả ba đã được **tái hiện bằng thực nghiệm trước khi sửa**, không sửa theo nghi ngờ trên giấy.
- Phát sinh trong lúc viết test: `/documents/{id}/edit` vỡ thành `TypeError` 500 khi tài liệu chưa có phiên bản nào. Đã sửa cùng nhánh vì thuộc mục 4 (xử lý lỗi HTTP).
- Đã thử **luồng đầy đủ bằng trình duyệt** trên một instance tách riêng (cổng 8799, `TLVB_DATA` riêng, chế độ demo) để không đụng dịch vụ/DB thật: nhập TXT → lập phiếu → sửa có dẫn nguồn → tải DOCX → sửa trộm DOCX → duyệt bị chặn, từ chối vẫn chạy → hash rỗng bị chặn cả tải lẫn duyệt → bản sạch duyệt được. Đây là mục "chưa thử luồng đầy đủ bằng trình duyệt" của bàn giao cũ, nay đã đóng trên Linux.
- Vẫn **chưa chạm** Ollama: chưa giải nén gói đầy đủ, chưa thử suy luận. Không nằm trong phạm vi nhánh này.


## 2026-09-08 — Codex tester — giao việc Claude ngày 09/09

- Người dùng yêu cầu QA và chuẩn bị giao Claude sửa ngày mai. Không sửa mã sản phẩm hoặc merge.
- Baseline HEAD `0981e7d`; tree trùng main merge PR #4 `822ce30` (`b90b589be96fa9fbdcf86edb0cd2d038f4f3af22`). Test trên snapshot /tmp, dữ liệu tổng hợp riêng.
- Bộ cũ: 17 passed, 1 skipped; pip check sạch. Bộ tái hiện bổ sung: 7 failed thuộc 4 nhóm lỗi: trạng thái duyệt sau inference lỗi; blocking event loop khi ghi đồng thời; stale /run; validation HTTP.
- Báo cáo: `docs/handoffs/QA_CLAUDE_2026-09-09.md`; bộ tái hiện và output trong `docs/qa/2026-09-08/`. Các file này đang local, chưa commit; GitHub Issue #5 có đầy đủ báo cáo và code test để tiếp quản từ xa.
- Issue giao việc: https://github.com/hongkhang21998-creator/tro-ly-van-ban/issues/5 . Claude cần nhận phạm vi và ghi nhánh/base trước khi sửa service.py/web.py; người dùng merge. Chưa điều khiển hoặc xác nhận Claude đã nhận việc.
- Không chạm data/, runtime, UI/Ollama thật. Chưa kiểm thử browser/Windows trực tiếp hoặc inference thật trong phiên này.

## 2026-09-08 tối — claude/qa-baseline — nhận việc Issue #5, chưa sửa mã

- Nhánh: `claude/qa-baseline`, base `822ce30` trên `main`. Phạm vi: **chỉ `docs/`**, không đụng `src/` hay `tests/`.
- Đã đối chiếu bằng chứng của Issue #5: PR #4 merge `822ce30`, tree trùng `0981e7d` (`b90b589…`). Chạy lại: bộ cũ 17 passed 1 skipped, bộ QA 7 failed. **Tái hiện đủ cả bảy**, báo cáo trung thực.
- Hai điểm nặng hơn báo cáo, đã ghi vào `docs/handoffs/QA_CLAUDE_2026-09-09.md`: (1) QA-01 làm bản `awaiting_review` **kẹt vĩnh viễn không duyệt lại được**, không chỉ hiển thị sai; (2) QA-02 ảnh hưởng **năm** route async chứ không một, `/upload` parse PDF ngay trên event loop nên treo UI cả khi không có model.
- Bộ QA đưa vào repo nguyên assertion, thêm `xfail(strict=True)`: CI xanh, lỗi vẫn nằm trong repo, và khi sửa xong CI sẽ đỏ vì XPASS để buộc gỡ marker.
- **Nhận phạm vi cho ngày 09/09**: `service.py` và `web.py` cho cả bốn nhóm QA-01…04. Chatbot khác đừng sửa hai file này trước khi đọc PR.
- Kế hoạch đã chốt với anh Khang: hai PR — P1 (QA-01 + QA-02) rồi P2 (QA-03 + QA-04). Tối nay **không sửa lỗi nào**; chưa chạm Ollama, UI, `data/`.

## 2026-09-09 — claude/qa-p1 — QA-01: lần chạy hỏng không còn xoá trạng thái duyệt

- Nhánh: `claude/qa-p1`, base `66edcf3` trên `claude/qa-baseline`. **PR xếp chồng** trên PR #6; #6 phải merge trước.
- Đã **tái hiện trước khi sửa**: `approved` → `model_unavailable` sau khi `graph.invoke` ném `ModelUnavailable`, sổ việc mất công việc đã xác nhận.
- Sửa: tách kết quả lần chạy khỏi trạng thái duyệt. Thêm cột `documents.error_kind` (`''` | `model_unavailable` | `error`) kèm migration `ALTER TABLE` theo đúng khuôn của `draft_hash`. `Service.record_failure()` chỉ ghi `error`/`error_kind`; **chỉ** khi tài liệu chưa có phiên bản nào thì mới ghi vào `state` — ở đó không có trạng thái duyệt nào để giữ. `save()` xoá cả `error` lẫn `error_kind` khi lưu thành công.
- `web.py`: trang tài liệu tách "Trạng thái" và banner lỗi lần chạy; gộp một dòng thì lỗi trích xuất đọc như thể đã thay thế trạng thái duyệt.
- Test: gỡ `xfail` của QA-01 trong `docs/qa/2026-09-08/`. Thêm 5 ca vào `tests/test_workflow.py` phủ `approved`/`awaiting_review`/`rejected`, model vắng, output sai schema, DB cũ chưa có cột, và hiển thị web. Đã xác nhận **cả 5 ca đỏ trên `service.py` cũ** — không phải test dán vào cho xanh.
- Ca `awaiting_review` kiểm tra đúng điểm nặng mà bàn giao nêu: sau lỗi vẫn `review()` duyệt được, không kẹt vĩnh viễn.
- Kết quả Linux/Python 3.12: **23 passed, 1 skipped, 6 xfailed** (QA-02/03/04 chưa đụng), 4.70 giây.
- Chưa chạm: QA-02/03/04, Ollama, `data/`, luồng trình duyệt, Windows trực tiếp (để CI chạy).

## 2026-09-09 — claude/qa-p1 — QA-02: route ghi rời event loop

- Bàn giao nói đúng: **năm** route async gọi thẳng service trên event loop, chỉ `/run` dùng threadpool. `/upload` parse PDF ngay trên loop nên treo UI cả khi không có model nào tham gia.
- Sửa: `run_in_threadpool` cho `/upload`, `/manual`, `/save`, `/edit`, `/review`. Import chuyển lên đầu module — để nó nằm trong thân `/run` chính là lý do bốn route kia không có gì nhắc rằng chúng đang chạy sai chỗ. `/edit` tách thành `apply_edit()` để cả cụm `get` + dựng nội dung + `save` đi trong **một** lần sang threadpool.
- **Không bỏ lock.** `Service.lock` giữ nguyên: nó là thứ đang bảo đảm kiểm soát phiên bản và thứ tự ghi. Việc cần sửa là ai *chờ* nó, không phải có nên có nó không.
- Đo lại đúng kịch bản của Codex (inference giả lập 1,2 giây, heartbeat 50 ms): **1,26 s → 0,051 s**.
- Test: gỡ `xfail` QA-02. Thêm 6 ca vào `tests/test_workflow.py` — bốn route ghi (parametrize), `/upload`, và một ca xác nhận `GET /tasks` vẫn trả lời trong lúc một lệnh ghi đang đợi lock. Barrier là `threading.Event`, mọi lần chờ có timeout, không ca nào dựa vào `sleep` để đồng bộ. Các ca **giữ lock trực tiếp thay vì mock model**, nên phép đo không dính vào tốc độ máy chạy test. Chạy lặp 3 lần: ổn định.
- Đã xác nhận **cả 6 ca đỏ trên `web.py` cũ**.
- Diễn tập tổng hợp nhập → sửa có dẫn nguồn → duyệt → lỗi AI → khôi phục: trạng thái `approved` giữ nguyên qua lỗi, sổ việc không mất việc, banner lỗi hiện đúng, lần chạy thành công sau đó tạo v3 và xoá dấu vết lỗi.

### Giới hạn còn lại, không nằm trong phạm vi PR này

- Lock là **toàn dịch vụ**, không theo từng tài liệu: một lần inference chậm vẫn xếp hàng mọi lệnh ghi của **mọi** tài liệu. Event loop rảnh nên đọc và giao diện còn đáp ứng — đó là điều QA-02 yêu cầu — nhưng ghi thì vẫn chờ. Tách lock theo tài liệu là việc riêng, cần cân nhắc cùng QA-03.
- Threadpool của anyio mặc định 40 luồng. Nhiều lệnh ghi cùng xếp hàng sau một inference dài có thể chạm trần; với một dịch vụ chạy local một người dùng thì chưa phải vấn đề, nhưng đây là trần thật, không phải vô hạn.
- QA-03 và QA-04 chưa đụng, vẫn `xfail(strict=True)` trong `docs/qa/2026-09-08/`.
