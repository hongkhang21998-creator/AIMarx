# SNAP-02 — kết quả

- **Ngày, người phụ trách:** 11/09/2026 — Claude (Opus). Anh Khang yêu cầu làm trọn gói trong một lượt.
- **Issue:** #31. **Nhánh:** `claude/snapshot-store`, từ `main` `f018c08` (sau PR #37 hợp đồng SNAP-01 và PR #38 hàng rào Data1000).
- **File:** đúng ba file của phiếu — `src/tro_ly_van_ban/provider_snapshot.py`, `tests/test_provider_snapshot.py`, file này. Không sửa `service.py`, `web.py`, `model.py`, `policy_gate.py`, bảng DB hiện có, TIEN_DO, WORKLOG hay file của Luna.

## Đã làm

Triển khai toàn bộ hợp đồng `docs/SNAPSHOT_CONTRACT.md`:

- `canonical_json`: kiểu đóng (không số thực, không tuple/bytes/subclass, số nguyên trong ±(2⁵³−1)), không chuẩn hoá Unicode, chỉ sắp khoá object.
- `prepare_snapshot`: kiểm `PrepareRequest` đóng; trong **một** `BEGIN IMMEDIATE` đọc tài liệu, nhãn, phiên bản từ DB, dựng payload, gọi `evaluate_policy`, rồi mới ghi. Bị từ chối thì không ghi gì.
- `claim_for_dispatch` (**chỉ snapshot local**) và `_claim_locked` (nội bộ gateway): nhận **chỉ** `snapshot_id`; kiểm lại hạn, hash payload **và** bản ghi, từng nguồn (nhãn, phiên bản, block), đủ 8 revision, đánh giá lại policy; rồi `prepared → dispatching` bằng CAS, cùng transaction. Xem mục "Sửa theo quyết định S1/S2".
- `finish`, `cancel`, `purge`, `load_snapshot`, `ensure_schema`. Bảng riêng `provider_snapshots`, không đụng bảng của `Service`.

## Sửa theo quyết định S1/S2 (Astra chốt 11/09, `docs/GRANT_SCHEMA_OPTIONS.md`)

- **S1 — không có đường tắt cho cloud.** `claim_for_dispatch` từ chối snapshot `CONSENT_REQUIRED` bằng `CONSENT_REQUIRED` (`GRANT_REQUIRED`) **trước mọi phép kiểm**, không đổi gì trên snapshot — kể cả khi snapshot đã hết hạn — để người dùng vẫn xác nhận được qua đường grant. Đường cloud duy nhất sẽ là `authorize_dispatch` của #32; trước khi có ledger, đường đó vẫn chưa được gửi mạng.
- **S2 — hàm ngoài sở hữu transaction.** Theo điều kiện 1 của Astra, `conn.in_transaction` không đủ. `_transaction(conn)` là nơi **duy nhất** mở `BEGIN IMMEDIATE`; nó trao lại vé `_Tx`, commit khi khối kết thúc bình thường và rollback khi có lỗi. `_claim_locked(tx, …, expected_decision)` đòi đúng vé đó (kết nối trần hay vé của transaction đã đóng → `RuntimeError`), **không bao giờ commit hay rollback**.
- **Không commit nửa chừng** (điều kiện 4). Snapshot chết thì `_claim_locked` chỉ ghi `expired`/`invalidated` vào transaction rồi báo `_SnapshotDied`; hàm ngoài chọn commit (cùng phần của nó, như grant `voided`) hoặc rollback cả khối. Cơ chế cũ `_CommitThenRaise` — hàm trong ra lệnh commit — đã bỏ. Không có đường nào commit `dispatching` riêng khỏi bước grant.
- `_claim_locked` và `_transaction` là **nội bộ gateway**, không được UI, MCP hay adapter gọi (điều kiện 2). Python không chặn được việc import tên có gạch dưới; ranh giới này giữ bằng quy ước và review.

## Kiểm tra

| Phép thử | Kết quả |
|---|---|
| `pytest -q tests/test_provider_snapshot.py` | 94 passed (thêm 8 test S1/S2) |
| `pytest -q tests docs` | 397 passed, 1 skipped (303 cũ + 94 mới) |
| Cùng bộ, `--basetemp` trên ổ Data1000 (NTFS) | 397 passed, 1 skipped |
| Tiến trình khác đọc DB **trong lúc** hàm ngoài chưa commit | Vẫn thấy `prepared` — chứng minh `_claim_locked` không tự commit |
| T13 (hai **tiến trình** `spawn`, 20 snapshot) lặp 10 lần | 10/10 đạt, mỗi snapshot đúng một bên thắng, bên thua nhận trạng thái chứ không nhận lỗi thô |
| Ví dụ mục 10 của hợp đồng | Khớp từng hash: `blocks_sha256` 81e826…, 3.488 byte, `payload_sha256` 8d31cb…, schema b0f3d8…, catalogue ab02a3… |

**Đột biến** — sửa mã cho sai có chủ đích, chạy lại bộ test, khôi phục:

