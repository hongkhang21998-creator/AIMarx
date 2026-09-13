# Windows — đồng bộ AIMarx và đánh giá máy train chính

Ngày 13/09/2026. Người thực hiện: Codex, theo yêu cầu anh Nguyen Hong Khang.
Base GitHub main: `380ebb41b2d79b00aeddb23e3e17639db61b99f4` (PR #50).
Nhánh bàn giao: `codex/windows-training-readiness-20260913`.
Phạm vi ban đầu: file bàn giao này. Theo yêu cầu tiếp theo hạ xuống 0.6B, PR #51
cập nhật thêm SLM_TRAINING_PLAN, KE_HOACH_AI_AGENT, TIEN_DO và WORKLOG.
Đã đối chiếu PR #47 đang mở; khi tích hợp giữ quyết định model mới và phân công
của gói đó, không ghi đè bằng tiến độ/model cũ. PR do anh Khang merge.

## Yêu cầu và kết luận

Anh Khang muốn máy Windows này là nơi train chính vì có GPU rời.
Ghi nhận Windows là máy đích mong muốn; trạng thái **chưa đủ điều kiện train
pilot Qwen3 0.6B theo kế hoạch đã giảm ngày 13/09**. Chưa kích hoạt training hoặc thay đổi
vai trò vận hành của máy Linux. Có GPU rời không đồng nghĩa đủ khả năng QLoRA.

## Đồng bộ đã thực hiện

- Checkout: `D:\Claude-cowork\tro-ly-van-ban`.
- Trước cập nhật: nhánh `claude/tien-do-ket-noi-aistudio`, commit
  `925c602ccd739c517b364a24997b61700428ae41`; working tree sạch.
- Xác minh commit cũ là tổ tiên của main mới, giữ nguyên nhánh cũ để đối chiếu.
- Đổi URL origin từ tên repo `tro-ly-van-ban` sang
  `https://github.com/hongkhang21998-creator/AIMarx.git`, fetch và tạo nhánh bàn giao
  từ origin/main. Không có merge lên main hoặc force push.
- `requirements.lock` không thay đổi giữa hai mốc; giữ venv hiện có.
- Không di chuyển dữ liệu giữa Windows/Linux, tải model, cài CUDA/PyTorch,
  đổi driver, khởi động training hoặc upload corpus.

## Phần cứng kiểm trực tiếp

| Thành phần | Kết quả ngày 13/09/2026 |
|---|---|
| CPU | Intel Core i3-12100, 4 nhân / 8 luồng |
| RAM hệ thống | 7,78 GiB hệ thống nhận |
| GPU | NVIDIA GeForce GT 710 |
| VRAM | 1.024 MiB tổng; khoảng 448 MiB đang dùng lúc kiểm |
| Driver | 456.71 |
| NVIDIA-SMI báo CUDA | 11.1; không chứng minh đã cài CUDA Toolkit |
| Python trong venv | 3.14.6 |

Kế hoạch `docs/SLM_TRAINING_PLAN.md` đã đổi từ Qwen3 1.7B xuống **Qwen3 0.6B**
theo anh Khang. Dự trù 16 GB của phương án cũ được bỏ; không coi đó là yêu cầu
tối thiểu cho 0.6B. Recipe mới thử rank 8/alpha 16, context 1.024 sau token audit;
smoke 20–50 optimizer steps chỉ sau kiểm backend và quyền dữ liệu.
GPU 1 GB hiện tại vẫn chưa có bằng chứng tương thích/đủ bộ nhớ. CPU LoRA là
hướng khảo sát riêng, chưa train hoặc đo hiệu năng; không cài stack cũ để ép GPU.

Tài liệu [bitsandbytes](https://huggingface.co/docs/bitsandbytes/main/en/installation)
được đối chiếu ngày 13/09/2026 nêu CUDA compute capability 6.0+ cho NF4/FP4 và
CUDA Toolkit từ 11.8. Chưa đo trực tiếp compute capability của card này; không
suy compute capability từ dòng CUDA Version trong NVIDIA-SMI.
[PEFT quantization](https://huggingface.co/docs/peft/developer_guides/quantization)
mô tả giảm bộ nhớ bằng QLoRA nhưng vẫn cần bộ nhớ cho model và quá trình train.

Windows hiện có thể dùng chuẩn bị/duyệt dữ liệu và chạy kiểm thử CPU.
Chưa benchmark inference model thật hoặc train trên CPU, nên không báo đạt
hiệu năng cho các công việc đó.

## Cổng dữ liệu kiểm lại tại máy Windows

- `evals.planning_v2.cli check`: 36 reference hợp lệ; training_approved=false.
- `evals.training.train02.cli check`: 120 mẫu, chia 80/20/20; cấu trúc hợp lệ,
  không cặp gần trùng bị phát hiện; 120 pending_human, 0 approved.
- `split_audit.status=blocked_dependency_46`, `export_ready=false`.
- Merge PR #50 không thay thế duyệt nhãn/quyền train/export; không tự cấp các quyền.
- `pip check`: không có dependency hỏng.
- Regression Windows bằng `.venv\Scripts\python.exe -m pytest -q` với
  `PYTHONUTF8=1`: **724 passed, 5 skipped, 1 warning trong 60,16 giây**.
  Cảnh báo deprecation alias AnyIO từ Starlette; không có test thất bại.
  Các test bị skip không tính là đã kiểm thành công. Bộ test không chứng minh
  GPU training, inference model thật hoặc toàn bộ giao diện sản phẩm đã chạy.

## Bước tiếp theo và phối hợp

1. Chuẩn bị baseline/token audit đúng 0.6B; khảo sát backend phù hợp trên Windows.
   Nếu GPU không phù hợp, báo lựa chọn thử CPU LoRA hoặc thay tài nguyên cùng các
   giới hạn đã đo. Chưa có quyết định mua/thuê hoặc trần chi phí.
2. Nếu nâng máy, kiểm GPU/VRAM, RAM, nguồn điện và khả năng lắp trước khi chọn thiết bị;
   dựng môi trường training riêng sau khi xác định GPU. Không dùng venv ứng dụng
   làm môi trường thử dependency training.
3. Hoàn tất duyệt mẫu và phụ thuộc #46 theo TRAIN-02, rồi mới chuẩn bị smoke train.
4. Ghi GPU/driver, phiên bản thư viện, đỉnh VRAM/RAM, resume/export và chất lượng
   trong bàn giao TRAIN tiếp theo trước khi đánh dấu máy train đã sẵn sàng.

Task khác cần đọc file này cùng bàn giao TRAIN-02 trước khi tiếp tục; không coi
yêu cầu chọn Windows là bằng chứng phần cứng hoặc dataset đã đạt.
