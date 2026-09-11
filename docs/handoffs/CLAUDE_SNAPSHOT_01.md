# SNAP-01 — giao Claude/Opus thiết kế snapshot gateway

## Mục tiêu và base

Base main `68765bd` (PR #29). Đọc WORKLOG, TIEN_DO và PR mở trước khi nhận. Giữ UX/UI; chỉ thiết kế lõi. Chính sách: public/synthetic được xét cloud; internal/restricted/unknown giữ local. Không gửi API thật, không dùng key, không tự duyệt ngân sách.

## Phạm vi sở hữu

Nhánh riêng từ main mới nhất đã merge: `claude/snapshot-contract`. Chỉ tạo `docs/SNAPSHOT_CONTRACT.md`, `docs/handoffs/SNAP-01-result.md`. Không sửa service/web/model/DB/PolicyGate, TIEN_DO hoặc WORKLOG trong gói này để tránh chồng với Astra. Luna sở hữu `docs/qa/planning-v1/`; không sửa.

## Sản phẩm

Thiết kế schema đóng cho snapshot bất biến và phép kiểm nguồn thay đổi, phù hợp PSC-01. Chỉ rõ source document/block refs, version, classification từ DB, payload đầy đủ, hash chuẩn hóa, revision prompt/schema/model/provider/policy, TTL và trạng thái. Làm rõ version tài liệu chưa có extraction; classification thay đổi trong tương lai phải làm snapshot cũ mất hiệu lực.

Liệt kê trình tự transaction/lock khi chuẩn bị và trước dispatch; không giữ DB transaction trong network. Nguồn trộn áp nhãn hạn chế nhất, không tin nhãn từ agent. Payload không nhận lại từ caller ở execute. Chỉ rõ kết nối với grant/ledger nhưng không triển khai chúng.

## Nghiệm thu

Đưa ví dụ synthetic hợp lệ và ca bị từ chối: thiếu nhãn, nội bộ, prompt injection, đổi 1 byte, đổi nguồn/version/nhãn/model/settings, snapshot hết hạn, execute đồng thời. Phân biệt thứ chứng minh bằng test sau này với bảo đảm hiện có. Nêu chữ ký hàm dự kiến, mã lỗi và tối thiểu 10 ca test để Astra review.

## Bàn giao và điểm dừng

Ghi base thực tế, file, quyết định còn cần chốt và giới hạn vào SNAP-01-result. Tạo PR tới main, dẫn issue giao việc và không merge. Dừng sau bản thiết kế; chưa viết runtime hoặc tự mở rộng sang agent swarm.
