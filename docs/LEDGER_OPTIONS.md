# Phương án ledger ngân sách — để Astra chốt trước LEDGER-01

Người soạn: Claude (Opus), 11/09/2026, theo yêu cầu của anh Khang. Chưa có issue giao việc; đề xuất Astra tạo **LEDGER-01** sau khi chốt. Khung trên: [PSC-01](PROVIDER_SECURITY_CONTRACT.md) mục 5–7 và 9, [quyết định grant](GRANT_SCHEMA_OPTIONS.md) (đặc biệt điều kiện 1, 2, 4, 6), mã đã merge `provider_snapshot.py` (#39) và `provider_grants.py` (#41).

Đây là **bảng lựa chọn**, chưa có dòng mã nào. Mỗi mục có phương án, lý do và một đề xuất; Astra trả lời gọn theo mẫu ở cuối. Ledger là mảnh **mở khoá đường tới mạng** (điều kiện 2 của grant), nên cẩn thận hơn mọi gói trước.

**Không có gì trong tài liệu này cấp quyền chi tiền.** Ngân sách mặc định là 0; mức thử 0,02 / 0,20 / 2 USD của PSC-01 vẫn là đề xuất chờ anh Khang duyệt riêng.

## Phần 1 — ba điểm đụng tới mã đã merge

### P1. `Authorization` không mang theo khoản giữ tiền

Đọc lại `provider_grants.py`: `authorize_dispatch` gọi `reserve(tx, …)` rồi **bỏ giá trị trả về**; `Authorization` chỉ có `grant_id` và `snapshot`. Adapter gửi xong sẽ không biết quyết toán vào khoản nào.

| Phương án | Nội dung |
|---|---|
| **A** | Sửa trong LEDGER-01: `reserve_locked` trả `Reservation(attempt_id, reserved_micro_usd, pricing_revision)`; `Authorization` thêm trường `reservation`. Adapter chỉ nhận `Authorization`, không tự tra DB |
| B | Adapter tự tra khoản giữ theo `snapshot_id` | Thêm một đường đọc DB ngoài transaction; hai nguồn sự thật |

**Đề xuất: A.**

### P2. Quyết toán và đóng snapshot phải cùng một transaction

`provider_snapshot.finish` tự mở transaction riêng. Nếu quyết toán tiền và `finish` ở hai transaction, crash giữa chừng sẽ để lại snapshot `completed` mà khoản tiền còn `reserved`, hoặc ngược lại.

| Phương án | Nội dung | Nhận xét |
|---|---|---|
| **A** | Thêm `_finish_locked(tx, snapshot_id, *, outcome, now_ms)` vào `provider_snapshot` — cùng kiểu `_claim_locked`: đòi vé `_Tx`, không commit. `finish` công khai = `_transaction` + `_finish_locked`. Ledger có `settle(...)` sở hữu transaction: quyết toán + `_finish_locked` | Đúng khuôn điều kiện 1 đã chốt |
| B | Ledger ghi thẳng vào bảng `provider_snapshots` | Phá quyền sở hữu bảng; hai module cùng viết một trạng thái |
| C | Hai transaction, đối soát sau | Loại: đúng dạng "nửa chừng" mà điều kiện 4 cấm |

**Đề xuất: A.** Sửa nhỏ trong `provider_snapshot.py`, cùng PR LEDGER-01.

### P3. `revisions.pricing` nghĩa là gì

Hiện là một chuỗi tự do do backend cấp (#39). Snapshot đã ghim nó, và mọi thay đổi đã làm snapshot chết (`REVISION_CHANGED`).

| Phương án | Nội dung |
|---|---|
| **A** | `pricing` = `sha256(canonical_json(mục rate card của đúng provider/model/endpoint))`. Sửa một con số giá, hay rate card được xác minh lại, là snapshot cũ chết — người dùng xem lại trần phí rồi mới xác nhận |
| B | Chuỗi phiên bản do người sửa rate card tự đặt | Phụ thuộc người sửa nhớ tăng số — đúng kiểu lỗi đã tránh ở `revisions.policy` |

**Đề xuất: A.** Không đổi mã đã merge, chỉ chốt nghĩa.

## Phần 2 — tiền và cách tính

### L1. Đơn vị tiền

| Phương án | Nội dung | Nhận xét |
|---|---|---|
| **A** | Số tiền là **số nguyên micro-USD** (1 USD = 1.000.000). Đơn giá lưu là **số nguyên micro-USD cho 1 triệu token**. Mọi phép tính là số nguyên, làm tròn **lên** | Không có sai số; khớp luật "không số thực" của snapshot. Ví dụ 0,27 USD/1M token = `270000` |
| B | `Decimal` lưu dạng chuỗi | Đúng nhưng mọi truy vấn cộng dồn phải làm ngoài SQL |
| C | `float` | **Loại** (PSC-01 cấm) |

**Đề xuất: A.** Công thức theo PSC-01, viết lại cho số nguyên:

```text
R_attempt = ceil( (I_bound × P_in + O_cap × P_out) / 1.000.000 ) + phí_cố_định_mỗi_request
```

### L2. Cận trên số token đầu vào (`I_bound`)

PSC-01: chỉ chấp nhận cận đã xác minh cho model, **không** dùng "số ký tự / 4", không gọi model để ước lượng.

| Phương án | Nội dung | Nhận xét |
|---|---|---|
| **A** | `I_bound = payload_size (số byte UTF-8) + phụ phí khung` (ví dụ 32 token/message + 256 token cố định; con số do adapter xác minh cho từng provider) | Với tokenizer **byte-level** (mỗi token phủ ít nhất một byte), số token không thể vượt số byte — đây là cận **đúng về toán**, không phải ước lượng. Rất bảo thủ với tiếng Việt (2–3 byte/chữ). Chỉ bật model mà adapter xác nhận được là tokenizer byte-level; không xác nhận được thì chặn |
| B | Mang tokenizer của từng model về máy để đếm chính xác | Chính xác hơn, nhưng phải tải và kiểm tệp tokenizer khớp đúng model đang bán — khó chứng minh |
| C | Gọi API đếm token của nhà cung cấp | **Loại**: gửi nội dung ra ngoài trước khi người dùng xác nhận |

**Đề xuất: A.** Ví dụ với snapshot mẫu của hợp đồng (3.488 byte, 2 message): `I_bound = 3.488 + 2×32 + 256 = 3.808`.

### L3. Token đầu ra và token suy luận ẩn

| Phương án | Nội dung |
|---|---|
| **A** | `O_cap = settings.max_output_tokens` của snapshot (≤ 2.048). **Chỉ bật model** mà tài liệu chính thức nói rõ phần suy luận ẩn nằm **trong** giới hạn đó. Model không giới hạn được suy luận thì không bật ở v1 (PSC-01 mục 5) |
| B | Cho thêm trần suy luận riêng trong rate card | Mở rộng được, nhưng phải tin rằng nhà cung cấp tôn trọng trần đó |

**Đề xuất: A.**

Ví dụ với **giá giả lập** 1 USD/1M đầu vào, 2 USD/1M đầu ra: `R = ceil((3.808 × 1.000.000 + 2.048 × 2.000.000) / 1.000.000) = 7.904 micro-USD ≈ 0,0079 USD`, dưới trần đề xuất 0,02 USD/request.

### L4. Rate card nằm ở đâu

PSC-01: không hardcode giá trong mã; mỗi mục có provider/model/endpoint, đơn giá, tiền tệ, nguồn chính thức, `verified_at`, `expires_at` ≤ 7 ngày. Thiếu hoặc hết hạn thì chặn.

| Phương án | Nội dung | Nhận xét |
|---|---|---|
| **A** | Tệp JSON riêng máy, cạnh kho dữ liệu trên Data1000 (ví dụ `…/workspace/config/rate_cards.json`), **người** sửa sau khi tự đọc trang giá chính thức; schema đóng; không commit | Ai sửa, sửa gì đều rõ; không có đường nào để model hay MCP ghi |
| B | Bảng trong DB, sửa qua UI | Cần thêm UI, thêm quyền |
| C | Nằm trong repo | **Loại**: PSC-01 cấm giá trong mã nguồn |

**Đề xuất: A.** Rate card hết hạn lúc giữ tiền → `PRICING_UNVERIFIED`, trước khi đụng mạng. Tiền tệ khác USD → `PRICING_UNVERIFIED`.

### L5. Hạn mức nằm ở đâu và ai được đổi

| Phương án | Nội dung |
|---|---|
| **A** | Cùng tệp cấu hình riêng máy; **mặc định 0** (mọi yêu cầu cloud ra `BUDGET_EXCEEDED`). Chỉ anh Khang sửa tay. Mỗi khoản giữ ghi lại `limits_revision` (hash của bộ hạn mức lúc đó) để đối soát |
| B | Sửa qua UI |

**Đề xuất: A.** Việc bật mức thử 0,02 / 0,20 / 2 USD là một quyết định **riêng**, không nằm trong PR ledger.

### L6. Ngày và tháng tính theo giờ nào

| Phương án | Nội dung | Nhận xét |
|---|---|---|
| **A** | Độ lệch cố định UTC+7 (Việt Nam không đổi giờ mùa hè) | Không phụ thuộc gói `tzdata` — Windows không có sẵn cơ sở dữ liệu múi giờ |
| B | `zoneinfo("Asia/Ho_Chi_Minh")` | Đúng về hình thức, nhưng trên Windows phải cài thêm `tzdata` |

**Đề xuất: A**, kèm test biên nửa đêm 23:59:59,999 → 00:00:00,000 giờ Việt Nam.

### L7. Công thức kiểm hạn mức

Theo PSC-01 mục 7 — mục này để **xác nhận cách hiểu**, không có lựa chọn khác an toàn hơn:

```text
request:  tổng mọi khoản (giữ + đã quyết toán + chưa rõ) của request này + R_mới     ≤ hạn mức request
ngày:     đã quyết toán có thời điểm bắt đầu trong ngày hôm nay
          + TẤT CẢ khoản đang giữ + TẤT CẢ khoản chưa rõ (kỳ nào cũng tính)  + R_mới  ≤ hạn mức ngày
tháng:    như ngày, với tháng hiện tại                                                ≤ hạn mức tháng
```

Khoản đang giữ và khoản chưa rõ **không được biến mất nhờ qua nửa đêm**. Kiểm và ghi nằm trong transaction của `authorize_dispatch` (`BEGIN IMMEDIATE`), nên hai yêu cầu sát hạn mức không thể cùng lọt.

**Đề xuất: xác nhận.**

## Phần 3 — trạng thái và vòng đời

### L8. Trạng thái một khoản (attempt)

```text
reserved ──(usage hợp lệ, ≤ khoản giữ)──────────► settled
    ├────(adapter chứng minh chưa gửi byte nào)──► released
    ├────(usage thiếu/sai, timeout sau khi gửi, crash)──► unresolved ──(đối soát tay)──► reconciled
    └────(usage thật > khoản giữ)────────────────► over_reserve  + khoá provider (L11)
```

`reserved` được ghi **trước** khi gửi, trong transaction của `authorize_dispatch`. Không có đường quay về `reserved`.

**Đề xuất: đồng ý sơ đồ.**

### L9. Retry

| Phương án | Nội dung |
|---|---|
| **A** | v1 **một** attempt mỗi request, khớp `max_attempts = 1` của grant (G7). Retry là gói sau |
| B | Làm luôn attempt thứ hai với khoản giữ riêng |

**Đề xuất: A.**

### L10. Khởi động lại

| Phương án | Nội dung |
|---|---|
| **A** | Hàm `recover_on_start(now_ms)` gọi một lần khi backend khởi động: mọi khoản `reserved` quá hạn chót của request (60 giây, PSC-01 mục 6) chuyển `unresolved`. Không phát lại request. Chạy lại nhiều lần vẫn cùng kết quả |
| B | Chuyển lười khi có người đọc |

**Đề xuất: A.**

### L11. Usage thật vượt khoản giữ

| Phương án | Nội dung |
|---|---|
| **A** | Ghi đủ số thật (không cắt cho đẹp), trạng thái `over_reserve`, **khoá riêng provider đó** cho tới khi đối soát tay xong |
| B | Khoá toàn bộ cloud |

**Đề xuất: A.**

### L12. Đối soát tay

| Phương án | Nội dung |
|---|---|
| **A** | Chỉ qua UI local, cần `Principal`; ghi số thật, bằng chứng (mã hoá đơn hoặc ghi chú ≤ 500 ký tự, không chứa nội dung tài liệu), thời điểm. Ghi thêm, **không sửa** dòng cũ. MCP và model không có đường nào |
| B | Cho phép thêm dòng lệnh CLI |

**Đề xuất: A.**

### L13. Khi nào được giải phóng khoản giữ

| Phương án | Nội dung |
|---|---|
| **A** | **Chỉ** khi adapter chứng minh chưa gửi byte nào (lỗi pool/connect trước khi gửi body). Mọi trường hợp khác — kể cả 4xx — là quyết toán theo usage nếu có, không có thì `unresolved` |
| B | Coi 400/401/403 là "không tính phí" và giải phóng |

**Đề xuất: A.** PSC-01 mục 6 thận trọng đúng chỗ này: nhà cung cấp không cam kết request lỗi là miễn phí.

## Phần 4 — an toàn của chính sổ

### L14. Đồng hồ bị lùi

| Phương án | Nội dung |
|---|---|
| **A** | Từ chối giữ tiền (`LEDGER_UNAVAILABLE`) nếu `now_ms` sớm hơn mốc mới nhất trong sổ quá 5 phút — chặn việc lùi đồng hồ để "được" sang ngày cũ |
| B | Không kiểm |

**Đề xuất: A.**

### L15. Sổ hỏng hoặc không ghi được

| Phương án | Nội dung |
|---|---|
| **A** | Mọi lỗi SQLite, số âm, tổng không khớp giữa các trạng thái → `LEDGER_UNAVAILABLE`, chặn cloud. Không bao giờ "đoán" số dư |
| B | Ghi cảnh báo rồi cho qua |

**Đề xuất: A.**

### L16. Lưu giữ

| Phương án | Nội dung |
|---|---|
| **A** | Không bao giờ tự xoá dòng sổ (mỗi dòng vài chục byte). Nhật ký thay đổi chỉ ghi thêm. Khớp điều kiện 6 của grant |
| B | Xoá khoản đã quyết toán quá 13 tháng |

**Đề xuất: A.**

## Gói đề xuất (nếu chọn toàn bộ phương án A)

```text
ledger_attempts
  attempt_id          TEXT PRIMARY KEY
  snapshot_id         TEXT NOT NULL UNIQUE      -- một request = một snapshot = một attempt (L9)
  grant_id            TEXT NOT NULL UNIQUE
  provider, model     TEXT NOT NULL
  pricing_revision    TEXT NOT NULL             -- P3
  limits_revision     TEXT NOT NULL             -- L5
  reserved_micro_usd  INTEGER NOT NULL CHECK(reserved_micro_usd > 0)
  actual_micro_usd    INTEGER CHECK(actual_micro_usd >= 0)
  started_at_ms       INTEGER NOT NULL          -- quyết định ngày/tháng (L6, L7)
  state               TEXT NOT NULL CHECK(state IN ('reserved','settled','released','unresolved','reconciled','over_reserve'))
  ended_at_ms, end_reason

ledger_events   -- chỉ ghi thêm: mọi lần đổi trạng thái, ai (hash principal), bằng chứng
ledger_locks    -- provider bị khoá sau over_reserve (L11)
```

```python
class Ledger:                                   # backend dựng từ tệp cấu hình riêng máy (L4, L5)
    def reserve_locked(self, tx, *, snapshot, grant_id, now_ms) -> Reservation   # P1; trong transaction của authorize_dispatch
def settle(conn, attempt_id, *, usage, now_ms) -> None           # P2: quyết toán + _finish_locked, một transaction
def mark_unresolved(conn, attempt_id, *, reason, now_ms) -> None
def release_unsent(conn, attempt_id, *, proof, now_ms) -> None  # L13
def recover_on_start(conn, *, now_ms) -> int                    # L10
def reconcile(conn, attempt_id, *, principal, actual_micro_usd, evidence, now_ms) -> None  # L12
```

Test tối thiểu, theo PSC-01 mục 9:
- hai **tiến trình** cùng giữ tiền sát hạn mức → tổng không vượt; nới khe ở đúng giữa bước tính tổng và bước ghi;
- qua nửa đêm, qua tháng: khoản giữ và khoản chưa rõ vẫn tính;
- crash sau khi gửi → `unresolved` khi khởi động lại, không phát lại;
- usage vượt khoản giữ → khoá provider;
- rate card hết hạn, sai tiền tệ, số âm, bool thay số → chặn trước mạng;
- hạn mức 0 → `BUDGET_EXCEEDED`;
- lỗi SQLite → `LEDGER_UNAVAILABLE`;
- đồng hồ lùi → chặn;
- đột biến "giữ tiền ở transaction riêng" phải làm test đỏ.

## Sau ledger vẫn chưa gọi được cloud

Còn: adapter từng provider (endpoint allowlist, TLS, chặn redirect/proxy, timeout, không log body), tệp rate card đầu tiên do người xác minh, đăng nhập local (điều kiện 3 của grant), route UI xác nhận, và quyết định riêng của anh Khang về mức chi thử.

## Mẫu trả lời

```text
P1: A | P2: A | P3: A
L1: A | L2: A | L3: A | L4: A | L5: A | L6: A | L7: xác nhận
L8: đồng ý | L9: A | L10: A | L11: A | L12: A | L13: A
L14: A | L15: A | L16: A
Điều kiện thêm:
```
