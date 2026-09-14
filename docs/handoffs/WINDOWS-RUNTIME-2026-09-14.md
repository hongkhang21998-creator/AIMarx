# Handoff triển khai AIMarx trên Windows — 2026-09-14

## Trạng thái đã hoàn tất

Đã chuẩn bị một checkout sạch của bản `main` sau PR #61 tại:

```text
D:/Claude-cowork/aimarx-token-stats
```

Commit nền đang chạy:

```text
e5d99cf46fbc8e8f43df8cf6e8dbb2d53887b77e
```

Checkout này được dùng riêng cho runtime Windows. Checkout training tại
`D:/Claude-cowork/tro-ly-van-ban` vẫn giữ nguyên branch
`codex/train03-cpu-backend`, các thay đổi training chưa commit và trạng thái
đang lệch `main`; không pull, reset, stash hoặc sửa các thay đổi đó.

## Thành phần Windows đã tải/cài

- Bộ cài chính thức: `D:/Claude-cowork/aimarx-windows-downloads/OllamaSetup.exe`
- Phiên bản bộ cài đã xác nhận: `0.34.0`
- Kích thước: `1,574,272,976` bytes
- SHA-256:
  `E2B98770FB87F3B4C593C22F2E8EDA59BCAC1CD7B141F1388C4181A8BF271A72`
- Chữ ký Authenticode: hợp lệ, người ký là Ollama Inc.
- Thư mục cài runtime hiện tại:
  `D:/Claude-cow/aimarx-token-stats/.runtime/ollama`
- API Ollama: `http://127.0.0.1:11434`
- Model đã tải: `qwen3:0.6b`
- Kích thước model: `522,653,767` bytes, định dạng GGUF, quantization `Q4_K_M`
- Digest model:
  `7df6b6e09427a769808717c0a93cadc4ae99ed4eb8bf5ca557c90846becea435`

Ollama native đang lưu model ở kho mặc định:

```text
C:/Users/admin'/.ollama/models
```

Không nên sao chép hoặc đổi kho model này sang `.runtime/models` một cách
ngầm định. `scripts/run-ollama.ps1` đã được cập nhật để dùng kho mặc định của
Windows khi `OLLAMA_MODELS` chưa được đặt, vẫn tôn trọng biến này nếu người
dùng chủ động đặt một kho khác, và không khởi động thêm server nếu API đã chạy.

## Cấu hình AIMarx runtime

Checkout sạch có môi trường Python riêng tại:

```text
D:/Claude-cowork/aimarx-token-stats/.venv
```

Cấu hình local hiện tại nằm trong file `.env` bị git bỏ qua:

```text
TLVB_DATA=D:/Claude-cowork/aimarx-token-stats/data
TLVB_MODE=ollama
TLVB_MODEL=qwen3:0.6b
TLVB_PORT=8765
```

Web đang chạy từ checkout sạch bằng Python trong `.venv`, lắng nghe tại:

```text
http://127.0.0.1:8765
```

Các địa chỉ đã kiểm tra trả HTTP 200:

- `/`
- `/tasks`
- `/usage?period=today`
- `/usage?period=all`

Kho dữ liệu ứng dụng hiện tại là kho mới:

```text
D:/Claude-cowork/aimarx-token-stats/data/state.sqlite3
```

Kho này đang rỗng có chủ ý. Đã tìm kiếm các vị trí workspace/Desktop liên quan
nhưng không xác định được `state.sqlite3` cũ; vì vậy không nhập nhầm dữ liệu
nghiệp vụ hoặc dữ liệu QA tổng hợp vào runtime.

## Bằng chứng kiểm tra

- Toàn bộ regression trên checkout sạch: `832 passed, 5 skipped`.
- Bộ test token: `16 passed`.
- Smoke tích hợp thật AIMarx → Ollama với tài liệu tổng hợp riêng: model trả kết
  quả thành công, ghi nhận `683` input tokens và `132` output tokens; dữ liệu
  smoke nằm ngoài kho nghiệp vụ và không phải bằng chứng đánh giá chất lượng
  mô hình.
- Ollama API trả version `0.34.0` và danh sách có `qwen3:0.6b`.

Các kết quả trên xác nhận đường chạy, model local, lưu usage và dashboard hoạt
động. Chúng không xác nhận chất lượng xử lý tài liệu nghiệp vụ thực tế.

## Phạm vi chưa tự động thực hiện

- Chưa khôi phục lịch sử token/tài liệu cũ vì chưa tìm được kho dữ liệu cũ có thể
  xác nhận.
- Chưa tự động lấy các file trong
  `C:/Users/admin'/OneDrive/Desktop/den-input26` vào kho AIMarx.
- Chưa tự động xuất dữ liệu sang
  `C:/Users/admin'/OneDrive/Desktop/work-output`.
- Chưa ghi sự kiện vào Google Calendar trong lần triển khai này.
- Không tìm thấy file ZIP checkpoint Colab trong workspace; checkpoint training
  không cần thiết để web dùng Ollama `qwen3:0.6b`. Nếu mục tiêu là khôi phục
  đúng ZIP training đó, cần cung cấp lại file hoặc đường dẫn nguồn xác định.

## Cách tiếp tục sau khi khởi động lại Windows

1. Mở Ollama native và kiểm tra API tại `127.0.0.1:11434`.
2. Nếu cần khởi động bằng repository, chạy `scripts/run-ollama.ps1`; launcher
   sẽ dùng Ollama đã cài hoặc binary trong `.runtime/ollama`, dùng kho model
   Windows mặc định và tái sử dụng server đang chạy.
3. Khởi động web từ checkout sạch với file `.env` hiện tại.
4. Chỉ sau khi anh xác nhận kho dữ liệu cũ hoặc thư mục tài liệu nghiệp vụ cần
   dùng, mới chuyển `TLVB_DATA` hoặc thực hiện nhập dữ liệu.

## Git handoff

Các thay đổi tài liệu/launcher được đặt trên branch:

```text
codex/windows-runtime-deployment-20260914
```

Branch này cần được review và merge bởi anh; không tự merge.
