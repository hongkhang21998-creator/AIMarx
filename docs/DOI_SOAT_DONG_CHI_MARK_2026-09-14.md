# Đối soát hệ thống Đồng chí Mark — 14/09/2026

## Nguồn và mốc kiểm tra

- Tài liệu người dùng cung cấp: `He_thong_Dong_chi_Mark.docx`, tiêu đề “HỆ THỐNG MULTI-AGENT ĐỒNG CHÍ MARK”, phiên bản Big Mark (Speaker) + 5 đồng chí biểu quyết + Mark Huấn.
- SHA-256 file Word: `543b4a03659b855bd8f39d7cf86b7ad462eb4ad2749be36a87131995182445b3`. Đã đọc nội dung body, header/footer; comments/footnotes/endnotes không có nội dung chữ bổ sung. Không sửa hoặc đưa file nguồn vào repo.
- Main: `b4bcad080bb65b9d293f26e7b6289f124561a3ec`. PR #56: `e2f826d228cebd297fe436462a385cd4c45f1075`, còn mở tại thời điểm kiểm tra. Các trạng thái trong tài liệu là ảnh chụp tại mốc này.
- Word là thiết kế để đối chiếu, không phải bằng chứng code đã chạy hoặc quyền tự động train/đăng/gửi dữ liệu. Bản cập nhật này chỉ thay tài liệu.

## Kết luận về mức hoàn thành

Đã có MVP văn bản, cơ chế nguồn/duyệt, bộ 120 mẫu được duyệt và tooling train. Báo cáo Colab T4 ghi nhận smoke LoRA Qwen3-0.6B tới step 5. Chưa có hệ thống Mark vận hành hoặc bằng chứng model đạt yêu cầu chuyên ngành. Không có cơ sở tính một tỷ lệ phần trăm hoàn thành chung.

| Yêu cầu trong Word | Bằng chứng hiện tại | Khoảng thiếu / nghiệm thu tiếp theo |
|---|---|---|
| Một model local, nhiều vai trò logic trên máy khoảng 8 GB | [model.py](../src/tro_ly_van_ban/model.py) gọi Ollama local; [service.py](../src/tro_ly_van_ban/service.py) có graph infer/validate | Chưa có registry 7 vai trò hoặc đo bộ nhớ cho toàn workflow Mark; role không đồng nghĩa model riêng |
| Big Mark điều phối, không bỏ phiếu, giải quyết deadlock có log | Có graph trích xuất/kiểm tra, chưa có Speaker | Cần quyền điều phối, trạng thái deadlock và log lý do; không để Speaker tự cấp quyền |
| Văn soạn; Tìm tra cứu; Kiểm kiểm tra; Tri tri thức; Gói đóng gói | Có đầu ra DOCX, nguồn và validation của MVP | Chỉ là năng lực nền, chưa phải 5 agent; chưa có RAG/hồ sơ tìm kiếm theo thiết kế |
| Năm vai trò bỏ phiếu tuần tự, timeout thành abstention | Chưa có voting runtime | Cần hợp đồng vòng/phiếu, timeout bền vững, chống phiếu trùng/cũ và test thứ tự |
| Big Mark và Huấn không biểu quyết | Chưa có lớp vai trò | Kiểm bằng backend và test âm, không chỉ ghi trong prompt |
| Huấn tham vấn sau Big Mark, không tự sửa đầu ra | Chưa có Huấn | Kết quả tham vấn tách khỏi bản người dùng duyệt; không tự đổi nội dung đã duyệt |
| Bốn nhóm nguồn cho Huấn | Chưa có corpus này được kiểm chứng trong gói đang đối chiếu | Điều lệ Đảng, Tuyên ngôn 1848, triết học Marx, chủ nghĩa xã hội khoa học: cần nguồn/ấn bản/quyền sử dụng và duyệt riêng; không trộn vào 120 mẫu hành chính |
| Task có objective/priority/workers/depends_on/approval_before; mailbox SQLite | [service.py](../src/tro_ly_van_ban/service.py) có documents/versions/approvals | Chưa có task/message schema đầy đủ, mailbox hoặc queue Mark; phải chốt version schema và migration |
| Phục hồi khi tắt máy, lỗi agent, mất mạng | Lưu phiên bản/duyệt; [provider_ledger.py](../src/tro_ly_van_ban/provider_ledger.py) có phục hồi attempt | Phục hồi ledger không phải phục hồi workflow. Graph chưa có durable checkpointer; cần chạy lại an toàn, retry và checkpoint nghiệp vụ |
| API cho việc khó qua gateway | Có nền policy/grants/ledger trong repo | Không suy ra đã có gateway gọi model và scheduler đầy đủ; quyền dữ liệu/ngân sách vẫn riêng |
| Người dùng duyệt trước phát hành/gửi/sửa quan trọng | MVP duyệt phiên bản/hash và phát hiện bản cũ | Tái sử dụng cho workflow mới; voting không thay sự thật nguồn hoặc phê duyệt của anh |
| Xưng hô “Đồng chí [Tên]” | Đề xuất giao tiếp trong Word | Áp dụng khi thiết kế thông điệp vai trò; không đổi tên package/CLI trong gói tài liệu |

