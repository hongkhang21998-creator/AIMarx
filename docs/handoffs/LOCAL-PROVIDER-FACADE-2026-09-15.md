# Bàn giao façade local và provider gateway — 15/09/2026

## Phạm vi hoàn thành

AIMarx chạy như một ứng dụng local duy nhất trên `127.0.0.1`. UI, API và MCP dùng chung `Aimarx`; không có đường tự đổi từ local sang cloud.

- Local: `/chat` và `POST /v1/chat` gọi Ollama; ghi token vào bảng hiện hữu.
- Credential: `/providers` quản lý key qua `keyring`; SQLite chỉ giữ provider, model, endpoint, bật/tắt, giới hạn, timeout và fingerprint.
- Cloud: UI xem trước payload rồi xác nhận. Backend nối snapshot, principal/grant dùng một lần, ledger giữ tiền, adapter và settlement.
- MCP: đúng năm tool `ask_aimarx`, `list_models`, `get_usage`, `read_document`, `get_evidence`; không có tool hoặc tham số credential/consent.

DeepSeek và OpenAI dùng endpoint cố định trong mã. Provider mặc định tắt; thiếu key, rate card đã xác minh hoặc ngân sách dương đều chặn trước network. Adapter tắt redirect, proxy môi trường và retry ngầm.

## Cấu hình riêng máy

Key được nhập trên `/providers`; không viết vào `.env`. `TLVB_PROVIDER_CONFIG` trỏ tới JSON rate card/hạn mức nằm ngoài Git, mặc định là `provider-config.json` trong `TLVB_DATA`. Schema được kiểm bởi `provider_ledger.load_config`; hạn mức mặc định bằng 0.

Không dùng giá ví dụ trong test cho provider thật. Trước live test phải nhập rate card từ nguồn chính thức, hạn dùng tối đa bảy ngày và hạn mức do anh Khang chốt.

## Checkpoint step40

Artifact tại `/home/asus/Downloads/AIMarx-Qwen2.5-3B-QLoRA-pilot-step40/checkpoint-40` có adapter SHA-256 khớp báo cáo: `3e60051c7df52204efbb64b70c94d07bd26eef798fa2b442114589f85d21a14f`.

Đây là PEFT/QLoRA Safetensors của Qwen2.5-3B, chưa phải model Ollama độc lập. Tài liệu Ollama hiện không liệt kê Qwen trong nhóm Safetensors adapter hỗ trợ trực tiếp, nên không tạo Modelfile suy đoán. Muốn dùng step40 cần merge/convert và lượng tử hóa trên môi trường đủ RAM, rồi kiểm output A/B trước khi đặt `TLVB_MODEL` sang tên model mới.

## Bằng chứng kiểm tra

- Full suite: `876 passed, 2 skipped`; một cảnh báo deprecation Starlette hiện hữu.
- Mock xuyên suốt cloud: prepare không gọi mạng; confirm tiêu thụ grant, giữ ledger, gọi đúng một request và quyết toán `settled`.
- Smoke web bằng kho `/tmp` và mode demo: năm route `/`, `/chat`, `/providers`, `/v1/providers`, `/v1/usage?period=today` trả HTTP 200 trên loopback; instance đã dừng.
- Chưa chạy inference Ollama thật trên checkout Linux này vì không có binary `ollama` trong PATH. Bằng chứng runtime Windows `qwen3:0.6b` trước đây thuộc commit cũ và không được tính là smoke của PR này.

## Hoàn tác

Revert PR này. Bảng `providers` chỉ chứa metadata và có thể để lại vô hại; credential trong kho hệ điều hành cần thu hồi qua `/providers` trước khi revert nếu đã nhập key thật.
