# SNAP-01 — kết quả

- **Ngày, người phụ trách:** 11/09/2026 — Claude (Opus), hai buổi trong cùng ngày theo nhịp anh Khang duyệt.
- **Issue:** #30. **Nhánh:** `claude/snapshot-contract`, tạo từ `main` `839afe9` (issue ghi `68765bd`; PR #35, #36 ở giữa chỉ đổi tài liệu và bộ chấm, không đụng mã lõi).
- **File:** chỉ `docs/SNAPSHOT_CONTRACT.md` và file này, đúng phạm vi phiếu. Không sửa service/web/model/DB/PolicyGate, TIEN_DO, WORKLOG hay `docs/qa/planning-v1/`.

## Đã làm

Hợp đồng snapshot bất biến: schema đóng cho yêu cầu và bản ghi; chuẩn hoá JSON không có số thực; hash SHA-256; vòng đời bảy trạng thái; trình tự transaction lúc chuẩn bị và trước khi gửi; mã lỗi chỉ lấy từ PSC-01; chữ ký hàm cho SNAP-02; ví dụ synthetic tính bằng mã thật; 18 ca bị từ chối; 18 ca test tối thiểu.

## Chỉ đạo mới trong buổi 2

Anh Khang: **cơ sở dữ liệu local bắt buộc lưu trên ổ Data1000**. Đã đưa vào hợp đồng (mục 3): bảng snapshot, grant, ledger đều nằm trong `state.sqlite3` của `/run/media/asus/Data1000/AIMarx/workspace/data`, không có file DB phụ, không có file tạm chứa payload; và phải chặn (`LEDGER_UNAVAILABLE`) khi ổ không gắn thay vì dựng DB mới.

## Kiểm tra thực tế

- **Khoá SQLite trên ổ Data1000** (NTFS, `ntfs3`, SQLite 3.53.1), hai tiến trình thật, DB thử trong `workspace/artifacts/` rồi đã xoá:
  - `BEGIN IMMEDIATE` + CAS: 20/20 lượt đúng một bên thắng.
  - Đối chứng kiểm và ghi tách transaction: **10/10 lượt cả hai cùng thắng**. Test T13 của SNAP-02 phải đỏ trên cách cài đặt này.
  - `BEGIN` thường không để hai bên cùng thắng nhưng bên thua nhận lỗi thô `database is locked`, nên vẫn cần `IMMEDIATE`.
- **Ví dụ mục 10** tính bằng `parser`, `model`, `model_catalog`, `policy_gate` thật ở `839afe9`; `evaluate_policy` cho `CONSENT_REQUIRED` với `synthetic`, `POLICY_DENIED` với `internal`/`unknown`, `PREPARE_LOCAL` với model local.
- Không chạy pytest: PR này chỉ có tài liệu, không đổi mã.

## Phát hiện ngoài phạm vi, cần anh biết

1. **Rút ổ Data1000 rồi khởi động lại ứng dụng.** `/run` là tmpfs; `Service.__init__` gọi `mkdir(parents=True)`. Hôm nay chỉ tình cờ thất bại vì quyền `root:root 0750` của `/run/media/asus` do udisks đặt. Nếu quyền đó đổi, ứng dụng sẽ dựng một DB rỗng trong RAM mà không báo gì. Chặn ở `Service` cần sửa `service.py` → đề xuất gói riêng.
2. **Hai kho DB đang cùng tồn tại** (Data1000 14:05 và bản laptop 12:34). `run-local.sh` và MCP dùng `data` tương đối theo thư mục đang đứng. Chạy nhầm từ bản laptop sẽ đọc/ghi kho cũ.
3. **Chưa kiểm** độ bền khi mất điện hoặc rút ổ lúc đang ghi trên ntfs3, và `fsguard` (`chmod` chỉ đọc) có tác dụng trên NTFS hay không.

## Còn cần chốt (mục 14 của hợp đồng)

Thứ tự `unknown`/`internal`; cách chống A→B→A khi có tính năng đổi nhãn; `PAYLOAD_INTEGRITY` có khoá cloud hay không; TTL 15/60 phút và chờ khoá 5 giây; nơi đặt `revisions.policy`; hàm gác Data1000 thuộc SNAP-02 hay gói riêng.

## Giới hạn

Đây là thiết kế. Không bảo đảm nào ở mục 12 của hợp đồng được coi là "đã có" nếu dòng đó ghi "chưa có". Xong snapshot vẫn chưa gọi được cloud: còn grant (#32), ledger, adapter, rate card và UI xác nhận.

## Việc tiếp theo và điểm dừng

Astra review PR; anh Khang merge. Sau khi merge vào `main` (kiểm bằng `git merge-base --is-ancestor`), SNAP-02 (#31) mới tạo nhánh `claude/snapshot-store` từ `main` mới. **Dừng tại PR này.**
