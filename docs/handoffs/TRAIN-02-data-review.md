# TRAIN-02 — bàn giao issue #49

Ngày 13/09/2026. AI thực hiện theo yêu cầu anh Khang; không khởi chạy subagent.
Base main: `9fc104facfc8974c0ee47eccc9e358895a48d523`.
Nhánh: `codex/train02-data-review`; checkout riêng `artifacts/aimarx-train02-49`.
Head cuối được ghi trong bình luận issue/PR sau commit để không tạo hash tự tham chiếu.

## Sản phẩm

- [Rà soát 36 baseline](TRAIN-02-baseline-review.md): từng ID, nguồn, quyết định,
  thứ tự bước, điểm cần người xác nhận; không thay reference/scorer đã merge.
- [Bảng duyệt 120 mẫu](../../evals/training/train02/review-index.md), cases/manifest,
  authoring tái lập và CLI offline; [hướng dẫn](../../evals/training/train02/README.md).
- 12 mẫu đại diện được serialize và kiểm trước khi serialize đủ 120. Bộ đầu đạt
  schema/nguồn, đủ 6 nhóm/4 decision, không cặp gần trùng vượt ngưỡng với baseline.
  Sau đó bổ sung verify trước draft cho nhóm nhiều nguồn và kiểm lại toàn bộ.
- 120 draft, 80 train / 20 validation / 20 smoke-test, 30 họ nguồn + 30 họ mẫu,
  mỗi họ bốn tình huống. Không nhân baseline bằng đổi tên/ngày, không dùng hồ sơ thật.
- Phân bố nhóm: clear 30, missing 22, multi_source 23, deadline 12, terminal 18,
  adversarial 15. Decision: plan 67, ask 35, no_action 10, out_of_scope 8.
- **0 đã được người duyệt; 120 pending_human; 0 quyền train; 0 quyền export**.
  Không tự điền reviewer hoặc human approval. Không có model AIMarx đã fine-tuned.

## Công cụ và cổng

Review theo lô có checklist, expected content hash, người tự khai danh tính,
reason, thời gian UTC và receipt chain. Duyệt chất lượng riêng với quyền train/export.
Sửa input/reference/rubric/split/family/nhãn làm hash khác; refresh giữ receipt cũ
nhưng thu hồi trạng thái/quyền. Loader từ chối sửa chỉ manifest hoặc lật cờ quyền.
Receipt local không xác thực danh tính/chữ ký số và không chống người sửa được cả
file/hash; giới hạn này ghi trong README.

Inference dùng allowlist TRAIN-01, không reference/rubric/reviewer. Review queue chứa
đáp án, ghi nhãn chỉ dùng cho người xem. Export tạo prompt/completion riêng, không
xuất smoke-test làm train; kiểm mọi mẫu được chọn, không lọc âm thầm mẫu chưa duyệt.
Output local tạo mới, không đè file. Không train, upload, gọi model/cloud hoặc GPU.

Không sửa hoặc tái triển khai module #46. Base chưa có module nên check báo
`blocked_dependency_46`; module xuất hiện nhưng chưa pin bản được nghiệm thu cũng
bị chặn. Tích hợp thật cần PR sau #46 merge/nghiệm thu để pin hash và chạy lại
integration. Test doubles ở TRAIN-02 chỉ xác nhận wiring/đường chặn, không chứng minh
thuật toán #46 đạt. Đây là phụ thuộc còn mở, không báo export production đã sẵn sàng.

Near-duplicate: word-bigram Jaccard ≥0,65 sau NFC/casefold/chuẩn hóa chữ số; so block
và request+nguồn, gồm cross-check 36 baseline. **0 cặp vượt ngưỡng** hiện tại.
Không chứng minh không có paraphrase/rò ngữ nghĩa. Static tests kiểm phân bố/tách họ
của draft; không thay split audit tùy ý. Toàn bộ smoke đã exposed; pilot cần test kín N≥120.

## Kiểm thử thực tế trên Linux

Interpreter venv hiện có: `/home/asus/Documents/ChatGPT/AI-agent for me/.venv/bin/python`,
Python 3.12, không đổi dependencies. Từ checkout TRAIN-02:

| Lệnh / phép kiểm | Kết quả |
|---|---|
| `python -m evals.planning_v2.cli check` | 36 reference qua kiểm cấu trúc, chưa duyệt |
| `python -m evals.training.train02.cli check` | 120 hợp lệ; 80/20/20; 120 pending; gần trùng 0; dependency #46 blocked |
| `python -m pytest -q tests/test_train02_data_review.py` | **67 passed**, 27,32 giây |
| `python -m pytest -q -o faulthandler_timeout=60` ngoài sandbox | **727 passed, 2 skipped**, 53,29 giây; một cảnh báo AnyIO có sẵn |
| CLI queue/inputs, batch review, export bị chặn | Kiểm qua tests với dữ liệu giả; queue 120 dòng tạo local thật |
| `git diff --check` | Không lỗi whitespace |

Lượt full pytest đầu trong sandbox không có tiến triển, đã ngắt đúng session test;
**không tính là pass**. Chạy lại ngoài sandbox đạt như trên, không giết/restart ứng dụng.
Data1000 opt-in và Windows-only junction là hai skip cũ trên Linux; không xác minh
production/Data1000 trong gói này. Windows kiểm qua GitHub Actions, trạng thái thực
được cập nhật ở PR; không suy pass Windows từ Linux.

Ca âm gồm thiếu/thừa trường, quote/version/worker/graph giả, stale hash sau sửa nhiều
loại nội dung, contract đổi, receipt sửa, quyền thiếu/giả, chưa attestation, reject thu
quyền, lô trùng/ID lạ, JSON trùng key/NaN, cấm đè file, chặn smoke-test export,
dependency thiếu/chưa nghiệm thu/findings, near-duplicate khác tập và sentinel gold/
rubric/reviewer không vào prompt. CI hiện có tự chạy toàn bộ pytest Ubuntu/Windows.

## Phạm vi sở hữu và phối hợp

Chỉ thêm:
- `evals/training/train02/` (core, CLI, authoring, cases, manifest, README, review-index).
- `tests/test_train02_data_review.py`.
- `docs/handoffs/TRAIN-02-data-review.md`, `TRAIN-02-baseline-review.md`.

Đã ghi claim trên issue #49 trước code. PR #47 vẫn mở lúc nhận việc, không sửa các
tài liệu kế hoạch/worklog/PSC-01 nó sở hữu. Không sửa file #46, ledger, runtime,
DB, dependencies, planning-v1/v2 hoặc extraction. Handoff này và issue/PR thay
worklog chung trong phạm vi phối hợp hiện tại.

## Bàn giao / rollback

PR cho anh Khang merge. Người duyệt dùng bảng/queue xem nguồn, chốt các điểm nghiệp vụ
rồi tạo decisions theo README; không coi merge code là duyệt dataset hoặc cấp quyền.
Sau #46 nghiệm thu mới nối/pin dependency; TRAIN-03 mới benchmark và xem tài nguyên.

Rollback bằng revert PR nếu đã merge; không có migration hay thay runtime/model.
Giữ riêng artifact đã được người duyệt ở thư mục mới, không tái sinh đè từ authoring.
Chưa có upload, provider grant/budget, job train hoặc deploy cần thu hồi.
