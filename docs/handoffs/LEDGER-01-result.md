# LEDGER-01 — hoàn thiện PR #44

Ngày 12/09/2026. Claude/Opus triển khai schema/reserve và phần dở; Astra tiếp nhận,
kiểm tra, sửa và hoàn thiện theo yêu cầu trực tiếp của anh Khang.

## Nguồn mã và phạm vi sở hữu

- Main/base: `d6a5f49811bd466cf8615beaf284705bf93bfc6b`.
- Draft Claude đã push: `4ad61eae2e524e5404b842722cc4ee486b631e42`.
- Kế thừa 4 file chưa commit từ worktree `aimarx-ledger-01`; SHA-256 patch:
  `f65dc6d036398d85e19c6c15bc5a7bc6beb45504c36414b29004ca8cdcc319fc`.
- Checkout hoàn thiện: `/home/asus/Documents/ChatGPT/AI-agent for me/artifacts/aimarx-pr44-completion`, nhánh `claude/ledger-store`,
  cập nhật chính PR #44. Không reset/clean cây gốc hoặc kho production Data1000.
- File: provider_ledger.py; provider_grants.py (P1); provider_snapshot.py (P2 và
  rollback/lỗi DB); test ledger/grant + runner mutation; LEDGER_OPTIONS và WORKLOG.
  Không sửa model, UI/MCP/parser, fixtures planning hoặc dữ liệu nghiệp vụ.

## Hành vi hoàn tất

1. Schema/số nguyên/ceil; đóng góp đủ sáu trạng thái, giá và giới hạn ngữ cảnh có
   revision, cấu hình riêng máy, mặc định ngân sách 0; bản ghi lệch trạng thái và
   số tiền bị chặn trước khi tính tổng.
2. Reservation đúng kiểu frozen và khớp dòng DB cả provider/model/endpoint,
   pricing/limits/deadline; reserve + claim + consume cùng transaction.
3. Settle + event + provider lock + `_finish_locked` cùng transaction; public finish
   chặn khoản pending; lỗi commit/SQLite được rollback và đổi thành mã không chứa
   nội dung exception. Kết quả failed vẫn có thể settled tiền, không sửa versions.
4. Recovery không retry; dead owner ngay, unknown chờ deadline/grace. Release,
   unresolved, recovery đóng snapshot failed nguyên tử. Reconcile idempotent theo
   principal/actual/evidence, giữ kỳ started_at gốc và chỉ mở lock khi hết sự cố.
   Settlement replay kiểm cả usage nguyên gốc và outcome, không chỉ số tiền.
5. Test functional, tranh hạn mức bằng hai tiến trình và crash thật trước/sau
   finish, test corruption/read-only/sentinel, mutation source trong bản sao riêng.

## Sửa thêm sau khi tiếp nhận

- Bộ dở có timestamp nửa đêm sai; sửa bằng ISO datetime có offset +07. Ca kiểm qua
  tháng trước đây bị rate card hết hạn chặn trước khi tới phép thử ngân sách; dùng
  rate card synthetic mới ở kỳ mới để thử đúng điều kiện.
- Reconcile trước đây không replay được. Settle trước đây bỏ qua outcome và usage
  khác nhưng cùng giá. Release/recovery trước đây để snapshot dispatching.
- Chặn Reservation giả dạng mutable, đối chiếu thêm các binding, giới hạn context
  đã xác minh, verified_at tương lai và trạng thái settled/reconciled thiếu actual.
- Thay test mô phỏng một hàm lỗi giả bằng runner thật sửa production source rồi
  yêu cầu test thất bại do assertion; collection/setup error không tính là bắt lỗi.

## Kiểm chứng

Kết quả local và mutation dưới đây đã chạy trên mã hoàn thiện trước khi push. CI Ubuntu/Windows
phải đọc ở Checks gắn với head PR, kết quả cuối ghi ở bình luận bàn giao PR #44.
Không dùng CI xanh của draft `4ad61ea` để chứng minh mã mới.

