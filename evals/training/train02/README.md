# TRAIN-02 — dữ liệu smoke và công cụ duyệt local

**120 dự thảo synthetic; 0 mẫu đã được người duyệt. Chưa train hoặc benchmark SLM.**
80 train / 20 validation / 20 smoke-test theo **30 họ nguồn và 30 họ mẫu**, mỗi họ
bốn tình huống. Tên split chỉ là dự kiến sử dụng, không cấp quyền train/export.
Tất cả đã công khai trong repo nên smoke-test **không phải test mù**. Pilot cần test
kín độc lập N≥120 sau này. Không chứa tài liệu/hồ sơ thật; nhãn internal/restricted
trong tình huống là mô phỏng, không phải giấy phép gửi hồ sơ thật ra ngoài.

Bắt đầu từ [bảng duyệt](review-index.md), mở ca nguồn trong `cases.json` để xem
input/reference/rubric đầy đủ. Báo cáo [review 36 baseline](../../../docs/handoffs/TRAIN-02-baseline-review.md)
phân biệt kết quả máy kiểm và câu hỏi cần người xác nhận. Không thay baseline.

## Phạm vi và cấu trúc

- `authoring.py`: 120 tình huống được AI viết cụ thể; gán họ/split trước khi serialize.
  Không gọi model hoặc dùng 36 baseline để đổi tên/ngày. Không có vòng lặp nhân tình
  huống bằng thay số: vòng lặp chỉ đóng gói các tình huống và hợp đồng worker.
- `cases.json`, `manifest.json`: bản chuẩn dự thảo, hash UTF-8 canonical JSON.
- `core.py`: kiểm schema, hash, receipt duyệt, near-duplicate, nối dependency #46,
  xuất prompt/completion local có kiểm soát.
- `cli.py`: check / inputs / review-queue / review / export, không gọi mạng.
- `review-index.md`: bảng gọn 120 ca; review-queue JSONL local chứa đầy đủ nội dung.

Dùng interpreter Python 3.12+ và dependency đã khóa của repo. Không cài thêm thư viện.
Các lệnh sau chạy từ root repo; thay `python` bằng interpreter venv hiện có.
Trên Windows dùng đường dẫn tạm của tài khoản và `PYTHONUTF8=1`.

```bash
python -m evals.training.train02.cli check
python -m evals.training.train02.cli review-queue --output /tmp/train02-review.jsonl
python -m evals.training.train02.cli inputs --output /tmp/train02-inputs.jsonl
python -m pytest -q tests/test_train02_data_review.py
```

`check` exit 0 chỉ xác nhận cấu trúc/hash và không có finding cross-split từ phương
pháp gần trùng. Báo riêng `split_audit.status`; dependency thiếu không được giả là
kiểm split đã đạt. `export_ready=false` trong check: công cụ này không cấp quyền xuất;
phải gọi export để kiểm lại đúng tập được chọn. Sai cấu trúc/hash hoặc finding rò
được phát hiện trả exit 2. Nội dung mẫu không được echo vào thông báo lỗi CLI.

`inputs` là artifact **chuẩn bị inference local**, được phép với draft; chỉ có
id/input/instruction/output_schema qua allowlist TRAIN-01. Không có reference,
rubric, split, provenance, reviewer hoặc lịch sử duyệt. Lệnh không gọi model.
`review-queue` chứa đáp án để người xem, không dùng làm input inference hay corpus train.

## Duyệt theo lô, đúng phiên bản

Mỗi dòng queue có ID, content_sha256 đầy đủ, input, reference, rubric, lịch sử và năm
mục checklist ban đầu false. Đọc nguồn rồi xác nhận từng mục:

1. Quyết định và sản phẩm đúng phạm vi người dùng yêu cầu.
2. Dữ kiện/số liệu/hạn có nguồn; citation đúng và có liên quan.
3. Hỏi đủ thông tin quan trọng, không hỏi thừa để né xử lý.
4. Worker và thứ tự phụ thuộc đúng; kiểm trước/sau dự thảo khi cần.
5. Không nhận injection, quyền giả, tự gửi/ký/chi tiền hoặc đổi nhãn nguồn.

