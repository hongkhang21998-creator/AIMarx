# Hợp đồng bảo mật provider — PSC-01

> Cập nhật phân công 11/09/2026: Gemini đã được bỏ khỏi phân công phát triển chủ động; các gói phụ do Astra điều phối lại cho Claude hoặc tự xử lý theo từng buổi. Các đề xuất giao fixture cho Gemini bên dưới là lịch sử. Hợp đồng bảo mật và phạm vi provider không thay đổi.

Ngày: 10/09/2026. Trạng thái: **thiết kế đề xuất, chưa triển khai**. Base: `881d1aa9c7280a4c5bf5c0aa6d7ab5bde34f4ad5` (PR #17 đã merge). Astra phụ trách thiết kế và nghiệm thu phần API khó; người dùng duyệt PR. Các giá trị mặc định bên dưới là lựa chọn của dự án, không phải giới hạn do nhà cung cấp công bố.

### Cập nhật triển khai — PG-01

PSC-01 đã được duyệt qua PR #18; nhãn trạng thái đầu tài liệu là lịch sử lúc viết thiết kế. PG-01 bổ sung `policy_gate.evaluate_policy`, **chỉ kiểm điều kiện chuẩn bị**, chưa nối vào runtime/MCP. Các phần grant/snapshot, kiểm phiên bản, ngân sách, khóa và adapter bên dưới vẫn chưa triển khai.

API nội bộ:

```python
evaluate_policy(
    request={"operation": "extract", "model_id": "configured-id"},
    models=trusted_catalogue,
    cloud_enabled=False,
    prompt_classification="unknown",
    source_classifications=("unknown",),
)
```

`request` chỉ nhận hai khóa operation/model_id, operation là extract hoặc draft, ID không rỗng và tối đa 128 ký tự trước strip. Không có nội dung prompt hoặc quyền trong request này; đây chưa phải toàn bộ PrepareRequest ở mục 5. `models` dùng schema bốn trường đầu vào của G-MCP-01, tối đa 100 mục. Tất cả mục, kể cả disabled, phải hợp lệ. Model ID phân biệt hoa thường sau strip.

Các keyword còn lại chỉ backend cấp từ cấu hình/kho local tin cậy, không ánh xạ trực tiếp từ HTTP/MCP hoặc output SLM. `source_classifications` là tuple tối đa 20 nhãn, một nhãn cho mỗi block đã chọn; thiếu nhãn của một block phải thay bằng unknown, không bỏ block khỏi danh sách. extract cần ít nhất một block; draft cho phép không có nguồn nhưng vẫn phải phân loại prompt. `prompt_classification` bao phủ mọi phần còn lại của payload (instruction/dữ kiện/template/schema), lấy nhãn hạn chế nhất nếu có nhiều thành phần. Hàm thuần dữ liệu không thể chứng minh backend đã lấy đúng nhãn hay bao phủ đủ payload; tích hợp snapshot và kiểm quyền là điều kiện bắt buộc sau này.

Kết quả là enum `PolicyDecision`, phải so sánh từng giá trị, không dùng làm boolean (hàm bool sẽ báo TypeError):

| Giá trị | Ý nghĩa |
|---|---|
| INVALID_REQUEST | Sai schema/kiểu/giới hạn hoặc catalogue lỗi; ưu tiên trước các kết luận chính sách |
| POLICY_DENIED | Model không có/bị tắt, cloud chưa bật, hoặc có nhãn internal/restricted/unknown trong yêu cầu cloud |
| PREPARE_LOCAL | Đủ điều kiện phân loại để chuẩn bị local; chưa xác minh endpoint hay quyền đọc tài liệu |
| CONSENT_REQUIRED | Cloud bật và tất cả thành phần public/synthetic; vẫn phải xin xác nhận người dùng và qua toàn bộ kiểm tra thực thi |

Không có kết quả cho phép gọi cloud ngay. PG-01 không cấp/kiểm grant hoặc giữ tiền, không đọc env/file/DB, không gọi mạng/log, không sửa input. Label sai hoa thường/khoảng trắng bị từ chối, không tự nâng thành public. Ba tool MCP hiện có chưa dùng module này; test đơn vị không phải bằng chứng đã chặn egress của toàn ứng dụng. Buổi tiếp theo đề xuất chốt schema snapshot bất biến và phép kiểm thay đổi nguồn; GrantStore/BudgetLedger vẫn làm từng gói sau đó.

## 1. Phạm vi và hiện trạng

Ứng dụng cá nhân xử lý và tạo sinh văn bản. `model_catalog.py` chỉ kiểm tra metadata; `enabled` không xác nhận API key hợp lệ, model đang hoạt động, hay quyền gửi dữ liệu. `data_destination` là nhãn suy từ provider, không chứng minh kết nối thực tế an toàn.

Hiện `model.py` gọi Ollama loopback; `mcp_server.py` chỉ có `list_documents`, `read_document`, `get_evidence`. Hợp đồng này dành cho đường gọi provider mới, không tuyên bố các bảo vệ đã có trong mã hiện tại. Các tool đọc hiện tại cũng có thể đưa nội dung cho MCP client: người dùng phải tin cậy client và chính sách cloud của client. Gateway này không kiểm soát được việc client tự gửi nội dung đã đọc sang dịch vụ khác.

Phiên bản đầu: text, một lần sinh, không streaming, không tool tự gọi tiếp, không tự đổi provider, không tự tạo dataset SLM. Swarm chỉ được gọi cùng cổng kiểm soát này; không giữ khóa hoặc tự duyệt. Thử cloud đầu tiên chỉ dùng dữ liệu tổng hợp do người dùng xác nhận.

## 2. Ranh giới tin cậy và kiến trúc

```text
MCP client / UI → yêu cầu chuẩn bị → PolicyGate → bản xem trước bất biến
Người dùng tại UI local → xác nhận bản xem trước → GrantStore
Yêu cầu thực thi → kiểm grant + phiên bản → giữ ngân sách → ProviderAdapter
ProviderAdapter → kiểm output/nguồn → kết quả ứng viên → luồng phiên bản và duyệt hiện có
                               ↘ đối soát phí + nhật ký metadata local
```

Tách `PolicyGate`, `GrantStore`, `BudgetLedger`, `SecretResolver`, `ProviderAdapter`. Chỉ adapter được lấy khóa và mở kết nối, sau khi mọi kiểm tra qua. Không gọi mạng trong transaction DB hoặc trong lock toàn dịch vụ. Snapshot trước inference; khi lưu lại kiểm phiên bản lần nữa. Nếu phiên bản đã đổi: báo conflict, không ghi đè, chi phí đã phát sinh vẫn được ghi nhận.

Model, tài liệu và tham số MCP đều không đáng tin để cấp quyền. Không nhận `approved=true`, API key, URL đích, header, giá hoặc nhãn phân loại do agent tự khai làm bằng chứng cho phép gửi. MCP stdio nhận danh tính client từ cấu hình launcher do người dùng kiểm soát, không từ một trường `client_id` tùy ý trong tool arguments. Không coi tên client là xác thực. Multi-user hoặc MCP qua HTTP phải có thiết kế xác thực riêng trước khi bật.

## 3. API key và endpoint

| Thành phần | Hợp đồng bắt buộc |
|---|---|
| Lưu khóa | Dùng kho bí mật hệ điều hành: Windows Credential Manager; Linux Secret Service. Nếu không có kho này, chỉ cho phép biến môi trường cấp riêng cho tiến trình backend ở chế độ phát triển. Không tự rơi về file plaintext |
| Tham chiếu | Cấu hình riêng backend dùng `credential_ref`; metadata public vẫn đúng năm trường PR #17. Không trả credential_ref hoặc khóa qua MCP/UI/log |
| Sử dụng | Lấy khóa ngay trước gửi, chỉ gắn Authorization cho endpoint tương ứng; không gửi vào prompt, query string hoặc command line. Không kế thừa khóa vào worker/Swarm |
| Thiếu/sai khóa | Thiếu khóa chặn trước mạng; 401/403 trả lỗi cố định. Không tự thử khóa/provider khác |
| Thu hồi | Ngừng nhận request mới, tăng revision cấu hình để vô hiệu grant chưa dùng; thu hồi khóa tại provider. Request đã gửi có thể vẫn tính phí. Không hứa xóa an toàn chuỗi khỏi bộ nhớ Python |
| Endpoint cloud | Allowlist chính xác scheme/host/port/path, HTTPS và kiểm chứng certificate; không nhận base_url tùy ý. Tắt redirect và proxy từ env (`trust_env=False`). Adapter DeepSeek và GLM có cấu hình tách biệt |
| Ollama local | Chỉ loopback đã duyệt, không đính kèm khóa cloud. Đổi sang host LAN/remote phải qua thiết kế lại; không vẫn gắn nhãn local |

Đích dự kiến theo tài liệu chính thức đã đọc: DeepSeek `https://api.deepseek.com/chat/completions`; GLM qua **Z.AI general API** `https://api.z.ai/api/paas/v4/chat/completions`. `glm` là model family; không giả định khóa Z.AI dùng được cho mọi nền tảng GLM. Nếu người dùng có tài khoản ở endpoint khác, phải chốt riêng trước khi triển khai. Coding Plan không được dùng thay general API theo suy đoán.

**Cập nhật 11/09/2026 — `qwen` và `kimi`:** danh mục model nhận thêm hai provider này, và cả hai đi qua đúng đường cloud của `policy_gate` (có test khoá lại). Endpoint của chúng **chưa vào allowlist**, chưa có adapter, và không request nào được gửi. Ứng viên theo tài liệu chính thức: Qwen qua Alibaba Model Studio, endpoint theo vùng và gắn workspace, khoá chỉ dùng được ở vùng tạo ra nó; Kimi qua `https://api.moonshot.ai/v1`. Điều khoản dữ liệu của cả bốn hãng khác nhau đáng kể — Kimi dùng nội dung để tối ưu model và không nêu cách từ chối, DeepSeek lưu tại Trung Quốc. Chi tiết và nguồn: `docs/NGHIEN_CUU_PROVIDER_2026-09.md`. Máy chủ MCP của ứng dụng trả nguyên nội dung văn bản, nên **không được đăng ký vào trợ lý cloud nào**: đường đó không đi qua `policy_gate`.

Khi kết nối cloud, kiểm IP đã resolve không thuộc loopback/private/link-local/reserved và bảo đảm kết nối sử dụng chính tập IP đã kiểm (không resolve lại giữa kiểm và dùng). Giữ TLS hostname/SNI của host allowlist. Nếu lớp transport không bảo đảm được, chặn cloud đến khi hoàn thiện; không chỉ kiểm DNS rồi để HTTP client resolve lại. Có test redirect, IPv4/IPv6 và DNS đổi đáp án. Không nhận URL/file đính kèm từ model để tự tải.

Mọi request/response debug HTTP phải tắt trên đường provider. Không log exception thô/headers/body; chuyển lỗi thành mã hữu hạn. Dùng khóa riêng cho ứng dụng, không tái sử dụng token xác thực MCP làm khóa provider.

## 4. Quyền gửi nội dung ra cloud

Phân loại do người dùng đặt ở local, mặc định `unknown`: `synthetic`, `public`, `internal`, `restricted`, `unknown`. Đây là nhãn chính sách ứng dụng, không phải kết luận pháp lý. Chính sách v1 chỉ nhận `synthetic`/`public` và vẫn cần xác nhận từng yêu cầu. `internal`, `restricted`, `unknown` chặn cloud; thao tác xác nhận gửi không vượt qua chặn này. Khi ghép nguồn, áp dụng nhãn hạn chế nhất. Văn bản mới không có nguồn vẫn phải phân loại prompt và dữ kiện người dùng nhập; thiếu nguồn không có nghĩa công khai.

Quyền bật provider, quyền đọc tài liệu, quyền gửi cloud, quyền duyệt dự thảo và quyền xuất dataset là các quyền riêng. Duyệt văn bản không cấp quyền gửi cloud. Che tên tự động không tự nâng tài liệu lên `public`.

Luồng v1:

1. Backend lấy đúng block đã chọn và phiên bản từ kho local; không lấy toàn bộ hồ sơ/history. Mọi yêu cầu tạo mới cũng đi qua bước này với prompt snapshot.
2. Dựng payload đầy đủ (system prompt, nguồn, schema, dữ kiện), chuẩn hóa ổn định rồi tính SHA-256. Bản xem trước hiển thị chính nội dung sẽ gửi, provider/đích/model, mục đích, số lần thử tối đa và trần phí toàn yêu cầu. Không đính kèm tên file/path nếu không cần. Template/model/settings cũng bị ràng buộc vào snapshot.
3. Người dùng xác nhận tại UI local. UI cần phiên đăng nhập local riêng, kiểm Host/Origin và CSRF, không nhận GET đổi trạng thái, không cấp chức năng xác nhận qua tool MCP. Việc bảo vệ UI là điều kiện trước khi bật cloud, vì localhost tự nó chưa chứng minh là người dùng.
4. Backend tạo grant ngẫu nhiên >=256 bit, lưu hash của token, ràng buộc principal/session đã cấu hình, request_id, payload_hash, source versions, provider/model/endpoint revision, policy revision, pricing revision, token cap, trần phí và hết hạn sau 5 phút.
5. Thực thi lấy payload từ snapshot đã lưu; không nhận payload thay thế. Kiểm lại tất cả revision và grant rồi tiêu thụ nguyên tử cùng bước giữ ngân sách. Bản sửa nội dung hoặc đổi provider cần xem trước và xác nhận mới.

Grant cho một logical request, chỉ khởi chạy một lần; retry được phép nằm trong request đó. Hai lệnh thực thi đồng thời chỉ một lệnh được gửi; lệnh còn lại trả trạng thái request hiện có. Thu hồi hoặc hết hạn chặn cả attempt chưa gửi tiếp theo. Không đưa grant vào prompt/log; token chỉ là handle và phải kiểm đúng principal. Nội dung chỉ dẫn trong nguồn không thể cấp grant.

Snapshot tạm có nội dung được lưu local với quyền truy cập như dữ liệu ứng dụng, không trong audit log; xóa sau khi request kết thúc/hết hạn (tối đa 24 giờ cho bản tạm). Output cần lưu phải đi vào kho phiên bản hiện có. Đây là xóa logic, không hứa secure erase/không còn trong backup.

## 5. Hợp đồng dữ liệu nội bộ để triển khai sau

Các cấu trúc dưới đây là đề xuất, chưa đăng ký MCP tool. Schema đóng: từ chối trường lạ, bool thật, số nguyên không nhận bool, không NaN/Infinity, có giới hạn chuỗi/mảng.

| Cấu trúc | Trường cốt lõi và nguồn tin cậy |
|---|---|
| PrepareRequest | `operation` là `extract` hoặc `draft`, `model_id`, source refs gồm document_id/block_ids/expected_version; draft mới thêm instruction/dữ kiện. Không nhận credential, endpoint hoặc giá |
| PreparedRequest | ID do backend sinh, payload hash và snapshot local, source versions, revisions, expiry, classification kiểm từ kho local, token/cost bound; chỉ backend được ghi |
| ExecuteRequest | `request_id`, `grant_token`; principal do transport cung cấp; không nhận body mới |
| AttemptRecord | request_id, attempt_no, state, reserved amount, currency, pricing_revision; ghi trước network |
| ProviderResult | request_id, status, output hoặc error_code, usage có thể null, billed estimate/status; không trả raw HTTP response |

Giới hạn đề xuất: tối đa 20 source blocks, payload UTF-8 <=32 KiB, output cấu hình <=2.048 token và response body <=1 MiB. Các trần này độc lập với giới hạn trích xuất local 5.000 ký tự hiện có. Model chỉ bật khi adapter xác minh được giới hạn context/output, cách đếm token và mọi thành phần bị tính phí. Reasoning không thể giới hạn đáng tin thì không bật model đó trong v1. Không gọi model để ước lượng phí.

Mã lỗi ổn định: `INVALID_REQUEST`, `POLICY_DENIED`, `CONSENT_REQUIRED`, `CONSENT_EXPIRED`, `STALE_REQUEST`, `CREDENTIAL_UNAVAILABLE`, `AUTH_FAILED`, `PROVIDER_BALANCE`, `RATE_LIMITED`, `TIMEOUT`, `OUTCOME_UNKNOWN`, `PROVIDER_ERROR`, `INVALID_OUTPUT`, `BUDGET_EXCEEDED`, `PRICING_UNVERIFIED`, `LEDGER_UNAVAILABLE`. Thông báo tiếng Việt ánh xạ cố định; chỉ thêm request_id do ứng dụng sinh.

## 6. Timeout, retry và kết quả không rõ

Mặc định đề xuất: pool 2s, connect 5s, write 10s, read 30s; **deadline toàn logical request 60s**, gồm xếp hàng, backoff và mọi attempt. HTTPX read timeout đo chờ dữ liệu, không thay thế deadline tổng. Dùng đồng hồ monotonic; hủy network task và không cho attempt mới sau deadline. Một cloud request đang chạy cho toàn ứng dụng ở v1; giữ ledger nguyên tử vẫn bắt buộc để chống nhiều tiến trình/tab.

| Tình huống | Quyết định v1 |
|---|---|
| Pool/connect timeout, xác định chưa gửi HTTP body | Có thể thử lại một lần |
| HTTP 429 | Tối đa một retry; chỉ khi adapter xác nhận response từ chối này chưa tính phí; nếu chưa có bằng chứng thì dừng |
| 400/401/402/403/404/422 | Không retry; 402 là thiếu số dư, không tự nạp tiền |
| 5xx, read/write timeout, đứt kết nối sau khi có thể đã gửi | Không tự retry; `OUTCOME_UNKNOWN`, giữ dự trù |
| 2xx nhưng sai schema/nguồn hoặc output bị cắt | Không tự sửa bằng lần gọi thứ hai; ghi phí thực tế nếu có, trả INVALID_OUTPUT |
| Người dùng hủy | Ngừng attempt tiếp theo, đóng kết nối; nếu đã dispatch thì vẫn giữ khoản có thể bị tính |

Tối đa 2 attempts/logical request. Backoff trước lần hai: ngẫu nhiên 0,5–1,5s; Retry-After hợp lệ phải được tôn trọng (seconds hoặc HTTP date), nếu vượt thời gian còn lại thì dừng, không rút ngắn để gửi sớm. Kiểm lại grant và ngân sách trước retry. Tắt retry ngầm ở SDK/transport và không retry vòng ngoài Swarm.

Không coi request_id/idempotency key tự đặt là bảo đảm provider khử trùng lặp. Người dùng muốn thử lại sau OUTCOME_UNKNOWN phải tạo yêu cầu/grant mới và thấy cảnh báo có thể bị tính phí cả hai. Response đến muộn chỉ được đối soát đúng attempt một lần, không hồi sinh job đã hủy hoặc tự lưu dự thảo.

## 7. Ngân sách và cách hạch toán

Cloud mặc định tắt, ngân sách mặc định **0**. Hồ sơ thử nghiệm đề xuất để người dùng tự bật sau: 0,02 USD/logical request; 0,20 USD/ngày; 2 USD/tháng. Đây không phải giá provider hoặc quyền chi tiền đã được cấp bởi PR thiết kế. Ngày/tháng theo Asia/Ho_Chi_Minh; lưu timestamp UTC. V1 chỉ hỗ trợ rate card USD; currency khác phải có thiết kế đối soát trước.

Không hardcode giá hiện hành trong source. Rate card cấu hình riêng backend phải có provider/model/endpoint, các đơn giá theo loại token, currency, nguồn chính thức, revision, verified_at và expires_at tối đa 7 ngày. Giá thiếu/hết hạn, model đổi alias không xác minh hoặc không xác định được trần phí: chặn. Không coi gói Coding Plan hoặc số dư tài khoản là ngân sách ứng dụng.

Với adapter text có input/output billing đã xác minh:

`R_attempt = ceil_money(I_bound * P_input_max / 1e6 + O_cap * P_output_max / 1e6 + other_billable_upper_bound)`.

`I_bound` phải bao gồm message framing/system/schema và mọi overhead; chỉ chấp nhận tokenizer/bound đã xác minh cho model, không dùng chars/4 như một trần bảo đảm. Không dựa vào cache hit để giảm dự trù. Reasoning và token ẩn phải nằm trong bound được xác minh; không rõ thì chặn. Dùng Decimal hoặc số nguyên micro-USD làm tròn lên, không float.

Trước mỗi attempt, transaction bền vững kiểm `settled + unresolved + active_reserved + R_attempt <= limit` cho request/ngày/tháng rồi ghi reserve và trạng thái dispatch. Kiểm cả ngân sách của attempt retry; cùng request không được vượt trần người dùng đã thấy. Nếu lần đầu được chứng minh không gửi/không tính phí thì giải phóng reserve của lần đó trước khi giữ lần hai. Không giữ transaction trong lúc chờ mạng.

Ví dụ **giá giả lập**: I_bound=1.000, O_cap=500, input=1 USD/triệu và output=2 USD/triệu → reserve 0,002 USD. Hai attempt có thể bị tính phí phải được dự trù 0,004 USD; v1 không tự tạo attempt thứ hai khi phí attempt đầu chưa rõ.

- Success có usage hợp lệ: chuyển reserve sang settled theo rate card đã pin, chỉ trả lại phần dư; không đếm hai lần reasoning đã gồm trong completion tokens.
- Usage thiếu/sai, crash sau dispatch hoặc mạng không rõ: chuyển sang unresolved và tiếp tục tính đủ reserve vào hạn mức. Không giải phóng chỉ vì TTL hoặc timeout.
- Restart: mọi record dispatch chưa kết thúc là unresolved; không tự phát lại request. Ledger hỏng/không ghi được: chặn cloud.
- Usage thực vượt dự trù: ghi đủ actual, không cắt số tiền để làm đẹp báo cáo; khóa provider và yêu cầu đối soát trước lần tiếp theo.
- Đối soát thủ công dựa vào hóa đơn/dashboard, ghi người thực hiện và bằng chứng local; không cho model tự sửa ledger.
- Khi qua ngày/tháng, settled tính theo kỳ attempt bắt đầu; active/unresolved vẫn tính vào khả dụng của kỳ hiện tại đến khi đối soát, không được biến mất nhờ qua nửa đêm. Một request_id có một tổng trần xuyên kỳ.

Đây là chặn chi phí **của luồng ứng dụng theo rate card đã xác minh**, không phải cam kết tuyệt đối về hóa đơn bên ngoài. Nhà cung cấp có thể tính phần request bị hủy; giá có thể đổi, khóa có thể bị dùng từ nơi khác. Dùng quota/spending cap bên provider khi có, tắt auto-top-up nếu có; không khẳng định các tính năng này tồn tại ở mọi tài khoản.

## 8. Audit, output và SLM

Audit local chỉ lưu timestamp, ID ngẫu nhiên, provider/model cấu hình, revisions, attempt/state/error_code, elapsed_ms, usage, reserve/settled/unresolved. Không lưu prompt, response, Authorization, grant, tên/path tài liệu hay raw exception. Log metadata giữ 30 ngày theo đề xuất; ledger chưa đối soát không bị xóa bởi dọn log. Output được coi là dữ liệu không tin cậy: escape khi hiển thị, không thi hành tool/code/URL, vẫn kiểm schema và nguồn. `draft` phải giữ placeholder khi thiếu dữ kiện; không tự approve.

Dataset SLM là gói riêng: mặc định không thu prompt/output làm dữ liệu huấn luyện; chỉ xuất mẫu người dùng duyệt, có nguồn gốc/giấy phép phù hợp và quyền xuất riêng. Quyền gọi cloud không cấp quyền huấn luyện. Hợp đồng này không kết luận điều khoản lưu giữ/huấn luyện của DeepSeek hay Z.AI; trước dữ liệu thật phải kiểm điều khoản tài khoản và chính sách dữ liệu cụ thể.

## 9. Tiêu chí nghiệm thu trước khi bật cloud

Các ca sau là yêu cầu test tương lai, **chưa chạy trong PR tài liệu**. Dùng mock transport, đồng hồ và ledger tạm; không cần khóa thật.

| Ca | Kết quả cần chứng minh |
|---|---|
| enabled=true, không grant hoặc classification unknown/internal | 0 network calls |
| Prompt injection giả lệnh duyệt, agent gửi approved=true | Không tạo grant |
| Đổi một byte payload, source version, endpoint/model/price revision | STALE_REQUEST trước network |
| Grant hết hạn/thu hồi, client khác dùng, hai execute cùng token | Không gửi trái quyền; nhiều nhất một logical request |
| Khóa sentinel + lỗi provider có echo khóa/body | Không rò qua log, exception công khai, UI hoặc MCP |
| Endpoint tùy ý, redirect, DNS rebinding, env proxy | Bị chặn; không gửi Authorization đến đích khác |
| 401/402/5xx/read timeout | Không retry; loại không rõ giữ reserve |
| Connect fail đã chứng minh chưa gửi; Retry-After dài | Tối đa hai attempts; deadline không bị kéo dài |
| Hai request đồng thời sát hạn mức, retry, qua nửa đêm | Tổng hạch toán không vượt quy tắc; không reset unresolved |
| Crash sau dispatch, duplicate result, usage thiếu/vượt reserve | Không phát lại; đối soát một lần; khóa khi vượt dự trù |
| Giá hết hạn, tiền âm/NaN, bool thay số, DB lỗi | Chặn trước network |
| Output sai nguồn/schema, timeout khi tài liệu đã approved | Không thay trạng thái/phiên bản đã duyệt |
| Cancellation và response nhỏ giọt | Deadline tổng hữu hạn, không attempt muộn |

Sau đó chạy regression Linux và CI Windows; kiểm nguyên ba MCP tool hiện có. Một thử nghiệm live với synthetic chỉ thực hiện khi người dùng cấu hình khóa, bật cloud và xác nhận trần phí. Không đánh dấu live/egress đạt từ việc đọc mã.

## 10. Gói việc tiếp theo — mỗi buổi một gói

1. **Astra:** triển khai PolicyGate thuần dữ liệu + test chặn cloud, chưa mạng/DB. Đây là đề xuất đầu việc nhỏ tiếp theo sau khi duyệt thiết kế.
2. Astra thiết kế chi tiết transaction grant/ledger và kiểm các tình huống crash; Claude giữ triển khai migration/service/UI theo hợp đồng được duyệt, không song song sửa cùng file.
3. Astra triển khai và kiểm adapter từng provider, timeout/retry/giới hạn giá; Gemini chỉ nhận fixture synthetic hoặc hàm nhỏ đã chốt schema và đường dẫn.

Đề xuất model cho phần khó: Astra mức suy luận high cho grant/ledger/API và kiểm thử race/crash; Claude giữ lõi hiện hữu. Không cần giao Gemini toàn bộ gateway. Mỗi gói có nhánh/base/file sở hữu và biên bản test riêng; chỉ người dùng merge. Danh sách này không phải giao chạy cả ba buổi hôm nay.

## Nguồn đã đối chiếu ngày 10/09/2026

- [DeepSeek — first API call](https://api-docs.deepseek.com/): endpoint và Bearer API key.
- [DeepSeek — error codes](https://api-docs.deepseek.com/quick_start/error_codes/): 401/402/429/500/503. Khuyến nghị retry của provider không chứng minh request miễn phí; hợp đồng v1 thận trọng hơn ở kết quả chưa rõ.
- [Z.AI — API introduction](https://docs.z.ai/api-reference/introduction): general API/Bearer và Coding Plan có endpoint riêng.
- [Z.AI — pricing](https://docs.z.ai/guides/overview/pricing): nơi đối chiếu rate card khi chọn model; tài liệu này không chép giá thành cấu hình chạy.
- [HTTPX — timeouts](https://www.python-httpx.org/advanced/timeouts/): connect/read/write/pool là các loại timeout riêng.
- [MCP — security best practices (draft)](https://modelcontextprotocol.io/docs/draft/tutorials/security/security_best_practices): ranh giới credential và SSRF. Tham khảo draft, không khẳng định ứng dụng đã tuân thủ toàn bộ đặc tả.
