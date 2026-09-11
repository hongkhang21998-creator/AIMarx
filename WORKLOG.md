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