| Đột biến | Bị bắt? |
|---|---|
| `BEGIN` thường + bỏ CAS | Có — T13, test DB bận |
| Đọc trạng thái, commit, rồi mới kiểm và ghi không CAS | Có — T13 |
| Bỏ kiểm nhãn / phiên bản / revision / hash / policy lúc claim | Có — T9 / T9 / T10 (14 ca) / T8 / T11 |
| Lấy nhãn **ít** hạn chế nhất | Có — 4 test |
| Bỏ kiểm đồng hồ lùi | Có — T12 |
| Nhận nhãn từ request | Có — T4 |
| Purge cả `dispatching` | Có — T16 |
| Ghi snapshot khi policy từ chối | Có — 7 test |
| `_claim_locked` tự commit | Có — 2 test S2 |
| Đường công khai claim được snapshot cloud | Có — 3 test S1 |
| Bỏ kiểm vé transaction | Có — test S2 |
| Hàm ngoài commit cả khi có lỗi | Có — 2 test S2 |
| **Chỉ bỏ CAS, giữ `BEGIN IMMEDIATE`** | **Không** — đúng thiết kế: khoá tự nó đã chặn thắng hai lần, CAS là lớp dự phòng thứ hai nên không tách riêng được |
| **Commit sát trước lệnh ghi *và* bỏ CAS** | **Không** — phải hỏng **cả hai** lớp cùng lúc; còn CAS thì tiến trình vào sau thấy `rowcount = 0` và thua. Khe chỉ vài micro giây, không có lời gọi nào ở giữa để nới. Bản trước của file này ghi rằng tách hàm sẽ cho chỗ nới khe — không đúng: bước grant nằm **sau** CAS, ngoài `_claim_locked` |

Tổng: 16/18 đột biến bị bắt.

Lần đầu T13 **không** bắt được đột biến tách transaction (lọt 20/20 lượt): khe quá hẹp, tiến trình kia đang ngủ trong busy handler. Đã sửa bằng cách cho `evaluate_policy` chậm 20 ms **trong tiến trình con** — không thêm cửa hậu nào vào mã chạy thật.

## Chỗ khác hợp đồng — cần Astra xét để sửa lại hợp đồng

1. **`extract` cần đúng một nguồn** (hợp đồng ghi ≥ 1). Block id của hai tài liệu trùng nhau (`b1`, `b2`…) nên model và bước ground sẽ nhầm nguồn. Nhiều nguồn chỉ dành cho `draft`.
2. **`draft` dùng khung prompt tối thiểu `draft-skeleton-0`** (hợp đồng chưa định nghĩa prompt soạn thảo). Chỉ để khoá hình dạng payload; chưa đánh giá, chưa nối model. Payload không chứa document id hay tên file.
3. **"Đã xoá" là cột `purged_at_ms`, không phải trạng thái.** Hình vẽ mục 6 có trạng thái `purged`, nhưng lời văn yêu cầu *giữ trạng thái cuối*; làm thành trạng thái thì mất `completed`/`failed`.
4. **`revisions.policy` = băm mã nguồn `policy_gate.py` + `model_catalog.py` lúc import** (quyết định 5 của mục 14). Không thể thêm hằng số vào file của Astra trong gói này, và băm thì không phụ thuộc người sửa có nhớ tăng số hay không.
5. **Model cloud thiếu `endpoint` hoặc `pricing` → `POLICY_DENIED` (`TARGET_UNVERIFIED`)** ngay lúc chuẩn bị. Hợp đồng chỉ ghi "bắt buộc", chưa ghi mã.
6. **Hash bản ghi.** Ngoài `payload_sha256`, bản ghi (nguồn, nhãn, revision) cũng có `record_sha256`; sửa tay một byte ở đó cũng ra `PAYLOAD_INTEGRITY`. Chỉ bắt được hỏng hoặc sửa vụng: ai sửa được DB thì cũng sửa được hash.
7. **Revision `catalogue` băm toàn bộ danh mục**, nên thêm một model *không liên quan* cũng làm snapshot chết. Thận trọng hơn cần thiết; đổi thành chỉ băm entry được chọn thì đỡ phiền nhưng phải chốt.
8. **`AlreadyClaimed.code` là `None`**: không phải lỗi công khai; tầng HTTP trả trạng thái hiện có (PSC-01 mục 4).
9. Mỗi thao tác đặt `PRAGMA busy_timeout=5000` trên kết nối caller đưa vào, và từ chối kết nối đang có transaction mở (`RuntimeError`).

Các quyết định còn mở ở mục 14 đang dùng giá trị đề xuất: `unknown` trên `internal`; TTL 15/60 phút; chờ khoá 5 giây; `PAYLOAD_INTEGRITY` → `STALE_REQUEST`, không khoá cloud.

## "Full stack" dừng ở đâu

Anh yêu cầu làm trọn, nhưng issue #31 cấm sửa service/web/DB hiện có, và grant (#32) chưa tồn tại. Vì vậy **chưa có**: màn hình xem trước và nút xác nhận gửi, route HTTP hay tool MCP gọi module này, grant, ledger, adapter, rate card. Module chưa được code nào của ứng dụng gọi tới; UI đang chạy trên Data1000 không thay đổi hành vi. Cloud vẫn **không** gọi được.

## Việc tiếp theo và điểm dừng

Astra review PR; anh Khang merge. Sau khi merge vào `main` (kiểm `git merge-base --is-ancestor`), GRANT-01 (#32) chờ Astra chốt schema grant theo PSC-01 rồi mới tạo nhánh `claude/grant-store` từ `main` mới. **Dừng tại PR này.**
