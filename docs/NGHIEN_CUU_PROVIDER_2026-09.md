# Nghiên cứu Qwen, Kimi, GLM, DeepSeek cho danh mục MCP — 11/09/2026

Bổ sung cho `docs/PROVIDER_SECURITY_CONTRACT.md` (PSC-01). Danh mục model (`model_catalog.py`) nay nhận thêm `qwen` và `kimi`, cạnh `deepseek` và `glm` đã có. **Thêm vào danh mục không bật được gì**: chưa có adapter cloud nào, và mọi provider không phải `ollama` đều đi qua `policy_gate` — mặc định chặn, tối đa chỉ `CONSENT_REQUIRED`.

Mỗi dòng dưới đây ghi rõ nguồn. **Nguồn chính thức** là tài liệu, điều khoản của chính hãng, hoặc thư viện Ollama. Dòng đánh dấu *(thứ cấp)* lấy từ bài tổng hợp, phải đối chiếu lại trước khi dùng làm căn cứ.

## Tóm tắt

| | Qwen (Alibaba) | Kimi (Moonshot) | GLM (Zhipu / Z.ai) | DeepSeek |
|---|---|---|---|---|
| Chạy local trên laptop 7 GB | **Có** — `qwen3:0.6b` đang dùng; `qwen3:1.7b` 1,4 GB có thể thử | **Không** — không có bản đủ nhỏ | **Không** — nhỏ nhất `glm4:9b` là 5,5 GB | **Có, hạn chế** — `deepseek-r1:1.5b` 1,1 GB, là bản chưng cất từ Qwen, chưa đo |
| API tương thích OpenAI | Có, endpoint theo vùng | Có | Có | Có |
| Công ty / nơi lưu dữ liệu API | Theo vùng người dùng chọn (Singapore, Bắc Kinh, Mỹ, Đức, Nhật, Hồng Kông) | Singapore | Singapore | **Trung Quốc** |
| Dùng nội dung để huấn luyện | Nói **không** | **Có**, không nêu cách từ chối | Theo DPA: **không lưu** nội dung | **Có**, có quyền từ chối |
| Xếp mức rủi ro dữ liệu trên giấy | Thấp hơn | Cao hơn | Thấp hơn | Cao hơn |

"Trên giấy" nghĩa là đọc chính sách công khai. PSC-01 mục 8 vẫn giữ nguyên yêu cầu: **trước dữ liệu thật phải kiểm điều khoản của đúng tài khoản**. Chính sách công khai có thể khác hợp đồng doanh nghiệp, và có thể đổi.

## Qwen — Alibaba Cloud Model Studio

- **Model:** họ Qwen3 có từ 0,6B đến 235B, giấy phép Apache 2.0 *(thứ cấp)*; bản mới nhất là Qwen3.8, trong đó Qwen3.8-27B có trọng số mở theo Apache 2.0 *(thứ cấp)*. Model Studio gọi bằng ID như `qwen3.8-max`, `qwen-plus` (chính thức).
- **Local (Ollama, chính thức):** `qwen3:0.6b` 523 MB, `qwen3:1.7b` 1,4 GB, `qwen3:4b` 2,5 GB, lượng tử hoá q4_K_M.
- **Endpoint (chính thức):** mỗi vùng một endpoint, gắn với workspace, và **khoá API chỉ dùng được ở vùng tạo ra nó**. Singapore: `https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`. Bắc Kinh: `https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`.
- **Dữ liệu (chính thức):** dữ liệu request lưu ở vùng đã chọn, nhưng **khâu suy luận có thể chạy ở nút khác** trong phạm vi triển khai đã chọn. Vùng Singapore chỉ có phạm vi "International". Tuyên bố không dùng dữ liệu để huấn luyện nằm ở trang FAQ của Model Studio (đọc qua kết quả tìm kiếm, chưa mở trực tiếp).
- **Ghi chú:** muốn chạy Qwen trên máy thì khai provider `ollama`, **không** khai `qwen`. Trong danh mục, `qwen` luôn nghĩa là API cloud của Alibaba.

