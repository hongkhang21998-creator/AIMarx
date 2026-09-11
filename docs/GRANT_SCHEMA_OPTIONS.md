# Phương án schema grant — để Astra chốt trước GRANT-01

Người soạn: Claude (Opus), 11/09/2026, theo yêu cầu của anh Khang: đưa phương án **trước khi merge PR #39** (SNAP-02). Issue liên quan: #32 (GRANT-01). Khung trên: [PSC-01](PROVIDER_SECURITY_CONTRACT.md) mục 4–5, [hợp đồng snapshot](SNAPSHOT_CONTRACT.md) mục 7.2 và 15.

Đây là **bảng lựa chọn**, chưa phải thiết kế đã chốt, chưa có dòng mã nào. Mỗi mục có phương án, lý do và một đề xuất; Astra có thể trả lời gọn kiểu `G1:A, G2:A, …` (mẫu ở cuối).

## Kết quả chốt — 11/09/2026 (Astra, qua anh Khang)

```text
S1: A | S2: A
G1: A | G2: A | G3: A | G4: A
G5: đồng ý các trạng thái, không hồi sinh issued
G6: A | G7: A | G8: A | G9: A
G10: theo bảng, kèm điều kiện 4 và 5 dưới đây
G11: A | G12: A, kèm điều kiện 6 dưới đây
```

Sáu điều kiện Astra yêu cầu ghi rõ vào thiết kế — **có hiệu lực cao hơn** chữ trong các bảng phương án bên dưới nếu có chỗ lệch:

1. **S2 — `conn.in_transaction` chưa đủ.** Nó chỉ chứng minh có transaction, không chứng minh là `BEGIN IMMEDIATE`. Hàm ngoài phải **sở hữu** transaction; hàm bên trong không tự commit hay rollback. Kiểm snapshot, tiêu thụ grant và giữ ngân sách phải **cùng thành công hoặc cùng rollback**.
2. **Không dời đường tắt sang `claim_locked`.** Đó là hàm nội bộ của gateway, không được UI, MCP hay adapter gọi trực tiếp. Đường công khai gọi cloud phải đi qua `authorize_dispatch`; **trước khi có ledger thì vẫn chưa được gửi mạng**.
3. **G4 — bí mật lúc khởi động chỉ là định danh phiên tiến trình.** Nó không xác thực người đang bấm và không phân biệt các trình duyệt. Dùng được để xây và test grant; **khi bật cloud phải gắn với phiên người dùng đã xác thực**. MCP không được tự truyền chuỗi principal để giả làm UI.
4. **G5/G10 — lỗi phải có quy tắc commit rõ.** Snapshot hết hiệu lực có thể cần lưu `voided`, nhưng **tuyệt đối không commit nửa chừng** khiến snapshot `dispatching` mà grant chưa `consumed`. Grant đã dùng chỉ trả trạng thái cũ **sau khi khớp token, principal và snapshot**, và không phát lại request.
5. **G11 — bấm hai lần.** Vi phạm `UNIQUE(snapshot_id)` phải trả **trạng thái yêu cầu hiện có**, không phải lỗi SQLite thô, và không tạo lần gửi thứ hai.
6. **G12 — giữ cả hồ sơ chưa đối soát.** Không chỉ giữ grant của snapshot `dispatching`; sau này request đã `failed` mà chi phí còn `unresolved` cũng phải giữ. Hash và principal vẫn là metadata cần bảo vệ (không log, không trả qua MCP).

Đã áp vào PR #39 (commit `4acf954`): điều kiện 1, 2 và phần "không commit nửa chừng" của điều kiện 4 — `_transaction` là nơi duy nhất mở `BEGIN IMMEDIATE` và trao vé `_Tx`; `_claim_locked` đòi vé đó, không commit/rollback; snapshot chết chỉ được ghi trong transaction, hàm ngoài chọn commit hay rollback; `claim_for_dispatch` từ chối snapshot cloud. Điều kiện 3, 5, 6 và phần còn lại của 4 thuộc GRANT-01 (#32).