Bịa dữ kiện/hạn, gán quyền hoặc thực thi không được phép là lỗi nghiêm trọng:
**reject**, ghi lý do, sửa nội dung rồi duyệt bản mới. AI review không thay người duyệt.

Người duyệt lập file JSON **array** các quyết định. Dưới đây là khung minh họa,
không phải quyết định cho mẫu thật; thay ID/hash sau khi đã xem đúng nội dung.

```json
[
  {
    "id": "ID_DA_XEM",
    "expected_sha256": "HASH_DAY_DU_CUA_NOI_DUNG_DA_XEM",
    "action": "approve",
    "reason": "Lý do của người đã kiểm tra",
    "checklist": {
      "decision": true,
      "grounding": true,
      "missing_information": true,
      "worker_order": true,
      "no_escalation": true
    },
    "training_approved": false,
    "export_approved": false
  }
]
```

Duyệt chất lượng và cấp quyền train/export là ba quyết định riêng: có thể approve
chất lượng nhưng giữ hai quyền false. Muốn export train/validation, cả hai quyền
phải true trên receipt hiện hành. Reject không được giữ quyền true. Khi đã có
quyết định thật của người duyệt:

```bash
python -m evals.training.train02.cli review --decisions /tmp/decisions.json --reviewer "Tên người thực sự duyệt" --human-attestation --output /tmp/train02-reviewed
python -m evals.training.train02.cli review-queue --data /tmp/train02-reviewed --output /tmp/train02-reviewed-queue.jsonl
```

Không có approve-all, không mặc định tên anh Khang, không tự tạo receipt khi sinh
dữ liệu. Thiếu/thừa trường, ID lạ/trùng hoặc một quyết định stale làm hỏng toàn lô
trước khi tạo output. Chỉ file được người dùng thực sự duyệt mới được áp dụng;
`--human-attestation` là lời xác nhận của người gọi, **không phải xác thực danh tính,
chữ ký số hay bằng chứng chống quản trị viên giả mạo file**. Tool local tin tài khoản
và người vận hành. Receipt hash chain phát hiện sửa không đồng bộ; không chống người
có thể sửa cả nội dung, lịch sử và hash. Không quảng bá thành audit log bất biến.

`review` tạo thư mục mới, giữ nguyên dữ liệu gốc. Một lần lỗi I/O có thể để lại thư
mục output chưa đủ file; loader từ chối bộ không có manifest hợp lệ. Chọn output mới
sau khi kiểm tra, không ghi đè bộ cũ. Các output file dùng exclusive create.

## Hash và sửa sau duyệt

- `source_sha256` bao gồm toàn bộ danh sách nguồn có ID/version/block/text/nhãn.
- `input_sha256` bao gồm request/as_of/sources.
- `content_sha256` bao gồm ID, family/template, split/category, input/reference/rubric,
  provenance và hash instruction/schema hiện hành.
- Receipt chứa hash nội dung được xem, người tự khai danh tính, thời gian UTC, lý do,
  checklist, hai quyền và hash receipt trước. Chỉ receipt cuối áp dụng; reject thu hồi.
- Manifest kiểm count, split counts, hash toàn cases và contract hash.

Sửa input/reference/rubric/split/family/nhãn rồi chỉ đổi manifest không qua loader.
Khi chỉnh draft bằng Python, gọi `core.refresh(case)` rồi `manifest_for(cases)` để
cập nhật hash: receipt cũ giữ trong lịch sử nhưng review_status trở về pending_human,
hai quyền false khi hash thay đổi. Không tự sửa receipt để giữ quyền. Không dùng
`authoring.py` tái tạo dữ liệu đã duyệt vì nó chỉ sinh draft mới và không giữ lịch sử.
Thay prompt/schema cũng làm nội dung đã duyệt không còn khớp contract.

## Split và dependency #46