## Kimi — Moonshot AI

- **Model:** flagship là Kimi K3; dòng K2 (K2.5, K2.6, K2.7) có trọng số mở và tự host được *(thứ cấp)*. Dòng K2 cỡ nghìn tỷ tham số, **không chạy được** trên máy 7–8 GB. Giấy phép K2 là một bản MIT có sửa đổi — cần đọc bản chính trong repo `MoonshotAI/Kimi-K2` trước khi dùng *(thứ cấp)*.
- **Endpoint (chính thức):** `https://api.moonshot.ai/v1` (tương thích OpenAI), và `https://api.moonshot.ai/anthropic`. Xác thực bằng `Authorization: Bearer`. Có gọi công cụ (tool use).
- **Dữ liệu (chính thức):** pháp nhân MOONSHOT AI PTE. LTD., Singapore; «We store the information we collect in secure servers located in Singapore». Nội dung người dùng được thu thập để «optimize our models». **Không nêu cách từ chối việc dùng để huấn luyện.** Chính sách cập nhật lần cuối 30/04/2025.
- **Kết luận:** không gửi nội dung nội bộ, kể cả khi đã bật cloud. `policy_gate` đã chặn sẵn nhãn nội bộ.

## GLM — Zhipu AI / Z.ai

- **Model (chính thức):** flagship `glm-5.3`, cùng `glm-5.3-flash`. GLM-5.2 theo giấy phép MIT; GLM-5.3 dùng giấy phép riêng; GLM-5.3-Flash theo MIT *(thứ cấp)*.
- **Local:** `glm4:9b` 5,5 GB (Q4_0) — không vừa laptop, và sát giới hạn máy Windows 8 GB.
- **Endpoint (chính thức, đã có trong PSC-01):** `https://api.z.ai/api/paas/v4/`. Coding Plan dùng endpoint khác, **không** được dùng thay general API.
- **Dữ liệu (chính thức):** pháp nhân JINGSHENG HENGXING TECHNOLOGY PTE. LTD., Singapore; dữ liệu cá nhân «generally processed in Singapore». Theo DPA, nội dung dùng API được xử lý tức thời và **không lưu trên máy chủ**. Cập nhật lần cuối 29/09/2025.

## DeepSeek

- **Model (chính thức):** API hiện dùng `deepseek-flash`. Tên cũ `deepseek-v4-flash` vẫn được nhận, và theo tài liệu thì từ 14/09/2026 `deepseek-v4-pro` sẽ được chuyển sang DeepSeek-V4.1-Flash. V4.1-Flash ra ngày 10/09/2026 theo giấy phép MIT *(thứ cấp)*.
- **Local (Ollama, chính thức):** `deepseek-r1:1.5b` 1,1 GB. Đây là model suy luận, chưng cất từ Qwen, luôn "nghĩ" trước khi trả lời — **chưa đo** với việc trích xuất.
- **Endpoint (chính thức, đã có trong PSC-01):** `https://api.deepseek.com`, và `/anthropic`.
- **Dữ liệu (chính thức):** «we directly collect, process and store your Personal Data in People's Republic of China». Dữ liệu được dùng «to train and improve our technology», **có quyền từ chối**. Lưu giữ chừng nào tài khoản còn tồn tại. Cập nhật lần cuối 10/02/2026.

## MCP: điểm dễ sơ ý nhất

Máy chủ MCP của AIMarx có `read_document` và `get_evidence`, **trả nguyên nội dung văn bản**. Kimi, GLM, Qwen đều quảng bá khả năng làm agent gọi công cụ. Nếu ai đó gắn máy chủ MCP này vào một trợ lý chạy trên cloud (app Kimi, Z.ai, Qwen Chat, v.v.), thì văn bản sẽ **rời máy mà không đi qua `policy_gate`**, vì cổng đó chỉ canh đường gọi model của ứng dụng.

