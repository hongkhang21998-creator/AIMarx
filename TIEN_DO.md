# Tiến độ từng ngày

Cập nhật: 09/09/2026. Theo yêu cầu anh Nguyen Hong Khang: **mỗi ngày làm một ít, không chạy marathon**.

## Nhịp làm việc

- Mỗi ngày chọn **một đầu việc nhỏ cho cả dự án**, không phải một việc lớn cho mỗi agent.
- Hoàn thành tiêu chí của đầu việc thì ghi bàn giao và dừng; không tự kéo việc tiếp theo vào cùng ngày.
- Việc chưa xong chuyển sang buổi sau, không làm bù dồn. Không bắt buộc ngày nào cũng làm.
- Mỗi đầu việc nên giới hạn một sản phẩm hoặc một hành vi kiểm chứng được. Nếu quá lớn, chia nhỏ trước khi làm.
- Đây là thứ tự các buổi làm việc, không phải lịch tự động hoặc cam kết ngày hoàn thành.
- Người dùng quyết định bắt đầu buổi tiếp theo và merge PR. Không tự merge, không tự đặt lịch chạy.

## Phân công

| Người | Trách nhiệm |
|---|---|
| Codex — tổng công trình sư | Chốt hợp đồng, chia việc, kiểm tra đầu ra và tích hợp |
| Claude — triển khai lõi | API/Swarm, trạng thái, DB/migration, concurrency, phiên bản và phê duyệt |
| Gemini qua AI Studio — triển khai gói nhỏ | Dữ liệu giả lập, nội dung giao diện, mẫu theo đặc tả; code nhỏ khi có hợp đồng rõ |
| Anh Khang | Chốt yêu cầu nghiệp vụ, nghiệm thu mẫu và merge |

Gemini chưa có kết nối repo trong quy trình này. Đầu ra được anh đưa về để kiểm tra; không coi trả lời trong AI Studio là đã sửa file hoặc chạy test.

## Bảng tiến độ

Trạng thái “đã chuẩn bị” không có nghĩa đã triển khai hoặc nghiệm thu.

| Mã | Buổi | Một đầu việc | Người chính | Điểm dừng | Trạng thái |
|---|---|---|---|---|---|
| P00 | 09/09/2026 | Ghi nhịp làm việc và gói Gemini vào repo | Codex | PR tài liệu được tạo, bàn giao cho anh | Đã chuẩn bị trên nhánh PR; chờ anh merge |
| G01a | Buổi kế tiếp | Gemini tạo đúng 2 ca: trích xuất hạn rõ; soạn mới thiếu số liệu | Gemini | Trả JSON 2 ca rồi dừng | Chưa bắt đầu |
| G01b | Buổi sau | Kiểm tra 2 ca G01a | Codex | Kết luận đạt hoặc ghi đúng lỗi cần sửa | Chờ G01a |
| G01c | Khi 2 ca đầu đạt | Tạo thêm 3 ca: nguồn mâu thuẫn, hạn tương đối, thiếu người ký | Gemini | 3 ca JSON rồi dừng | Chờ G01b |
| Q01 | Buổi riêng | Kiểm tra một PR QA của Claude theo SHA mới nhất | Codex | Báo cáo kiểm tra cho một PR | Chưa lên lịch |
| S00 | Sau khi QA ổn định | Chốt một phương án thử Swarm + model local và yêu cầu môi trường | Codex | Bản cấu hình đề xuất có điểm chưa xác minh | Chưa bắt đầu |
| S01 | Buổi riêng sau S00 | Thử một task Swarm với dữ liệu giả lập | Claude | Ghi kết quả thật, RAM/thời gian hoặc lỗi cụ thể | Chờ S00 và môi trường |
| S02 | Sau S01 | Chốt hợp đồng DraftRequest/DraftResult | Codex | Một hợp đồng để Claude triển khai | Chưa bắt đầu |

Không giao cả S00–S02 trong một buổi. Thử Swarm không đi trước việc bảo đảm trạng thái/phiên bản. Các gói job/outbox, UI, DOCX sẽ được chia tiếp sau khi có bằng chứng từ S01, không áp thời hạn ngay.

## Bàn giao cuối mỗi buổi

Chỉ cần cập nhật một dòng trạng thái và phần sau, tối đa 8 dòng:

- Ngày, mã việc, người phụ trách:
- Nhánh, base SHA và phạm vi file:
- Đã làm:
- Kiểm tra thực tế và bằng chứng/link:
- Chưa kiểm tra hoặc còn lỗi:
- Việc nhỏ tiếp theo:
- Trạng thái: chưa làm / đang làm / chờ kiểm tra / đạt / bị chặn.
- Dừng ở đây; chỉ tiếp tục khi anh yêu cầu.

Trước khi code, đọc WORKLOG và các PR đang mở. Người nhận việc ghi file sở hữu để tránh đụng nhánh Claude. Không suy trạng thái PR từ tài liệu cũ.

## Tài liệu liên quan

- [Gói Gemini AI Studio](docs/handoffs/GEMINI_AI_STUDIO_WORK_PACK.md).
- [Thiết kế Agent Swarm — PR #8](https://github.com/hongkhang21998-creator/tro-ly-van-ban/pull/8): mới là thiết kế, không phải runtime đã chạy.
- [QA — Issue #5](https://github.com/hongkhang21998-creator/tro-ly-van-ban/issues/5).
- [Nhật ký phối hợp](WORKLOG.md).

## Nhật ký phiên P00

Chỉ tạo TIEN_DO.md và gói hướng dẫn Gemini trên nhánh codex/daily-small-steps từ main. Không sửa src/tests/schema/runtime, không gửi prompt tới Gemini hoặc bắt đầu task cho Claude. Tài liệu này thay nhịp “sáng sửa hết, chiều chạy model” trước đây bằng các buổi nhỏ, không dồn việc.
