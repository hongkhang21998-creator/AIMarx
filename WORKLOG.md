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