- **Quy tắc:** máy chủ MCP của AIMarx chỉ nối với client chạy trên chính máy đó, qua stdio. Không đăng ký nó vào bất kỳ trợ lý cloud nào.
- **Việc còn phải làm:** chưa có gì trong mã ngăn được việc này, vì đó là cấu hình phía client. Nếu sau này mở MCP qua HTTP thì phải có xác thực và chỉ nghe loopback.

## Khuyến nghị theo định hướng AIMarx

1. **Giữ local là mặc định** (nguyên tắc 1 và 5 trong `docs/AIMARX_DINH_HUONG.md`). Với phần cứng hiện có, chỉ họ Qwen nhỏ và DeepSeek 1.5B chạy được. Ứng viên đo tiếp là `qwen3:1.7b`, nhưng phải giải quyết RAM trước: `llama-server` đã chiếm ~2,2 GB ngay với bản 0.6B ở `num_ctx` 8192.
2. **Cloud chỉ cho dữ liệu giả lập hoặc công khai**, như PSC-01 đã quy định. Nếu phải chọn thử một hãng, thì trên giấy GLM (Z.ai, không lưu nội dung) và Qwen (theo vùng, nói không huấn luyện) ít rủi ro hơn Kimi (dùng nội dung để tối ưu model, không có cách từ chối) và DeepSeek (lưu tại Trung Quốc, dùng để huấn luyện).
3. **Pháp luật Việt Nam về bảo vệ dữ liệu cá nhân** đặt nghĩa vụ riêng cho việc chuyển dữ liệu cá nhân ra nước ngoài. Tài liệu này không phải ý kiến pháp lý; trước khi gửi bất kỳ dữ liệu thật nào ra cloud cần kiểm riêng.

## Nguồn đã đối chiếu ngày 11/09/2026

**Chính thức:**
- [Kimi API — tổng quan](https://platform.kimi.ai/docs/api/overview) · [Kimi OpenPlatform — chính sách quyền riêng tư](https://platform.kimi.ai/docs/agreement/userprivacy)
- [DeepSeek API docs](https://api-docs.deepseek.com/) · [DeepSeek — chính sách quyền riêng tư](https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html)
- [Z.ai — quick start](https://docs.z.ai/guides/overview/quick-start) · [Z.ai — chính sách quyền riêng tư](https://docs.z.ai/legal-agreement/privacy-policy)
- [Alibaba Model Studio — tương thích OpenAI](https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope) · [Model Studio — vùng và phạm vi triển khai](https://www.alibabacloud.com/help/en/model-studio/regions/) · [Model Studio — FAQ](https://help.aliyun.com/en/model-studio/faq-about-alibaba-cloud-model-studio)
- [Ollama — qwen3](https://ollama.com/library/qwen3/tags) · [Ollama — deepseek-r1](https://ollama.com/library/deepseek-r1/tags) · [Ollama — glm4:9b](https://ollama.com/library/glm4:9b)
- [MoonshotAI/Kimi-K2 trên GitHub](https://github.com/moonshotai/kimi-k2)

**Thứ cấp** (chỉ dùng cho tên model mới nhất và giấy phép, cần đối chiếu lại):
- [Qwen 3.5 → 3.8 guide](https://codersera.com/blog/qwen-3-5-complete-guide-2026/) · [Qwen3.8-27B với Ollama](https://tech-insider.org/how-to-run-qwen3-8-27b-locally-ollama-2026/)
- [Kimi API models](https://www.morphllm.com/kimi-api) · [Kimi K3 API](https://agentsapis.com/kimi-api/)
- [DeepSeek V4.1-Flash — MIT](https://datanorth.ai/news/deepseek-releases-deepseek-v4-1-flash)
- [GLM-5.2 — MIT](https://datanorth.ai/news/zhipu-ai-releases-glm-5-2) · [GLM-5.3 — phiên bản và giấy phép](https://innfactory.ai/en/ai-models/glm/)