| Phép thử | Kết quả |
|---|---|
| Regression `pytest -q tests docs`, dữ liệu ext4, bật ca Data1000 | 588 passed, 1 skipped, 1 warning; 61,52 giây |
| Regression cùng bộ, toàn bộ basetemp trên Data1000 NTFS | 588 passed, 1 skipped, 1 warning; 252,06 giây |
| Regression local sau reboot (Data1000 chưa gắn) | 587 passed, 2 skipped, 1 warning; 60,86 giây |
| Đột biến source độc lập | 15/15 bị bắt bằng test assertion; không tính lỗi collection/setup |

Một skip ở Linux là test Windows junction; warning là deprecation AnyIO có sẵn.
Windows bỏ qua probe `/proc` và ca Data1000 không được bật, nhưng vẫn chạy nhánh
unknown/deadline, tranh hạn mức và crash bằng multiprocessing spawn.

Chạy lại từ checkout PR với Python 3.12 và requirements.lock:

```bash
python -m pytest -q tests docs
python tests/ledger_mutations.py /tmp/aimarx-ledger-mutations.json
# Chỉ trên máy có mount Data1000 thật, dùng basetemp TEST mới riêng biệt:
AIMARX_TEST_DATA1000=1 python -m pytest -q tests docs --basetemp /run/media/asus/Data1000/AIMarx/workspace/_ledger_test/ledger-01-verification
```

Runner mutation sửa source trong thư mục tạm, không sửa checkout. Các mutation
được lưu cùng kết quả tại `LEDGER-01-mutations.json`.

## Giới hạn và bàn giao tiếp

- Không có adapter/khóa/API thật, chưa UI xác nhận/đăng nhập local. Merge ledger
  không bật cloud hoặc cấp quyền chi phí; ngân sách 0 và rate card chỉ giả lập.
- Usage/UnsentProof là kiểu nội bộ, không xác thực caller Python. Adapter sau này
  phải tạo từ transport tin cậy, không nhận object tự khai từ UI/model/MCP.
- `now_ms` do backend tin cậy cấp. High-water chặn lùi qua kỳ và nhảy >400 ngày;
  không thay xác minh giờ hệ thống. Deadline mạng monotonic còn thuộc gói adapter.
- Linux dùng `/proc` start token; Windows chưa có probe tương đương, giữ phí đầy đủ
  đến deadline/grace rồi unresolved. Không tự coi PID chưa rõ là đã chết.
- Schema ledger chưa được triển khai production. Không migration dữ liệu thật;
  DB synthetic của draft cũ thiếu cột mới cần dựng lại riêng, không tự ALTER kho thật.
- Trần số học: actual ngoài dải hỗ trợ bị từ chối, khoản reserve giữ nguyên để
  recovery/đối soát; không clamp xuống reserve hoặc tự xóa khoản bất định.
- Không benchmark SLM, không thay model, không restart ứng dụng. Bước sau ledger
  là adapter/rate card tin cậy và quyền UI trong gói riêng, từ main sau merge.

## Rollback và tránh chồng việc

Anh Khang merge. Khi cần rollback mã đã merge, dùng PR revert commit merge #44;
không xóa DB/ledger/events để rollback tiền. Hiện chưa có production migration.
Worktree cũ của Claude vẫn có diff dở: không push lại nhánh cũ lên #44. Sau khi
bàn giao, đọc head PR và WORKLOG trước khi nhận file. Bản sao dở được bảo toàn;
không ai cần ghi đè nó để lấy mã hoàn thiện từ GitHub.

## Khôi phục sau reboot cùng ngày

Máy khởi động lại trước khi commit thành công; checkout /tmp bị xóa. Astra tái lập
đúng các sửa chữa từ nhật ký phiên này trên bản dở gốc có cùng hash patch, sang
checkout bền vững nêu trên. Hash blob snapshot `06c5043` và grants `912f117` khớp
trước reboot. Chạy lại regression local và mutation trước push; số liệu Data1000
ở trên thuộc lượt đã hoàn tất trước reboot, không tuyên bố ổ đang được gắn.