## Bằng chứng dữ liệu và training

1. PR #48: 36 ca reference proposal-v2; [review baseline](handoffs/TRAIN-02-baseline-review.md) phân biệt đánh giá AI với duyệt nghiệp vụ.
2. PR #50: chuẩn bị 120 mẫu dự thảo và công cụ duyệt. PR #52: split audit #46 và [duyệt của anh Khang](handoffs/TRAIN-02-human-approval.md). Snapshot `evals/training/train02/reviews/2026-09-13-khang` có 120 approved; root draft giữ lịch sử. Chia 80 train / 20 validation / 20 smoke; 20 smoke đã biết không phải test mù và không dùng train/tune.
3. Hash export train: `1062862c5db0c466de2b2ac20c3f217edabfcaa84ea34304c28c46a9758e4a2b`; validation: `8d3c43d3d69df8c7c58cba9733e76b1619d77629a144fae946468c8c56ad1741`.
4. [Preflight Windows](handoffs/TRAIN-03-Windows-Qwen06.md), PR #54: 2,914 GiB RAM trống, dưới cổng 4 GiB; không chứng minh train Windows thành công. Thông tin anh nói đã chạy cần bổ sung log/artifact của lượt đó trước khi đổi kết luận.
5. PR #55 đã merge [tooling Colab](../training/colab_qwen06/config.json). [PR #56](https://github.com/hongkhang21998-creator/AIMarx/pull/56) còn mở: context tăng 2048→4096 sau token audit, 100 mẫu dài tối đa 2448 token, không vượt giới hạn sau sửa. Context train này khác giới hạn runtime trích xuất.
6. Báo cáo #56: T4, FP16, checkpoint-1 rồi process mới chạy tới checkpoint-5; thời gian tương ứng 11,69 và 37,72 giây. Đây là smoke kỹ thuật. Con số VRAM 14,563 GiB là dung lượng thiết bị, không phải peak sử dụng; loss 0,578054 không chứng minh chất lượng tăng.
7. Còn thiếu xác minh độc lập resume optimizer/RNG so với chạy liên tục, reload adapter inference, base-vs-adapter evaluation, GGUF/Windows và backup local. Báo cáo đã thao tác tải ZIP không thay xác minh đường dẫn/hash bản sao Windows/Data1000.

CI của #56 báo thành công trên Linux/Windows; báo cáo trước đó ghi full Linux 819 passed, 2 skipped và test Colab sau sửa 5 passed. Đây là kết quả từ gói trước, không phải suite được chạy lại trong PR tài liệu này, không phải nghiệm thu nghiệp vụ hoặc đo máy ASUS.

## Quyết định cần chốt trước triển khai Mark

- “Đồng thuận” là nhất trí hay đa số? Quorum bao nhiêu? Abstention có tính mẫu số? Người đề xuất có bỏ phiếu không?
- Thứ tự Văn→Tìm→Kiểm→Tri→Gói là ví dụ hay bắt buộc? Bao nhiêu vòng, thời hạn nào, khi nào xác định deadlock? Quyền yêu cầu làm lại do vi phạm an toàn khác quyền giải quyết deadlock thế nào?
- Huấn được gọi khi nào, được đọc dữ liệu nào, lưu tư vấn ở đâu? Chốt nguồn và phiên bản của corpus trước ingest, không tự áp dụng tài liệu mới vào training.
- Chọn schema task/message, checkpoint, idempotency và quyền thao tác trước khi triển khai hàng đợi. Một worker tuần tự vẫn cần kiểm ngân sách/tài nguyên và phục hồi.

Các câu hỏi này không cản việc cập nhật tài liệu; chúng là cổng thiết kế cho issue triển khai kế tiếp. [Kế hoạch cập nhật](../KE_HOACH_AI_AGENT.md) giữ bốn giai đoạn Word, đề xuất đưa phục hồi tối thiểu lên giai đoạn 1 và khép bằng chứng TRAIN-03 trước pilot.

## Phối hợp và bàn giao

PR #47 còn mở, sửa tài liệu phân công; không sửa các quyết định nhân sự/model phát triển của nhánh đó. Khi tích hợp phải giữ phần cập nhật 14/09 và hòa giải thông tin lịch sử. Không sửa file thuộc #56 hoặc tác vụ trainer Windows. Mỗi gói code sau nhận main mới, claim file/SHA/test trên issue trước làm; anh Khang là người merge. Không có training mới, corpus upload mới hoặc chi phí mới trong lần đối soát này.
