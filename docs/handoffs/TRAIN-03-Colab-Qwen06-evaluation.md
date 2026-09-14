# TRAIN-03 — reload và đánh giá adapter trên Colab T4

Ngày 14/09/2026, sau khi PR #56 và #57 đã merge, lượt smoke được chạy lại trên
Colab T4 miễn phí. Checkpoint-1 được tạo và một process mới resume đến
checkpoint-5. ZIP local có SHA-256
`a9be6d2bb38b089b7384f3c1bdc5d681b2fc5fcc403285904afc7df339f8aa1d`;
16 file checkpoint-5 khớp manifest. Adapter có SHA-256
`df47b36bb75edf8237aa9effe81c0e10bc22b993f48fe9bccbc078e093173a48`.

Công cụ evaluation ở commit `f7e6808dbc913d3ca16d3433d7f70b4e408725f0` kiểm lại
manifest rồi nạp model gốc và adapter bằng PEFT ở chế độ inference-only. Cả hai
được đo completion-only trên cùng 20 validation, 8.803 completion token, FP16.
Model gốc có loss 0,6562779318; adapter có loss 0,5426937412; chênh lệch
adapter trừ base là -0,1135841906. Perplexity tương ứng 1,9276042909 và
1,7206355721. JSON gốc đã được chép nguyên số vào file cùng tên trong thư mục
handoff.

Kết quả xác nhận checkpoint có thể reload và loss validation giảm ở smoke 5
bước. Nó chưa đo chất lượng nghiệp vụ, độ đúng nguồn, hành vi trên 20 smoke-test
hoặc khả năng chạy Windows. Không dùng kết quả này để tự động chọn số step cho
pilot dài; cần thiết kế evaluation sinh đầu ra và anh duyệt trước.

Không mua compute, không mount Drive, không push model lên cloud và không export
20 smoke-test. Phiên Colab hiển thị 0 compute unit và T4 miễn phí.

## Hoàn thiện PR sau đối soát

Đã hòa giải với main `f140d21` chứa notebook lưu từ Colab. Notebook được đưa về
trạng thái chưa chạy; kết quả số giữ ở handoff và lịch sử Git. Pin code mới
`6cc93935e68d4dda263a935f78704c657db610e8` bổ sung kiểm file validation thực tế,
config cố định, identity checkpoint và file bắt buộc trước nạp model. Phép tính
loss giữ nguyên so với lượt T4 ghi trên; không gọi kết quả cũ là lượt GPU mới.
Thứ tự notebook: chuẩn bị → step 1 → resume step 5 → evaluation → ZIP.

Hash manifest chứng minh tính toàn vẹn so với manifest, không thay chữ ký hoặc
nguồn tin cậy. Chỉ dùng checkpoint do quy trình đã biết tạo ra. Giảm loss trên
20 mẫu chưa bảo đảm câu trả lời đúng nghiệp vụ hoặc tổng quát hóa tốt.