## Phần 1 — hai quyết định phải chốt TRƯỚC khi merge #39

Hai điểm này làm đổi mã trong PR #39, nên chốt sau khi merge là phải mở thêm một PR sửa lại.

### S1. `claim_for_dispatch` có được claim snapshot cloud mà không có grant?

Hiện tại (#39, đã đọc lại mã): **có**. `claim_for_dispatch` claim cả snapshot `PREPARE_LOCAL` lẫn `CONSENT_REQUIRED`, không cần grant. Chưa có code nào gọi hàm này nên hôm nay vô hại, nhưng đó là một đường tắt vượt qua bước xác nhận, chờ ai đó nối nhầm.

| Phương án | Nội dung | Được | Mất |
|---|---|---|---|
| **A** | Sửa trong #39: `claim_for_dispatch` từ chối snapshot `CONSENT_REQUIRED` (`CONSENT_REQUIRED`). Snapshot cloud chỉ claim được qua hàm của module grant (S2) | Không bao giờ có đường tắt, kể cả khi nối nhầm; test khoá lại ngay | #39 thêm vài dòng + 1–2 test |
| B | Giữ nguyên, ghi cảnh báo trong docstring; GRANT-01 sửa sau | #39 merge ngay | Đường tắt tồn tại trên `main` giữa hai PR; chỉ được bảo vệ bằng lời dặn |

**Đề xuất: A.** Hàng rào trong mã, không phải trong lời dặn.

### S2. Grant và snapshot "cùng một transaction" bằng cách nào?

PSC-01 và hợp đồng snapshot (mục 7.2 bước 8) yêu cầu kiểm snapshot, tiêu thụ grant và (sau này) giữ ngân sách trong **một** transaction. Nhưng `claim_for_dispatch` hiện tự mở và tự commit `BEGIN IMMEDIATE`, nên module khác không chen bước của mình vào giữa được.

| Phương án | Nội dung | Được | Mất |
|---|---|---|---|
| **A** | Tách trong #39: `claim_locked(conn, snapshot_id, *, config, now_ms)` — làm đúng các bước kiểm + CAS nhưng **yêu cầu caller đang giữ `BEGIN IMMEDIATE`** (kiểm `conn.in_transaction`). `claim_for_dispatch` (chỉ cho local) = mở transaction + `claim_locked`. Module grant có `authorize_dispatch` = mở transaction + kiểm/tiêu thụ grant + `claim_locked`; ledger sau này chèn thêm vào đúng hàm đó | Một transaction thật; mỗi module giữ phần của mình; ledger có sẵn chỗ | Sửa #39 (tách hàm, không đổi hành vi) |
| B | Hook: `claim_for_dispatch(..., before_commit=callable)` gọi callable trước CAS | Ít sửa | Callback khó đọc, khó test, dễ bị truyền nhầm từ tầng ngoài |
| C | Hai transaction: claim snapshot rồi mới tiêu thụ grant | Không sửa #39 | **Loại**: đúng dạng lỗi đã đo trên Data1000 (tách transaction → 10/10 lượt thắng đôi) |

**Đề xuất: A**, làm luôn trong #39 cùng S1.

> *Đính chính:* bản đầu của đề xuất này ghi thêm rằng tách hàm sẽ cho chỗ để test bắt đột biến "commit sát trước lệnh ghi". Không đúng: bước tiêu thụ grant nằm **sau** CAS, ngoài hàm nội bộ. Đột biến đó chỉ sống khi đồng thời bỏ cả CAS, xem `docs/handoffs/SNAP-02-result.md`.

## Phần 2 — schema grant cho GRANT-01 (#32)

### G1. Grant ràng buộc với snapshot thế nào?

PSC-01 liệt kê grant phải ràng buộc: payload hash, source versions, provider/model/endpoint revision, policy revision, pricing revision. Tất cả những thứ đó **đã nằm trong bản ghi snapshot**, được băm thành `record_sha256` (#39).

| Phương án | Grant lưu | Nhận xét |
|---|---|---|
| **A** | `snapshot_id` + `snapshot_record_sha256` + `payload_sha256` | Một hash phủ đủ danh sách PSC-01; lúc tiêu thụ so lại với snapshot. Bản ghi snapshot bị thay hay sửa là grant không khớp |
| B | Chỉ `snapshot_id` | Gọn, nhưng tin hoàn toàn vào bảng snapshot; mất một lớp kiểm độc lập |
| C | Chép lại từng trường (versions, revisions…) vào grant | Trùng lặp, hai nơi phải giữ đồng bộ, không thêm an toàn so với A |

**Đề xuất: A.**

### G2. Bao nhiêu grant cho một snapshot?

| Phương án | Nội dung |
|---|---|
| **A** | Đúng **một**: `UNIQUE(snapshot_id)`. Grant hết hạn hay bị thu hồi thì chuẩn bị snapshot mới rồi xác nhận lại |
| B | Nhiều grant nối tiếp cho cùng snapshot (xác nhận lại khi grant cũ hết hạn) |

**Đề xuất: A.** Snapshot sống 15 phút, grant 5 phút; bấm lại "chuẩn bị" không tốn gì, còn B phải lý giải grant nào đang hiệu lực.

### G3. Token và cách lưu

| Phương án | Nội dung | Nhận xét |
|---|---|---|
| **A** | `secrets.token_urlsafe(32)` (256 bit); DB chỉ lưu `SHA-256(token)`; tra theo hash | Token ngẫu nhiên 256 bit không thể dò ngược từ hash, nên không cần salt; tra theo chỉ mục hash nên không có rò rỉ qua thời gian so sánh |
| B | HMAC-SHA256 với khoá bí mật trong keyring hệ điều hành | Chống được cả kẻ đọc DB **và** có token ứng viên — kịch bản gần như không tồn tại với token 256 bit; đổi lại phải quản lý khoá |

**Đề xuất: A.** Token chỉ trả về **một lần** lúc cấp, không bao giờ vào log, exception, `repr` hay trang lỗi (#32 yêu cầu test).

### G4. "Principal tin cậy" trong ứng dụng một người dùng là gì?

Hiện UI chỉ có token CSRF sinh mỗi lần khởi động tiến trình (`web.py`), chưa có đăng nhập. PSC-01 yêu cầu phiên đăng nhập local **trước khi bật cloud**, nhưng chưa có gói nào làm.

| Phương án | Principal | Được | Mất |
|---|---|---|---|
| **A** | `ui:` + hash của một bí mật phiên do UI sinh lúc khởi động (tách khỏi token CSRF). Grant chỉ cấp và chỉ dùng được từ UI; MCP **không có** principal nên không bao giờ giữ được grant | Làm được ngay, test được bằng principal giả lập; khởi động lại UI là mọi grant chưa dùng mất hiệu lực (điều mong muốn) | Chưa phải đăng nhập thật: ai mở được trình duyệt trên máy là dùng được |
| B | Người dùng hệ điều hành (uid) | Không phải làm gì | Mọi tiến trình của asus đều cùng uid, kể cả MCP — không phân biệt được gì |
| C | Chờ gói đăng nhập local rồi mới làm grant | Đúng PSC-01 nhất | Chặn GRANT-01 vô thời hạn |

**Đề xuất: A**, và ghi rõ trong #32: **đăng nhập local vẫn là điều kiện trước khi bật cloud thật** (PSC-01 mục 4 bước 3); A chỉ là principal đủ để xây và test grant.

### G5. Trạng thái grant

```text
issued ──(authorize_dispatch thành công)──► consumed
   ├──(người dùng thu hồi / thu hồi hàng loạt)──► revoked
   ├──(quá hạn, phát hiện lúc dùng)──► expired
   └──(snapshot chết khi kiểm lúc dùng)──► voided
```

Không có đường nào quay về `issued`. Câu cần chốt là **G6**.

### G6. Tiêu thụ rồi mà mạng chưa bao giờ được gọi (adapter crash trước khi gửi)?

| Phương án | Nội dung |
|---|---|
| **A** | Không bao giờ hoàn lại. `consumed` là `consumed`; người dùng chuẩn bị và xác nhận lại. Khớp PSC-01: không rõ đã gửi hay chưa thì coi như có thể đã gửi |
| B | Hoàn lại khi adapter chứng minh chưa gửi byte nào | Phải tin lời adapter; mở lại đúng lỗ "hồi sinh token" mà #32 cấm |

**Đề xuất: A.**

### G7. Retry trong cùng một logical request

PSC-01 cho tối đa 2 attempt trong một request, và thu hồi hay hết hạn phải chặn cả attempt chưa gửi tiếp theo.

| Phương án | Nội dung | Nhận xét |
|---|---|---|
| **A** | GRANT-01 chỉ làm attempt đầu (`max_attempts = 1`, cột có sẵn). Retry thiết kế cùng ledger, vì mỗi attempt phải giữ ngân sách riêng | Gọn, đúng thứ tự phụ thuộc |
| B | Làm luôn `authorize_retry`: grant `consumed`, chưa thu hồi, chưa hết hạn, `attempts_used < max_attempts` | Có sẵn khi ledger tới, nhưng chưa có ledger thì không test được trọn |

**Đề xuất: A.**

### G8. Thời hạn grant

| Phương án | Nội dung |
|---|---|
| **A** | `expires = min(cấp + 5 phút, snapshot.expires_at_ms)` — grant không bao giờ sống lâu hơn snapshot |
| B | 5 phút độc lập |

**Đề xuất: A.** Với B, snapshot chết trước thì grant vẫn "còn hạn" trên giấy, gây nhầm khi đối soát.

### G9. Grant cho snapshot local (`PREPARE_LOCAL`)?

| Phương án | Nội dung |
|---|---|
| **A** | Không. Grant chỉ dành cho `CONSENT_REQUIRED`; local đi `claim_for_dispatch` như hôm nay (khớp S1-A). Trích xuất local hiện chạy không cần xác nhận, không đổi trải nghiệm |
| B | Mọi dispatch đều qua grant, kể cả local | Một đường duy nhất, nhưng thêm một bước bấm cho mọi lần trích xuất local — trái chỉ đạo giữ UX |

**Đề xuất: A.**

### G10. Mã lỗi khi dùng grant

Để không thành "máy dò" token, mọi trường hợp **trước khi** khớp được cả token lẫn principal trả cùng một mã.

| Tình huống | Mã công khai (tập PSC-01) |
|---|---|
| Token không tồn tại, sai principal, bị thu hồi, không khớp snapshot | `CONSENT_REQUIRED` |
| Token và principal khớp nhưng grant đã hết hạn | `CONSENT_EXPIRED` |
| Grant hợp lệ nhưng snapshot chết khi kiểm lại | mã của snapshot (`STALE_REQUEST`/`CONSENT_EXPIRED`), grant → `voided` |
| Grant đã `consumed` | trả trạng thái request hiện có (PSC-01 mục 4), không phải lỗi |

**Đề xuất: như bảng.** Lý do cụ thể ghi vào `end_reason` để đối soát.

### G11. Token đi từ lúc xác nhận tới lúc gửi bằng đường nào?

Đây là việc của tầng UI, nhưng quyết định sớm để GRANT-01 không làm sai giả định.

| Phương án | Nội dung | Nhận xét |
|---|---|---|
| **A** | Route xác nhận (POST, có CSRF) cấp grant và **gọi `authorize_dispatch` ngay trong cùng request**; token không bao giờ rời backend | Không có token trong HTML, URL hay cookie; ít bề mặt nhất. Hợp với ứng dụng một người dùng, một cửa sổ |
| B | Trả token trong ô ẩn của trang, bấm "gửi" lần hai mang token về | Người dùng có một bước "nhìn lại" — nhưng bản xem trước đã là bước đó rồi |
| C | Cookie HttpOnly | Thêm quản lý cookie, không thêm an toàn so với A |

**Đề xuất: A.** Grant vẫn tồn tại như một bản ghi độc lập (để thu hồi, hết hạn, đối soát, chống bấm hai lần), chỉ token là không phải đi đâu.

### G12. Lưu và dọn

| Phương án | Nội dung |
|---|---|
| **A** | Bảng `provider_grants` trong `state.sqlite3` trên Data1000 (hợp đồng snapshot mục 3.1). Không có nội dung nhạy cảm (chỉ hash). Giữ 30 ngày theo mức log PSC-01, **trừ** grant gắn với snapshot còn `dispatching` (chờ đối soát) |
| B | Xoá ngay sau khi snapshot kết thúc |

**Đề xuất: A.** B làm mất dấu vết "ai đã xác nhận gì" đúng lúc cần đối soát nhất.

## Gói đề xuất (nếu chọn toàn bộ phương án A)

```text
provider_grants
  grant_id                TEXT PRIMARY KEY          -- 32 hex, không phải bí mật
  token_sha256            TEXT NOT NULL UNIQUE      -- G3
  snapshot_id             TEXT NOT NULL UNIQUE      -- G2
  snapshot_record_sha256  TEXT NOT NULL             -- G1
  payload_sha256          TEXT NOT NULL             -- G1
  principal_sha256        TEXT NOT NULL             -- G4
  issued_at_ms            INTEGER NOT NULL
  expires_at_ms           INTEGER NOT NULL          -- G8
  state                   TEXT NOT NULL CHECK(state IN ('issued','consumed','revoked','expired','voided'))
  consumed_at_ms          INTEGER
  ended_at_ms             INTEGER
  end_reason              TEXT
  max_attempts            INTEGER NOT NULL DEFAULT 1  -- G7
  attempts_used           INTEGER NOT NULL DEFAULT 0
```

```python
def issue_grant(conn, snapshot_id, *, principal: str, now_ms: int) -> tuple[str, str]:
    """(grant_id, token). Chỉ route xác nhận của UI gọi. Snapshot phải prepared, CONSENT_REQUIRED, còn hạn."""

def authorize_dispatch(conn, snapshot_id, token, *, principal: str, config, now_ms: int) -> SnapshotView:
    """Sở hữu transaction (điều kiện 1): with _transaction(conn) as tx → kiểm grant → _claim_locked(tx, …,
    expected_decision="CONSENT_REQUIRED") → grant consumed → (ledger giữ ngân sách). Snapshot chết
    (_SnapshotDied) → grant voided rồi commit cả hai; lỗi khác → rollback cả khối (điều kiện 4).
    Trước khi có ledger: KHÔNG trả thứ gì cho phép adapter gửi mạng (điều kiện 2)."""

def revoke(conn, grant_id, *, now_ms: int) -> None: ...
def revoke_all_unconsumed(conn, *, now_ms: int) -> int: ...   # nút "thu hồi hết"
```

Test tối thiểu, bám yêu cầu của #32: đồng hồ giả (biên 5 phút, biên hạn snapshot); **hai tiến trình** cùng `authorize_dispatch` một token (nới khe ở bước tiêu thụ, như bài học T13 của #39); thu hồi trước/sau khi tiêu thụ; sai principal / hash / revision; khởi động lại không hồi sinh `consumed`; crash giữa transaction (không có trạng thái nửa vời); sentinel token không xuất hiện trong exception, `repr`, log; MCP không có đường cấp hay dùng grant; và đột biến "tiêu thụ grant ở transaction riêng" phải làm test đỏ.

## Chưa nằm trong GRANT-01 dù chọn phương án nào

Ledger và giữ ngân sách, retry, adapter, rate card, đăng nhập local, màn hình xem trước. Xong GRANT-01, cloud **vẫn** chưa gọi được.

## Mẫu trả lời

```text
S1: A | S2: A
G1: A | G2: A | G3: A | G4: A | G6: A | G7: A | G8: A | G9: A | G10: như bảng | G11: A | G12: A
Ghi chú:
```

Nếu chọn S1-A và S2-A, Claude sửa luôn PR #39 (tách `claim_locked`, chặn `CONSENT_REQUIRED` ở `claim_for_dispatch`, thêm test), chạy lại toàn bộ và đột biến, rồi anh Khang mới merge.
