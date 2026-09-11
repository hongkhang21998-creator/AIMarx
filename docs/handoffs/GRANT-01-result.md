# GRANT-01 — kết quả

- **Ngày, người phụ trách:** 11/09/2026 — Claude (Opus).
- **Issue:** #32. **Nhánh:** `claude/grant-store`, từ `main` `1cfc799` (sau PR #39 SNAP-02 và PR #40 quyết định grant).
- **Quyết định áp dụng:** `docs/GRANT_SCHEMA_OPTIONS.md` — S1/S2, G1–G12 đều A, cộng sáu điều kiện của Astra (điều kiện thắng khi lệch bảng).
- **File:** đúng ba file của phiếu — `src/tro_ly_van_ban/provider_grants.py`, `tests/test_provider_grants.py`, file này. Không sửa UI, service, web, `provider_snapshot.py` hay bảng nghiệp vụ.

## Đã làm

- Bảng `provider_grants` trong `state.sqlite3` (trên Data1000 khi chạy thật). Chỉ lưu hash của token và hash của principal.
- `issue_grant(conn, snapshot_id, *, principal, now_ms) -> IssuedGrant` — cho snapshot `CONSENT_REQUIRED` còn `prepared` và còn hạn; token 256 bit trả về **một lần**; hạn = min(5 phút, hạn snapshot).
- `authorize_dispatch(conn, snapshot_id, token, *, principal, config, now_ms, ledger) -> Authorization` — đường cloud duy nhất, sở hữu transaction: kiểm grant → `_claim_locked` → `ledger.reserve_locked` → grant `consumed`.
- `revoke`, `revoke_all_unconsumed`, `purge_grants`, `ensure_schema`. `Principal`, `RequestExists`.

## Sáu điều kiện của Astra — làm ở đâu

| Điều kiện | Cách làm | Test |
|---|---|---|
| 1. Hàm ngoài sở hữu transaction; cùng thành công hoặc cùng rollback | `authorize_dispatch` mở `_transaction`; `_claim_locked` và ledger nhận vé `_Tx`; commit chỉ khi trọn vẹn hoặc khi "chết có ghi nhận" | ledger lỗi → rollback cả ba; **tiến trình chết thật giữa transaction** (`os._exit`) → không nửa vời |
| 2. Không đường tắt; trước ledger chưa gửi mạng | `authorize_dispatch` **bắt buộc** nhận `ledger` có `reserve_locked`; không có → `LEDGER_UNAVAILABLE`, không đụng DB. Ledger thật chưa có ⇒ hôm nay không có `Authorization` nào ngoài test. MCP/web/service không import module | 3 ca không ledger; kiểm mã nguồn MCP/web/service |
| 3. Principal chỉ là phiên tiến trình; MCP không giả được UI | `Principal` chỉ dựng từ bí mật ≥ 32 byte; DB lưu **SHA-256 của digest**, nên đọc DB không đủ để giả — kể cả khi nhét thẳng giá trị DB vào đối tượng, bỏ qua hàm khởi tạo | giả từ giá trị DB (3 cách + dựng đối tượng trực tiếp) → `PRINCIPAL_MISMATCH` |
| 4. Không commit nửa chừng; đã dùng thì chỉ trả trạng thái sau khi khớp đủ | Snapshot chết → grant `voided` **cùng commit**; lỗi khác rollback. `consumed` chỉ trả `RequestExists` sau khi khớp token, principal, snapshot; sai principal thì vẫn chỉ `CONSENT_REQUIRED` | hai tiến trình cùng token (15 cặp) → đúng một lần giữ ngân sách; sai principal sau khi đã dùng không lộ gì |
| 5. Bấm hai lần → trạng thái hiện có | `issue_grant` kiểm grant có sẵn **trong** `BEGIN IMMEDIATE` → `RequestExists`, không bao giờ `IntegrityError` | bấm hai lần tuần tự; **hai tiến trình** cùng cấp một snapshot → đúng một grant |
| 6. Giữ hồ sơ chưa đối soát | `purge_grants` chỉ xoá grant **chưa từng dẫn tới gửi** (revoked/expired/voided) sau 30 ngày; grant `consumed` **không bao giờ** bị xoá khi chưa có ledger để biết đã đối soát xong | grant consumed có mốc thời gian cũ tuỳ ý vẫn còn |

## Kiểm tra

| Phép thử | Kết quả |
|---|---|
| `pytest -q tests/test_provider_grants.py` | 39 passed |
| `pytest -q tests docs` | 436 passed, 1 skipped (397 cũ + 39 mới) |
| Cùng bộ, `--basetemp` trên ổ Data1000 (NTFS) | 436 passed, 1 skipped |
| Ba test nhiều tiến trình (tranh token, tranh cấp, crash) lặp 10 lần | 10/10 |
| DB sau khi dùng | Không chứa token hay bí mật phiên dưới dạng thô |

**16/16 đột biến bị bắt**: tách kiểm snapshot và tiêu thụ grant thành hai transaction; bỏ kiểm principal / snapshot / hạn / ràng buộc bản ghi; không báo `consumed`; rollback khi snapshot chết (mất `voided`); cho phép chạy không ledger; lưu token thô; bỏ kiểm grant có sẵn khi cấp; grant sống lâu hơn snapshot; purge cả `consumed`; lưu digest thay vì hash của digest; thu hồi bằng principal khác; thu hồi mà không huỷ snapshot; cấp grant cho snapshot local.

Hai lần test **ban đầu không bắt được** đột biến, đã sửa:

1. Test tranh token nới khe ở `evaluate_policy` (theo bài học SNAP-02) — nhưng chỗ đó nằm **trước** claim, nên đột biến "tiêu thụ grant ở transaction riêng" vẫn lọt test này (chỉ test ledger lỗi và test crash bắt được). Chỗ đúng là bước ledger, nằm giữa claim và tiêu thụ; tiến trình con giờ dùng ledger chậm 20 ms, ngủ **trước** khi ghi.
2. Grant `consumed` không có `ended_at_ms`, nên đột biến "purge cả consumed" tình cờ vô hại. Test giờ đặt mốc thời gian cũ cho grant đã dùng và kiểm nó vẫn còn.

## Giới hạn — không được hiểu là đã có

- **Chưa gọi được cloud.** Không có ledger thật, adapter, rate card. `Authorization` chỉ xuất hiện trong test với `FakeLedger`.
- **Principal chưa phải người dùng đã xác thực** (điều kiện 3). Bật cloud thật cần gói đăng nhập local — chưa có issue.
- **Chưa có route UI** cấp và dùng grant (G11: bấm xác nhận thì cấp và gọi `authorize_dispatch` trong cùng request). Chưa có màn hình xem trước.
- **Chưa có retry** (G7): `max_attempts = 1` được khoá bằng `CHECK` trong bảng.
- `_transaction`, `_claim_locked` là tên nội bộ của `provider_snapshot`, được module grant dùng như phần cùng gateway. Python không cấm import tên có gạch dưới; ranh giới giữ bằng quy ước, review và test kiểm mã nguồn MCP/web/service.
- Grant `consumed` được giữ vô thời hạn cho tới khi ledger định nghĩa "đã đối soát".

## Việc tiếp theo và điểm dừng

Astra review PR; anh Khang merge; kiểm `git merge-base --is-ancestor`. Các gói còn thiếu trước khi cloud chạy được, **chưa có issue**: ledger (giữ và đối soát ngân sách, `reserve_locked`), adapter theo provider, rate card, đăng nhập local, route UI xác nhận. **Dừng tại PR này.**
