# Triển khai laptop

## Quyết định phần cứng

Laptop được kiểm tra trực tiếp: Intel i3-8130U (2 nhân / 4 luồng), RAM khả dụng toàn máy khoảng 7,1 GiB, đĩa dự án còn khoảng 175 GiB tại thời điểm kiểm tra. Máy này làm máy chủ ứng dụng theo chỉ định của người dùng.

Máy phụ do người dùng cung cấp: i3-12100, RAM 8 GB, GT 710 1 GB, Windows 11 Home. Chưa kết nối hoặc cài dịch vụ trên máy phụ. Không tự cài SSH, thay router/IP hoặc mở cổng mạng.

Ứng dụng bind loopback, một worker, dùng SQLite và file local. Không cần Docker/WSL cho laptop Linux hiện tại. Chỉ mở LAN sau khi có lớp xác thực và yêu cầu riêng. Không tự đồng bộ văn bản qua OneDrive hoặc Calendar.

## Runtime

Python 3.12 chạy trong `.venv` riêng. Model/runtime nếu cài được nằm tại `.runtime`, không đưa lên Git. Model đầu tiên thử là Qwen3 0.6B để kiểm tra đường gọi local và mức dùng RAM; chưa được công nhận đủ độ chính xác nghiệp vụ.

Ollama chính thức: https://github.com/ollama/ollama ; hướng dẫn https://docs.ollama.com/linux . Model: https://ollama.com/library/qwen3:0.6b . Không cài script có quyền root, không thay dịch vụ hệ thống. Server local cần được khởi động lại sau khi máy reboot theo README/scripts.

## Dữ liệu và backup

Kho làm việc `data/` bị loại khỏi Git. Dùng bản sao đã khử nhạy cảm khi kiểm thử. Bản gốc được giữ riêng với bản trích xuất/dự thảo.

Để sao lưu ở giai đoạn này: dừng ứng dụng, sao chép toàn bộ thư mục dữ liệu đến ổ backup, khởi động lại và kiểm tra danh sách hồ sơ. Khôi phục vào một thư mục mới và chạy thử với `TLVB_DATA` trỏ tới bản khôi phục trước khi thay kho đang dùng. Không đồng bộ DB đang ghi qua OneDrive.

## Các bước chưa triển khai

Chưa có truy cập máy phụ, tự khởi động sau reboot, OCR Docling, mẫu nghiệp vụ do người dùng cung cấp, theo dõi thư mục, Google Calendar hoặc fine-tune. Từng phần được mở bằng PR riêng sau pilot bản local.
