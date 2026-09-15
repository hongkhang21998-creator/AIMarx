# API-MCP-PROVIDER — phạm vi AIMarx hiện hành

Ngày chốt: 15/09/2026

## Mục tiêu duy nhất

AIMarx là **cổng cá nhân để quản lý và sử dụng nhanh các tài khoản/provider AI
qua API và MCP Server**. Hệ thống không còn mục tiêu tự huấn luyện model hoặc
chứng minh một SLM fine-tuned tốt hơn base.

AIMarx chỉ truy cập được dịch vụ đã có API/connector hợp lệ và đã được anh cấu
hình. MCP không tự đăng nhập website, không vượt xác thực, không lấy mật khẩu và
không biến một tài khoản web không có API thành provider.

## Quyết định đã khóa

- Dừng mọi TRAIN tiếp theo; không có TRAIN-08.
- Hủy kế hoạch A/B kín 120 ca vì không còn là cổng phát hành.
- Không cần merge adapter step 40, chuyển GGUF Q4_K_M hoặc chọn Q3/Q4 để hoàn
  thành mục tiêu API/MCP.
- Qwen/Ollama chỉ là **provider local tùy chọn**. Nếu giữ Q3 hiện có thì vẫn khóa
  `num_ctx=2048` vì phù hợp máy 8 GB; đây không phải yêu cầu của cổng API/MCP.
- Một façade/provider gateway dùng chung cho UI, API và MCP.
- Không tự gửi dữ liệu, phát sinh chi phí, phát hành văn bản hoặc thay quyền duyệt.

Các artifact TRAIN-01–07 được giữ làm lịch sử và có thể dùng lại nếu tương lai
anh đổi mục tiêu; không xóa checkpoint hoặc bằng chứng cũ.

## Chức năng cần đưa vào hoạt động

### 1. Quản lý provider và tài khoản API

- Thêm, thay, kiểm tra kết nối, bật/tắt và thu hồi credential.
- Credential thật nằm trong kho bí mật hệ điều hành; SQLite chỉ giữ tên provider,
  cấu hình không nhạy cảm, fingerprint và trạng thái.
- Hỗ trợ trước các provider đã có adapter/allowlist trong repo như local Ollama,
  OpenAI và DeepSeek. Provider mới phải có adapter riêng; không dùng endpoint tùy
  ý do model hoặc MCP client truyền vào.
- Cho người dùng chọn provider/model rõ ràng. Không cần SLM tự quyết định.
- Hiển thị kết quả kiểm tra, lỗi xác thực, timeout, trạng thái bật/tắt và lượng dùng
  mà không làm lộ API key.

### 2. API façade cá nhân

- UI, API và MCP gọi cùng một service/gateway; không có đường tắt lấy key trực tiếp.
- Mỗi request kiểm provider đang bật, model thuộc allowlist, timeout, giới hạn
  request, ngân sách và quyền dữ liệu trước khi gọi.
- Local provider chỉ dùng loopback và không fallback cloud.
- Cloud provider không nhận tài liệu nội bộ/hạn chế/unknown nếu chưa có snapshot
  bất biến và grant rõ ràng.
- Lỗi provider phải trả trạng thái thật; không báo hoàn thành giả hoặc tự retry vô hạn.

### 3. MCP Server

- Chạy MCP stdio/local để Codex, Claude hoặc MCP client được phép kết nối AIMarx.
- MCP chỉ nhận tên provider/model và nội dung công việc cần thiết; **không có tham
  số API key, mật khẩu hoặc secret**.
- Công cụ MCP phải dùng đúng façade và hàng rào quyền giống UI/API.
- Danh sách công cụ, schema đầu vào/đầu ra và lỗi phải ổn định, có test smoke.
- MCP không tự thêm tài khoản, cấp grant, nâng budget, gửi hoặc phát hành văn bản
  nếu người dùng chưa thực hiện thao tác quản trị tương ứng.

## Việc triển khai tiếp theo

1. Nghiệm thu các thao tác credential: add/replace/test/enable-disable/revoke.
2. Nghiệm thu chọn provider/model và chuyển đổi giữa local, OpenAI, DeepSeek.
3. Chạy mock cho API gateway, timeout, budget, grant và ledger.
4. Chạy smoke API và MCP bằng Ollama loopback hoặc provider giả lập.
5. Chỉ khi anh duyệt: probe một cloud provider bằng đúng một request giả lập,
   budget tối thiểu và không chứa hồ sơ thật.
6. Ghi hướng dẫn cấu hình MCP client và quy trình đổi provider/tài khoản.
7. Sau probe, thu hồi grant thử hoặc đưa budget về 0 nếu chưa dùng thường xuyên.

## Tiêu chí hoàn thành

- Có thể thêm và kiểm tra credential mà key không xuất hiện trong DB, log, API
  response hoặc tham số MCP.
- Có thể chọn và gọi provider đã bật từ UI/API/MCP qua cùng gateway.
- Local không tự fallback cloud; provider tắt hoặc hết budget bị chặn rõ ràng.
- Timeout/lỗi xác thực/lỗi mạng không làm mất tác vụ hoặc báo thành công giả.
- Một request cloud giả lập hoạt động với ledger và chi phí nằm trong hạn mức anh
  duyệt; không có tài liệu nhạy cảm.
- MCP client kết nối được, liệt kê đúng tool và thực hiện smoke end-to-end.
- Có lệnh dừng, thu hồi credential/grant và rollback cấu hình.

## Phân công

- **Sol:** hoàn thiện adapter, façade, API/MCP, test và hướng dẫn vận hành theo hợp
  đồng đã khóa.
- **Astra:** chỉ review bảo mật, quyền dữ liệu, ngân sách và nghiệm thu các đường
  gọi; không thiết kế hoặc mở đợt train.
- **Anh Khang:** thêm credential, chọn provider/model, duyệt budget/grant và quyết
  định khi nào thực hiện probe thật.

## Liên hệ PR #82

PR #82 đang triển khai agent local Q3 và hành vi chọn tool. Phần Ollama loopback,
MCP/API smoke và khóa context 2.048 có thể tái sử dụng; phần biến SLM thành điều
phối bắt buộc không còn là mục tiêu. Cần thu gọn #82 hoặc chỉ lấy các thành phần
provider/MCP phù hợp trước khi merge.

## Điểm dừng của PR này

Đây là thay đổi phạm vi và tiêu chí nghiệm thu. Chưa gọi cloud, chưa thêm key, chưa
phát sinh chi phí, chưa bật provider thật và không chạy hoặc lên lịch training.
