# Hợp đồng snapshot bất biến cho gateway provider — SNAP-01

> **Bản nháp buổi 1 (11/09/2026).** Buổi 2 bổ sung ví dụ synthetic, bảng ca bị từ chối, danh sách test và `docs/handoffs/SNAP-01-result.md`, rồi mới mở PR. Chưa có dòng mã runtime nào; mọi chữ ký hàm dưới đây là **đề xuất** để Astra review.

Issue giao việc: #30. Base: `main` `839afe9` (sau PR #36; issue ghi `68765bd` vì viết trước PR #35, #36 — hai PR này chỉ đổi tài liệu và bộ chấm kế hoạch, không đụng `service.py`, `policy_gate.py`, schema DB). Khung trên: [PSC-01](PROVIDER_SECURITY_CONTRACT.md) mục 2, 4, 5.

## 1. Snapshot để làm gì, và không làm gì

Snapshot là **bản chụp đóng băng của đúng thứ sẽ gửi đi**, cùng mọi điều kiện đã dùng để quyết định được phép chuẩn bị. Nó trả lời một câu: *"Thứ người dùng xác nhận có còn đúng là thứ sắp gửi không, và các điều kiện lúc đó có còn nguyên không?"*

Snapshot **không** phải quyền gửi. Nó không chứa token, không chứa `approved`, không giữ tiền. Quyền là việc của grant (#32), tiền là việc của ledger (chưa có issue). Một snapshot hợp lệ, còn hạn, chưa bị đổi vẫn **không đủ** để gọi mạng.

## 2. Hiện trạng trong mã — điều thiết kế phải dựa vào

Đọc tại `839afe9`, không phải suy từ tài liệu:

| Sự thật | Ở đâu | Hệ quả cho snapshot |
|---|---|---|
| `documents.id` = SHA-256 của bytes gốc | `Service.ingest` | Tài liệu tự định danh theo nội dung. Nhập lại cùng file trả về id cũ, không parse lại |
| `documents.blocks` chỉ được ghi một lần, lúc nhập | `Service.ingest`; không có `UPDATE ... blocks` nào | Hiện nay block **không đổi được**. Snapshot vẫn băm lại block, vì OCR/parse lại sau này sẽ phá giả định này |
| `documents.classification` chỉ ghi lúc nhập; nhập trùng giữ nhãn cũ; tài liệu cũ mặc định `unknown` | `Service.ingest`, migration PR #29 | Hiện chưa có đường **đổi nhãn**. Khi có, bắt buộc phải làm snapshot cũ mất hiệu lực (mục 6) |
| "Phiên bản" là số thứ tự của bảng `versions` (phiếu trích xuất/sửa tay), bắt đầu từ 1 | `Service.save` | Tài liệu chưa có phiếu nào có phiên bản hiện hành = **0** |
| `Service.save(expected_version=...)` ném `Conflict` nếu phiên bản đã đổi | `Service.save` | Đây là hàng rào thứ hai khi **lưu** kết quả. Snapshot thêm hàng rào **trước khi gửi**, để không tốn tiền cho kết quả chắc chắn bị từ chối |
| `Service.lock` là `threading.RLock` **trong một tiến trình** | `Service.__init__` | Không đủ: `mcp_server.main()` tạo `Service` riêng trên cùng `state.sqlite3` từ tiến trình khác. Mọi phép kiểm-rồi-chuyển-trạng-thái của snapshot phải nằm trong `BEGIN IMMEDIATE` của SQLite |
| Payload gửi model chỉ gồm `id` + `text` của block; `location` không gửi | `model.build_messages` | Snapshot băm cả `location` để phát hiện parse lại, nhưng payload chỉ chứa thứ thật sự gửi |
| `evaluate_policy` là hàm thuần, 4 kết quả, không có kết quả "được gửi" | `policy_gate.py` | Snapshot gọi lại nó ở **cả** lúc chuẩn bị và lúc gửi, với nhãn đọc lại từ DB |

## 3. Schema đóng

Quy tắc chung (theo PSC-01 mục 5): từ chối trường lạ và trường thiếu; `bool` phải là `bool` thật; số nguyên không nhận `bool`; **không có số thực** ở bất cứ đâu trong snapshot (mục 4 giải thích); chuỗi có giới hạn độ dài; mảng có giới hạn phần tử.

### 3.1. `PrepareRequest` — thứ caller được gửi

```text
PrepareRequest
  operation      "extract" | "draft"
  model_id       str, 1..128 ký tự trước strip
  sources        list[SourceSelection], 0..20; extract cần >= 1
  instruction    str | null, <= 4.000 ký tự — chỉ draft; extract phải là null
  facts          list[str], <= 30 mục, mỗi mục <= 2.000 ký tự — chỉ draft; extract phải là []

SourceSelection
  document_id       64 ký tự hex thường
  block_ids         list[str], 1..20, không trùng, giữ thứ tự caller
  expected_version  int >= 0 — phiên bản caller đang nhìn thấy (0 = chưa có phiếu)
```

Tổng số block trên mọi nguồn ≤ 20 (PSC-01). **Không có** trường classification, credential, endpoint, giá, `approved`, payload hay settings trong `PrepareRequest`. Có thì từ chối cả yêu cầu (`INVALID_REQUEST`), không lặng lẽ bỏ trường.

Nhãn của phần instruction/facts với `draft` **không** nằm trong request. Backend nhận nó riêng từ form UI local (có CSRF), qua đối số `prompt_classification`; MCP không có đường nào đặt nó. Với `extract`, mọi phần ngoài block đều là hằng số trong mã nên backend tự gán `public`.

### 3.2. `ProviderSnapshot` — bản ghi chỉ backend được ghi

```text
ProviderSnapshot
  schema                  "aimarx.snapshot/1"
  snapshot_id             32 ký tự hex, secrets.token_hex(16) — định danh, KHÔNG phải quyền
  operation               "extract" | "draft"
  state                   xem mục 5
  created_at_ms           int, UTC epoch ms
  expires_at_ms           int, created_at_ms < expires_at_ms <= created_at_ms + TTL_MAX
  sources                 list[SourceRef]
  prompt_classification   nhãn (mục 3.3)
  effective_classification  nhãn hạn chế nhất trên prompt + mọi nguồn
  policy_decision         "PREPARE_LOCAL" | "CONSENT_REQUIRED"
  target                  {model_id, provider, model, data_destination}
  revisions               Revisions
  payload                 Payload
  payload_sha256          64 hex = sha256(canonical_json(payload))
  payload_size            int, số byte của canonical_json(payload), <= 32.768
  end_reason              null | mã lý do (mục 7) — chỉ có khi state kết thúc

SourceRef
  document_id       64 hex
  document_version  int >= 0, đọc từ DB (không lấy từ caller)
  classification    nhãn đọc từ documents.classification tại cùng transaction
  block_ids         list[str], như caller chọn
  blocks_sha256     sha256(canonical_json([{id, location, text} của đúng các block đã chọn, theo thứ tự]))

Revisions   — mỗi giá trị là str 1..128 ký tự, do backend cấp từ mã/cấu hình
  prompt      model.PROMPT_VERSION (hiện "2026-09-11.v5")
  schema      sha256(canonical_json(model.generation_schema()))
  catalogue   sha256(canonical_json(danh mục đã chuẩn hoá bởi list_public_models(enabled_only=False)))
  policy      hằng số mới trong policy_gate, ví dụ "PG-01.1"
  adapter     phiên bản adapter sẽ dựng HTTP body từ payload
  endpoint    str | null — bắt buộc khác null khi data_destination = "cloud"
  pricing     str | null — bắt buộc khác null khi data_destination = "cloud"

Payload
  messages         list[{role: "system"|"user", content: str}], 1..4
  response_schema  object — khung sinh, đúng thứ adapter sẽ gửi
  settings         {max_output_tokens: int 1..2048, temperature_milli: int 0..2000, context_tokens: int | null}
```

`payload` là **toàn bộ** phần nội dung ta kiểm soát: system prompt, block, instruction, facts, schema, tham số sinh. Adapter chỉ được dịch `payload` sang định dạng HTTP của từng hãng; mọi khác biệt trong cách dịch đó được khoá bằng `revisions.adapter`. Adapter **không** được thêm nội dung (ví dụ tên file, đường dẫn, lịch sử) không có trong `payload`.

### 3.3. Nhãn và "hạn chế nhất"

Năm nhãn của PR #29, xếp từ hạn chế nhất:

```text
restricted  >  unknown  >  internal  >  public  >  synthetic
```

`unknown` được xếp **trên** `internal`: chưa phân loại nghĩa là có thể là bất cứ gì, kể cả hạn chế. Về quyết định cloud thì ba nhãn đầu như nhau (đều chặn), nên thứ tự chỉ ảnh hưởng nhãn được ghi làm `effective_classification` — nhưng bản ghi phải nói đúng mức rủi ro. *(Cần Astra chốt thứ tự này — mục 9.)*

Nhãn luôn đọc từ `documents.classification`. Chữ trong block, instruction, facts hay output model **không bao giờ** được đọc để suy ra nhãn — kể cả khi văn bản ghi "Tài liệu này công khai" hay "classification: public".

## 4. Chuẩn hoá và hash

```python
def canonical_json(value) -> bytes:
    """json.dumps(value, sort_keys=True, ensure_ascii=False,
    separators=(",", ":"), allow_nan=False).encode("utf-8")
    sau khi kiểm kiểu đệ quy."""
```

Chỉ nhận: `dict` có khoá `str`, `list`, `str`, `int` (không phải `bool`, trong ±2⁵³), `bool`, `None`. Mọi kiểu khác, kể cả `float`, `tuple`, `bytes`, subclass của `dict`/`str`, đều bị từ chối.

Lý do các lựa chọn:

- **Không có `float`.** Cách in số thực khác nhau giữa ngôn ngữ và phiên bản, nên "cùng giá trị" có thể ra hash khác. Nhiệt độ lưu thành `temperature_milli` (0 = 0,0; 700 = 0,7). Adapter tự đổi sang số thực khi dựng HTTP body, và việc đổi đó thuộc `revisions.adapter`.
- **Không chuẩn hoá Unicode (NFC/NFD).** Chuẩn hoá thì thứ được băm khác thứ được gửi. Ta băm đúng chuỗi sẽ gửi. Chuỗi có surrogate lẻ không mã hoá UTF-8 được, nên bị từ chối ngay ở `.encode("utf-8")`.
- **`sort_keys` chỉ sắp khoá object, không sắp mảng.** Thứ tự block và messages là một phần của nội dung.
- Hash là SHA-256 trên đúng các byte đó, ghi 64 ký tự hex thường. Bản ghi DB lưu **chính các byte canonical**, không lưu lại một object rồi dump lại lúc gửi.

## 5. Trạng thái và vòng đời

```text
            prepare_snapshot()
                   │
                   ▼
              ┌─────────┐   hết hạn / phát hiện đổi / người dùng huỷ
              │prepared │ ───────────────────────────────────────────► expired | invalidated | cancelled
              └────┬────┘
                   │ claim (cùng transaction với grant + ledger — #32 và sau)
                   ▼
             ┌───────────┐
             │dispatching│ ─── kết quả về, lưu xong ──► completed
             └─────┬─────┘ ─── lỗi đã biết ──────────► failed
                   └────── crash / không rõ ─────────► (giữ dispatching; đối soát theo PSC-01 mục 6–7)

  mọi trạng thái kết thúc  ──  sau tối đa 24 giờ  ──►  purged (xoá payload, giữ metadata)
```

- Chỉ `prepared` chuyển được sang `dispatching`, và chỉ **một lần**: `UPDATE ... SET state='dispatching' WHERE snapshot_id=? AND state='prepared'`, kiểm `rowcount == 1`. Hai lệnh execute đồng thời thì một lệnh thắng, lệnh kia thấy `rowcount == 0` và nhận trạng thái hiện có (PSC-01 mục 4).
- Trạng thái kết thúc (`expired`, `invalidated`, `cancelled`, `completed`, `failed`) **không bao giờ** quay lại `prepared`. Không có hàm "làm mới" snapshot; đổi gì thì chuẩn bị snapshot mới.
- `dispatching` không tự hết hạn: request có thể đã tính tiền. Restart thấy `dispatching` thì coi là **kết quả không rõ**, không tự gửi lại.
- `purged` chỉ xoá `payload` (nội dung có thể nhạy cảm), giữ hash, revisions, nguồn, trạng thái cuối để đối soát. Đây là xoá logic, không hứa secure erase (PSC-01 mục 4).

TTL đề xuất: `prepared` sống **15 phút** (đủ để đọc bản xem trước rồi bấm xác nhận; grant sau đó còn 5 phút riêng theo PSC-01). `TTL_MAX` = 60 phút. Đồng hồ là **UTC wall clock truyền vào hàm** (`now_ms`), không đọc đồng hồ bên trong — để test bằng đồng hồ giả và để hết hạn còn đúng qua restart. Vì đồng hồ hệ thống có thể bị lùi, thêm điều kiện `now_ms >= created_at_ms`; lùi quá thì coi như hết hạn chứ không coi là còn trẻ.

## 6. Trình tự transaction

Nguyên tắc: **không gọi mạng, không gọi model, không đọc file lớn trong transaction**; mọi phép kiểm-rồi-ghi nằm trọn trong một `BEGIN IMMEDIATE` để tiến trình MCP hay tab khác không chen giữa được.

### 6.1. Chuẩn bị — `prepare_snapshot`

1. Ngoài transaction: kiểm `PrepareRequest` theo schema đóng. Sai → `INVALID_REQUEST`, không đụng DB.
2. `BEGIN IMMEDIATE`.
3. Với từng nguồn: đọc `documents` (blocks, warnings, classification) và phiên bản mới nhất trong `versions`. Tài liệu không có → `INVALID_REQUEST` (không nói tài liệu có tồn tại hay không). Cần OCR (`requires_ocr`) → `INVALID_REQUEST`. `expected_version` khác phiên bản hiện hành → `STALE_REQUEST`. Block id không có trong tài liệu → `INVALID_REQUEST`.
4. Dựng `payload` trong bộ nhớ (hàm thuần; với `extract` dùng lại `build_messages` và `generation_schema` hiện có). Tính `blocks_sha256`, `payload_sha256`, `effective_classification`. Payload > 32 KiB → `INVALID_REQUEST`.
5. Gọi `evaluate_policy` với nhãn **vừa đọc ở bước 3**, catalogue và `cloud_enabled` từ cấu hình backend. `INVALID_REQUEST`/`POLICY_DENIED` → trả lỗi, **không** ghi snapshot (không lưu nội dung chẳng để làm gì).
6. `INSERT` snapshot với `state='prepared'`. `COMMIT`.
7. Trả về bản xem trước: `snapshot_id`, nội dung payload (để UI hiển thị **đúng thứ sẽ gửi**), target, nhãn, hạn. Không trả gì cho phép tự dựng lại payload để gửi.

Bước 3–6 chỉ là đọc SQLite và tính toán trong bộ nhớ, nên giữ `BEGIN IMMEDIATE` suốt đoạn này chỉ tốn vài mili giây.

### 6.2. Trước khi gửi — `claim_for_dispatch`

Caller chỉ đưa `snapshot_id` (và sau này `grant_token`). **Payload không bao giờ được nhận lại từ caller**; adapter chỉ gửi payload đọc từ bản ghi.

1. `BEGIN IMMEDIATE`.
2. Đọc snapshot. Không có → `INVALID_REQUEST`. `state != 'prepared'` → trả trạng thái hiện có, không gửi.
3. Hết hạn (`now_ms >= expires_at_ms` hoặc `now_ms < created_at_ms`) → chuyển `expired`, `CONSENT_EXPIRED`.
4. Băm lại byte payload đã lưu, so với `payload_sha256`. Lệch → chuyển `invalidated` (lý do `PAYLOAD_INTEGRITY`), `STALE_REQUEST`.
5. Với từng nguồn, đọc lại DB: tài liệu còn; `classification` bằng nhãn đã chụp; phiên bản mới nhất bằng `document_version`; `blocks_sha256` tính lại bằng giá trị đã chụp. Lệch bất kỳ → `invalidated`, `STALE_REQUEST`.
6. Lấy revisions hiện hành từ mã/cấu hình backend, so **từng trường** với snapshot. Lệch → `invalidated`, `STALE_REQUEST`.
7. Gọi lại `evaluate_policy` với nhãn và cấu hình hiện hành. Kết quả phải **đúng bằng** `policy_decision` đã chụp. Ví dụ cloud vừa bị tắt → giờ ra `POLICY_DENIED` → `invalidated`.
8. *(#32)* Kiểm và tiêu thụ grant. *(ledger, chưa có issue)* Giữ ngân sách. Cả hai **trong cùng transaction này**.
9. `UPDATE ... SET state='dispatching' WHERE snapshot_id=? AND state='prepared'`; `rowcount != 1` → rollback, trả trạng thái hiện có.
10. `COMMIT`. Trả cho adapter một bản sao payload giải mã từ byte đã lưu.
11. **Ngoài transaction:** gọi mạng.
12. Transaction mới: lưu kết quả qua `Service.save(expected_version=document_version)` — hàng rào `Conflict` sẵn có vẫn chạy; chuyển snapshot sang `completed`/`failed`.

Bước 3–7 thất bại thì chuyển trạng thái **rồi `COMMIT`** (không rollback), để lần gọi sau không phải kiểm lại và bản ghi nói rõ vì sao nó chết.

### 6.3. Khi đổi nhãn tài liệu (tính năng tương lai)

Hiện chưa có đường đổi nhãn, nên so bằng giá trị ở bước 5 là đủ. Nhưng so bằng giá trị có lỗ **A→B→A**: nhãn `public` → người dùng đổi `restricted` (ý là *đừng gửi*) → đổi lại `public`; snapshot chụp lúc đầu lại khớp. Vì vậy, **ai làm tính năng đổi nhãn phải làm một trong hai**, trong cùng transaction với lần đổi:

- thêm cột `documents.classification_revision` tăng đơn điệu, và snapshot chụp cả số này; hoặc
- chuyển mọi snapshot `prepared` của tài liệu đó sang `invalidated` (lý do `CLASSIFICATION_CHANGED`).

Đề xuất cách thứ nhất: không bắt tính năng đổi nhãn phải biết tới bảng snapshot. *(Cần chốt — mục 9.)*

## 7. Mã lỗi

Mã công khai **chỉ dùng tập đã có trong PSC-01 mục 5**, không thêm mã mới. Lý do cụ thể đi vào `end_reason` để đối soát, không đưa ra ngoài.

| Lý do nội bộ (`end_reason`) | Mã công khai | Trạng thái snapshot |
|---|---|---|
| sai schema, trường lạ, kiểu sai, vượt giới hạn | `INVALID_REQUEST` | không tạo |
| không có tài liệu / block / snapshot id | `INVALID_REQUEST` | không tạo / không đổi |
| policy từ chối lúc chuẩn bị | `POLICY_DENIED` | không tạo |
| `EXPIRED` | `CONSENT_EXPIRED` | `expired` |
| `VERSION_CHANGED`, `SOURCE_CHANGED`, `CLASSIFICATION_CHANGED`, `REVISION_CHANGED`, `POLICY_CHANGED` | `STALE_REQUEST` | `invalidated` |
| `PAYLOAD_INTEGRITY` (byte trong DB không khớp hash) | `STALE_REQUEST` | `invalidated` |
| `ALREADY_CLAIMED` | không phải lỗi: trả trạng thái hiện có | không đổi |

`PAYLOAD_INTEGRITY` nghĩa là DB bị sửa ngoài ứng dụng hoặc hỏng. PSC-01 chưa có mã riêng cho việc này. *(Cần chốt: gộp vào `STALE_REQUEST` như trên, hay khoá cloud tới khi người dùng kiểm — mục 9.)*

Thông báo lỗi không chứa nội dung block, instruction, payload hay giá trị trường lạ; chỉ mã và `snapshot_id`.

## 8. Chữ ký hàm dự kiến (cho SNAP-02)

Module mới `src/tro_ly_van_ban/provider_snapshot.py`. Không sửa `service.py`, `web.py`, `model.py`, `policy_gate.py` hay bảng hiện có; module tự tạo bảng riêng.

```python
class SnapshotError(ValueError):
    code: str        # mã công khai, mục 7
    reason: str      # end_reason nội bộ

@dataclass(frozen=True)
class TrustedConfig:          # backend dựng từ mã/cấu hình, không bao giờ từ HTTP/MCP
    models: tuple[dict, ...]
    cloud_enabled: bool
    revisions: Mapping[str, str | None]

@dataclass(frozen=True)
class SnapshotView:           # bản chỉ đọc; payload là bytes, mỗi lần .payload() trả object mới
    snapshot_id: str
    state: str
    payload_sha256: str
    payload_bytes: bytes
    ...

def canonical_json(value) -> bytes: ...
def ensure_schema(conn: sqlite3.Connection) -> None: ...
def prepare_snapshot(conn, request: dict, *, config: TrustedConfig,
                     prompt_classification: str, now_ms: int) -> SnapshotView: ...
def claim_for_dispatch(conn, snapshot_id: str, *, config: TrustedConfig,
                       now_ms: int) -> SnapshotView: ...
def finish(conn, snapshot_id: str, *, outcome: str) -> None: ...
def purge(conn, *, now_ms: int) -> int: ...
```

`claim_for_dispatch` ở SNAP-02 chưa có grant/ledger. Nó phải **ghi rõ trong docstring và tên test** rằng việc thắng claim chỉ chứng minh snapshot không bị dùng hai lần — không chứng minh đã được quyền gửi.

*Bảo đảm này mới là thiết kế.* Buổi 2 sẽ tách rõ thứ đã có trong mã hôm nay với thứ chỉ có sau khi SNAP-02 có test.

## 9. Việc cần Astra chốt (sơ bộ)

1. Bảng snapshot đặt **trong `state.sqlite3`** (đề xuất: để bước 5 và 8 của mục 6.2 đọc `documents` và ghi grant/ledger trong **một** transaction) hay file riêng.
2. Thứ tự "hạn chế nhất": `unknown` xếp trên hay dưới `internal`.
3. Cách chống A→B→A khi có tính năng đổi nhãn (mục 6.3).
4. `PAYLOAD_INTEGRITY` gộp `STALE_REQUEST` hay khoá cloud.
5. TTL `prepared` 15 phút và `TTL_MAX` 60 phút.
6. `revisions.policy`: thêm hằng số vào `policy_gate.py` (việc của Astra, người sở hữu file đó) hay để snapshot tự băm mã nguồn policy.

---

*Buổi 2 (chưa làm):* ví dụ synthetic hợp lệ đầy đủ; bảng ca bị từ chối (thiếu nhãn, nội bộ, prompt injection, đổi 1 byte, đổi nguồn/phiên bản/nhãn/model/settings, hết hạn, execute đồng thời); tối thiểu 10 ca test; phân biệt bảo đảm hiện có với thứ chỉ test mới chứng minh; `SNAP-01-result.md`; PR tới `main`.