Không sao chép `evals/training/split_audit.py`. Adapter chỉ truyền đúng năm trường
metadata của hợp đồng #46, ánh xạ `smoke-test → test`, giữ nguyên kết quả finding.
Module **chưa có trên base**, nên check báo `blocked_dependency_46`, export bị chặn.
Nếu xuất hiện module nhưng chưa pin bản nghiệm thu, báo `blocked_unreviewed_dependency_46`.

Sau #46 được merge **và nghiệm thu**, một PR tích hợp riêng kiểm hash file module,
đặt `SPLIT_AUDIT_APPROVED_SHA256` trong core và chạy lại integration tests thật.
Không có cờ CLI bỏ qua gate. Tests TRAIN-02 dùng test double rõ ràng để kiểm đường
pass/fail/metadata; **không coi đó là đã test thuật toán #46**. Test phân bố static
của 120 draft kiểm số họ và phân tách tập, không thay công cụ audit dữ liệu tùy ý.

## Gần trùng và giới hạn

NFC Unicode, casefold, thay các chuỗi chữ số bằng token chung, lấy tập word-bigram.
So Jaccard giữa từng block nguồn và giữa request+toàn nguồn; lấy điểm lớn nhất.
Ngưỡng **0,65**, báo ID cặp, nguồn baseline và cross_split. So mọi cặp TRAIN-02 và
TRAIN-02 với 36 baseline planning-v2. Không so từng cặp baseline với chính baseline.
Cặp vượt ngưỡng khác split hoặc với baseline chặn export; cặp cùng split chỉ để rà.
Không có cơ chế đánh dấu false-positive để bỏ qua trong gói này: phải sửa/phân lại
họ dữ liệu rồi duyệt lại, hoặc đề xuất cải tiến phương pháp có test riêng.

Có thể bỏ sót paraphrase, đồng nghĩa, đổi cấu trúc xa nhau; có thể báo nhầm đoạn ngắn
hoặc lời dẫn phổ biến. Không dùng embedding/model judge, không tuyên bố phát hiện mọi
rò rỉ. Với bản draft hiện tại: **0 cặp vượt ngưỡng**, không phải chứng nhận độc lập ngữ nghĩa.
Các worker/output chung là hợp đồng; các họ mẫu được nhóm theo nghiệp vụ/cấu trúc nguồn,
không giả rằng mỗi câu khác chữ là một template độc lập.

## Export và điểm dừng

```bash
python -m evals.training.train02.cli export --data /tmp/train02-reviewed --split train --output /tmp/train02-train.jsonl
python -m evals.training.train02.cli export --data /tmp/train02-reviewed --split validation --output /tmp/train02-validation.jsonl
```

Lệnh chặn nếu bất kỳ mẫu được chọn chưa approved đúng hash hoặc thiếu quyền; không
âm thầm lọc bỏ mẫu chưa duyệt. Kiểm split trên toàn bộ dataset và near-duplicate với
baseline. Smoke-test không được xuất thành train/validation; sửa nhãn split làm
mất duyệt. Mỗi dòng có prompt JSON serialize từ allowlist và completion JSON của
reference riêng; rubric/review/test gold không vào prompt. Đây là dữ liệu chuẩn bị,
chưa là notebook/tokenizer/label-mask cho training; mask/token budget thuộc TRAIN-03.
Không upload, không provider grant, không job GPU, không publish model.

## Tái tạo và kiểm tra

```bash
python -m evals.training.train02.authoring --representative --output /tmp/train02-first12-new
python -m evals.training.train02.authoring --output /tmp/train02-all-new
python -m evals.planning_v2.cli check
python -m pytest -q tests/test_train02_data_review.py tests/test_planning_v2.py tests/test_ledger_43a.py
python -m pytest -q
```

12 ca đại diện ghi trong `REPRESENTATIVE_IDS`, bao phủ sáu nhóm và bốn decision.
Không dùng tác vụ này để bật model/runtime, train, duyệt thay người hoặc merge PR.
