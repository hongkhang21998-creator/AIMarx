# TRAIN-04 — kết quả chạy Colab A/B

Ngày chạy 2026-09-14, sau khi PR #66 merge tại main
`9c3c9b3b899ecaa22eb3e69f61a23b37969cc0a8`. Phiên Colab cũ không còn,
nên checkpoint-20 được tái tạo bằng notebook pilot đã pin, trên Tesla T4
miễn phí. Không dùng Drive, không push model và không train quá step 20.

## Cổng checkpoint

- Global step: 20.
- Validation: 20 ca, 8.803 completion token.
- Base loss: `0.6562779318347893`.
- Adapter loss: `0.4265158023940397`.
- Delta adapter trừ base: `-0.22976212944074964`.
- Adapter SHA-256:
  `fc3e47189d2b4d470a3897867238a401cc4741b603bdbdd03e9bf25e427748ac`.

## Gói A/B

Inference greedy đã hoàn tất 20 ca base và 20 ca adapter. Gói review có
20 dòng; gold và reveal không được mở trong phiên chạy.

| Gói | Byte | SHA-256 | Nội dung |
| --- | ---: | --- | --- |
| `AIMarx-TRAIN04-review-first.zip` | 9.014 | `1d8413747fe841e0ff987f9657d12afbdccd93237bedb82f25d570ea69dd37b4` | `review.jsonl` |
| `AIMarx-TRAIN04-open-after-review.zip` | 5.104 | `f9b2df32850d3c48ccd98d4190ced6bac8e2e33ed2792025c23198456355aabe` | `reveal-after-review.json`, `gold-after-review.jsonl` |

Colab đã gọi download cả hai gói. Tuy nhiên, trình duyệt trong app không
lưu chúng vào `~/Downloads`, nên chưa có bằng chứng backup local. Cần tải
`review-first`, chấm và hash nhận xét trước khi mở gói `open-after-review`.

20 smoke này là tập công khai dùng cho hồi quy, không phải test mù. Nghiệm
thu chuyên ngành cuối vẫn cần bộ kín độc lập N≥120 được duyệt và
cấp quyền riêng.
