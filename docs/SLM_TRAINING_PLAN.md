# Kế hoạch fine-tune SLM cho AIMarx

Khởi lập 12/09/2026 · Astra · mở rộng PR #45 về điều phối tuần tự.
Cập nhật 13/09/2026 theo anh Khang: **chỉ Qwen3 0.6B, non-thinking** cho vòng đầu.
Trạng thái: **điều chỉnh kế hoạch để review; chưa train hoặc phát sinh chi phí**.
Mốc main đã đối chiếu: `380ebb4` (TRAIN-02, PR #50 đã merge).
Quyết định 0.6B này thay các đề xuất model lớn hơn trong kế hoạch cũ.

## 1. Mục tiêu và giới hạn của lần train đầu

Huấn luyện bổ sung bằng SFT/LoRA trên model có sẵn để làm tốt một việc hẹp:
đọc yêu cầu cùng các đoạn nguồn được chọn, đề xuất chuỗi bước có thứ tự, chọn worker
trong danh sách cho phép và chỉ ra thông tin cần hỏi. Không huấn luyện nền từ đầu.
Không lấy tên AIMarx làm yêu cầu nạp corpus tư tưởng/chính trị vào model.

Đích nghiệm thu: công văn yêu cầu báo cáo nhưng thiếu số liệu → nhận diện sản phẩm,
trích căn cứ, hỏi số liệu thiếu, đề xuất khung báo cáo, kiểm nguồn và trình người duyệt.
Không bịa số liệu, thời hạn hoặc giả vờ đã chạy worker.

SLM sinh **proposal**. Backend giữ hàng đợi một worker, cấp trạng thái/số lần thử,
lưu checkpoint nghiệp vụ, kiểm phiên bản/nguồn/quyền/ngân sách và cho phép chuyển bước.
Train không thay thế scheduler, persistence, ledger, adapter hay đăng nhập. Không cho
model sinh shell, URL gọi mạng, token, quyền tự cấp, phê duyệt hay lệnh mở agent mới.
Một model có thể lần lượt đóng nhiều vai trò; không nạp nhiều SLM cùng lúc.

## 2. Những gì đã có và còn thiếu

| Thành phần kiểm trực tiếp | Hiện trạng / cách dùng |
|---|---|
| `docs/qa/planning-v1/cases.json` | 6 ca giả lập: thiếu số liệu, hạn tương đối, hạn mâu thuẫn, không có việc, injection, nguồn trộn |
| `evals/planning/score.py` | Chấm 6 trường; `suggested_steps` hiện là danh sách chuỗi, chưa có schema step/worker/depends_on |
| `evals/extraction/cases.json` | 18 ca gồm dev/test/test2, dành regression trích xuất; không phải 18 kế hoạch gold |
| Model local | Cấu hình Qwen3 0.6B; vòng này chỉ đo base 0.6B so với bản fine-tune 0.6B, chưa có benchmark mới |
| Ledger | Đã merge #44; không đồng nghĩa đã có adapter mạng hoặc scheduler chạy được |
| Dataset train / notebook / artifact | Chưa có bộ train được duyệt, chưa có training job/model AIMarx đã fine-tune |
| TRAIN-01 / TRAIN-02 tại main #50 | 36 reference proposal-v2; 120 draft smoke (80/20/20), 0 approved; split audit còn blocked_dependency_46, export_ready=false |

Giữ 6 + 18 ca hiện có làm regression/reference. Vì đã đọc chúng để thiết kế prompt
và schema, không gọi chúng là test mù độc lập. Không lẫn đáp án `expected`/`gold`,
`must_not_do` của evaluator vào đầu vào inference. Bộ test mới phải được giữ riêng.

## 3. Model và phần cứng

**Model train duy nhất của vòng đầu: `Qwen/Qwen3-0.6B`, `enable_thinking=False`.**
Đây là quyết định giảm quy mô của anh Khang ngày 13/09/2026. Baseline vẫn bắt buộc
để đo chất lượng; không dùng baseline để tự nâng model lên kích thước lớn hơn.

| Vai trò | Model / điều kiện |
|---|---|
| Baseline sản phẩm | Qwen3 0.6B hiện có, cùng prompt/schema đã chốt |
| Ứng viên fine-tune | Cùng base Qwen3 0.6B, pin revision; bản inference Q4_K_M đo riêng trên Windows và ASUS |
| Phạm vi benchmark | Base 0.6B so với fine-tuned 0.6B; model lớn hơn nằm ngoài vòng này |
| Nếu 0.6B không đạt | Báo lỗi và thu hẹp tác vụ/context có kiểm chứng; không tự đổi model hoặc hạ chuẩn nguồn/quyền |

Máy đã đo: i3-8130U, 2 nhân/4 luồng, UHD 620, hệ thống nhận 7,1 GiB RAM. Mức
available 3,2 GiB là ảnh chụp một thời điểm, không là ngân sách cố định. Đã từng OOM.
ASUS dùng soạn/kiểm dữ liệu và inference từng yêu cầu; không chọn máy này làm máy
train GPU. RAM hệ thống không tương đương VRAM CUDA. Dung lượng GGUF không phải
đỉnh RAM ứng dụng.

Windows là máy đích anh muốn dùng train chính. Kiểm ngày 13/09: i3-12100, RAM
7,78 GiB, GT 710 chỉ 1.024 MiB VRAM, driver 456.71. **Chưa đạt training-ready**;
giảm xuống 0.6B không chứng minh GPU/driver tương thích hoặc đủ VRAM cho QLoRA.
Bỏ dự trù 16 GB của phương án cũ; không thay bằng một mức VRAM tối thiểu chưa đo.
TRAIN-03 phải kiểm backend/GPU trước khi tải model, sau đó smoke 20–50 optimizer
steps trên tài nguyên phù hợp, đo VRAM, host RAM và thời gian trước pilot.
CPU LoRA trên Windows là hướng cần khảo sát tính khả thi riêng, chưa có benchmark
hoặc cam kết vừa RAM/tốc độ; không tự chuyển sang CPU khi GPU thất bại.
Trên GPU không hỗ trợ BF16 chọn FP16 đã thử tương thích. Merge/export cũng cần
đo host RAM/disk; không ép nạp bản đầy đủ khi thiếu bộ nhớ.

[Model card Qwen3-0.6B](https://huggingface.co/Qwen/Qwen3-0.6B) xác nhận model 0.6B
và hỗ trợ `enable_thinking=False`. Fine-tune/export phải kiểm với đúng base này;
không coi file GGUF inference là trọng số dùng để train.

## 4. Hợp đồng dữ liệu cần chốt trước khi sinh dataset

Gói TRAIN-01 tạo schema **proposal-v2** riêng; không âm thầm thay scorer planning-v1.
Các trường dưới đây là đề xuất để đóng schema, chưa là API runtime:

- Top-level: `schema_version`, `decision` (plan/ask/no_action/out_of_scope),
  `requested_product`, `evidence_quotes`, `missing_information`, `steps`.
- Step: `id`, `goal`, `worker_id`, `depends_on`, `source_refs`, `input_refs`,
  `output_schema_id`, `completion_checks`.
- `source_refs` dùng ID/phiên bản/block thật trong input. `input_refs` chỉ trỏ input
  hiện có hoặc output của bước trước. ID không trùng, không chu trình, không forward
  reference. Đề xuất tối đa 6 bước ở pilot; bài dài phải thu hẹp phạm vi/hỏi lại.
- Worker allowlist dự kiến: extract, ask_user, draft, verify. Đây là ID vai trò để
  thiết kế, chưa tuyên bố đã có worker tương ứng. Backend quyết định model và quyền.
- `state`, `attempts`, thời gian chạy, kết quả duyệt, grant/budget và quyền thực thi
  **không nằm trong target model**: backend cấp khi nhận proposal hợp lệ.
- `cloud_eligible` của fixture cũ chỉ dùng đánh giá/phân loại tham khảo. Quyền gửi
  do policy gate kiểm từ nhãn nguồn backend; không học một boolean như giấy phép gửi.
- Với ask_user: backend lưu trạng thái chờ người dùng; chỉ tiếp tục sau khi có dữ
  liệu và kiểm lại kế hoạch/nguồn. Không bắt model tự điền câu trả lời vào target.

Bản dataset JSONL gồm metadata tách khỏi `prompt`/`completion`: sample_id,
source_family_id, template_family_id, split, quyền sử dụng/xuất dữ liệu, source_hash,
reviewer, reviewed_at, schema/prompt version. Trainer chỉ đọc các trường model cần.
Gold completion là JSON proposal đã duyệt, không chứa state thực thi hoặc log riêng.
Dạy câu trả lời có cấu trúc và lý do kiểm chứng ngắn khi schema cần; không dùng
chuỗi suy nghĩ nội bộ dài làm nhãn train.

## 5. Chuẩn bị dataset và chống rò đáp án

### Hai quy mô thử

1. **Smoke dataset 120 mẫu**: dự kiến 80 train / 20 validation / 20 test theo nhóm
   nguồn. Chỉ kiểm pipeline, mask, overfit và export; không tuyên bố đủ chất lượng
   dùng thật từ 20 test. Dữ liệu này không được tái sử dụng như test mù của pilot sau.
2. **Pilot 800–1.200 mẫu đã duyệt**: chia khoảng 70/15/15 theo family; tập test độc
   lập tối thiểu 120 mẫu. Số mẫu là mục tiêu chuẩn bị, không bảo đảm model sẽ học được.
   Nếu thiếu chất lượng/độ đa dạng, bổ sung có mục tiêu theo lỗi validation.

Phân bố đề xuất: 30% yêu cầu rõ và đủ nguồn; 25% thiếu dữ liệu/cần hỏi;
15% nhiều bước phụ thuộc; 10% hạn tương đối/mâu thuẫn; 10% không có việc/ngoài phạm vi;
10% injection, đòi tự duyệt, đòi gửi nội bộ ra cloud. Các ca nguồn trộn, bảng số liệu,
định dạng khác nhau được rải trong nhiều nhóm. Nguồn benchmark đối kháng được đánh
nhãn synthetic thật, dù nội dung mô phỏng văn bản hạn chế.

- Gom cùng hồ sơ, bản sửa, template và bản paraphrase vào một family trước khi
  chia tập. Near-duplicate check và rà soát chéo nguồn giữa các split.
- Tách tập trước khi tăng cường dữ liệu; chỉ sinh biến thể trong train. Không lấy
  6 ca cũ rồi đổi tên/ngày để tạo cả train và test.
- Astra/Claude có thể dự thảo gold synthetic; người dùng/người được giao nghiệp vụ
  phải duyệt nhãn trước khi đưa vào pilot. Chưa duyệt → quarantine, không train.
- Không dùng output chưa duyệt, toàn bộ audit log hoặc việc bị từ chối làm positive
  target. Cặp sai→sửa dùng phân tích lỗi hoặc chuyển thành input→gold đúng; DPO/RL
  chưa thuộc vòng đầu.
- Test mù không đưa cho model sinh train hoặc dùng chọn checkpoint/hyperparameter.
  Một evaluator giữ bộ test và chỉ mở sau khi khóa candidate. Các lần thử sau cần
  ghi việc đã nhìn test; khi dùng lỗi test để sửa, cần test mới độc lập.
- Đáp án/người chấm phải phân biệt đúng nguồn chữ với đúng ý nghĩa công việc.
  Không lấy substring match hoặc hai model đồng ý làm nhãn nghiệp vụ đúng.

Chỉ đóng gói dữ liệu synthetic/public có quyền dùng để train và quyền xuất đã duyệt.
Nhãn internal/restricted/unknown giữ local; không coi việc khử tên là tự nâng quyền.
Export train là quyền riêng, không kế thừa grant gọi API. Không upload corpus thật
hoặc checkpoint chứa dữ liệu đó, không tự publish model lên Hub/Ollama.

## 6. Recipe pilot có thể tái lập

### Chế độ Windows chậm, có điểm dừng — yêu cầu 13/09/2026

Ưu tiên mới: giảm tải máy, lưu được tiến độ và kiểm trước khi tăng khối lượng.
Các giá trị dưới đây là **đặc tả cần triển khai và đo**, chưa có trainer/giám sát
tài nguyên hoạt động. Chạy chậm không tự làm giảm lượng RAM cần để nạp model,
không sửa được GPU không tương thích và không bảo đảm chất lượng model.

- Khảo sát **CPU LoRA** trong môi trường training riêng, giữ base 0.6B đóng băng;
  không mặc định ép GT 710 chạy CUDA. FP32 là cấu hình tương thích để khảo sát CPU,
  chưa chọn BF16/FP16 trên CPU khi chưa kiểm hỗ trợ và tính ổn định.
- Bắt đầu 2 CPU compute threads, 1 interop thread, DataLoader workers=0,
  ưu tiên tiến trình BelowNormal, microbatch=1, gradient checkpointing và
  use_cache=false. Giới hạn threads/priority không phải giới hạn cứng CPU%/nhiệt độ.
  Giữ rank=8/alpha=16, context=1.024 sau token audit; không giảm context bằng cắt gold.
- Learning rate 5e-5 cho lượt thử bảo thủ; warmup 10%, max_grad_norm=1.0.
  Learning rate thấp không thay thế giới hạn tài nguyên hoặc chứng minh học tốt hơn.
  Accumulation=16 chỉ gom gradient, không coi là giảm RAM so với microbatch=1.
- Trước nạp: RAM khả dụng ít nhất 4 GiB và đĩa trống ít nhất 15 GiB là cổng
  vận hành tạm thời, **không cam kết đủ**. Đo đỉnh RAM riêng ở nạp, forward/backward
  và lưu checkpoint. Chặn bắt đầu nếu không đạt; không tự đóng ứng dụng của anh.
- Khi chạy: kiểm RAM ít nhất mỗi giây và giữa microsteps; dừng trước bước kế
  tiếp khi RAM khả dụng <1,5 GiB, đĩa trống <10 GiB, loss/gradient không hữu hạn,
  hoặc lỗi lưu checkpoint. Watchdog ở ngoài trainer cần bảo vệ cả giai đoạn nạp.
  Đây là giám sát best-effort, không chặn tuyệt đối được mọi đỉnh RAM trong kernel.
- Thử 1 optimizer step và checkpoint trước; mở tiến trình mới để kiểm resume,
  rồi mới 5 steps. Sau hai cổng này mới smoke 20–50 steps; mỗi phiên thử tối đa
  30 phút, dừng tại ranh giới bước. Watchdog có thể buộc dừng nếu bước bị treo;
  lúc đó chỉ hứa khôi phục checkpoint hợp lệ gần nhất, mất phần đang tính là có thể.
- Lưu mỗi optimizer step ở thử 1/5 steps, mỗi 5 steps ở smoke; checkpoint phải
  có adapter, optimizer/scheduler, RNG, bước/data cursor, config và hash dataset/base.
  Ghi vào thư mục tạm cùng volume, xác minh xong mới đổi tên/đánh dấu hoàn chỉnh.
  Giữ 2 checkpoint hoàn chỉnh gần nhất, chỉ dọn checkpoint cũ của đúng run sau
  khi bản mới được kiểm; không ghi đè model gốc hoặc artifact người dùng.
- Chỉ lưu ở ranh giới optimizer step khi gradient accumulation đã hoàn tất;
  Ctrl+C dừng có kiểm soát, mất điện/process kill có thể mất phần sau checkpoint.
  Không tự bật chạy qua đêm, tự khởi động lại hoặc chuyển backend khi thất bại.
- Chưa đo được nhiệt CPU bằng cảm biến đáng tin cậy trong phiên này; không báo
  “đã giám sát nhiệt” hoặc “an toàn tuyệt đối”. Nếu máy giật/treo/thermal throttling,
  dừng để kiểm tra. Thử CPU không thay đổi BIOS, driver, pagefile hoặc power plan.

Kiểm trực tiếp ngày 13/09/2026: RAM khả dụng khoảng **2,1 GiB**, đĩa D còn
73,4 GiB; venv ứng dụng Python 3.14.6 chưa có torch/transformers/peft. Cổng RAM
tạm thời chưa đạt. Riêng 0,6 tỷ trọng số FP32 khoảng 2,4 GB (2,24 GiB), chưa
tính activation/runtime/các bản sao lúc nạp; không hứa train vừa máy 8 GB.
TRAIN-02 kiểm lại vẫn 120 pending_human, 0 approved, blocked_dependency_46.
Vì vậy **chưa khởi chạy train**, chưa cài stack hoặc tải model trong lần này.

Thứ tự: hoàn tất quyền/kiểm dữ liệu → chuẩn bị môi trường riêng và kiểm RAM →
nạp + 1 step/checkpoint → resume + 5 steps → smoke ngắn → đánh giá rồi mới pilot.
Các cổng của mục này ưu tiên hơn recipe GPU chung bên dưới khi thử trên Windows.

Nguồn kỹ thuật: [PEFT LoRA](https://huggingface.co/docs/peft/package_reference/lora)
và [Transformers Trainer](https://huggingface.co/docs/transformers/main_classes/trainer).
Ngưỡng RAM/thời gian là lựa chọn bảo thủ của dự án để thử, không phải bảo đảm của thư viện.

Ưu tiên SFT với PEFT QLoRA; Unsloth là lựa chọn thực thi sau smoke, không thay đổi
hợp đồng dữ liệu và bộ chấm. [PEFT quantization](https://huggingface.co/docs/peft/developer_guides/quantization)
mô tả huấn luyện adapter trên nền lượng tử hóa; không dùng trực tiếp file GGUF
Q4_K_M của Ollama làm trọng số train.

Cấu hình **khởi điểm để kiểm chứng**, không phải cấu hình tối ưu đã đo:

| Tham số | Pilot đề xuất |
|---|---|
| Base | Qwen/Qwen3-0.6B; pin revision SHA, tokenizer và chat template non-thinking |
| Quant train | 4-bit NF4 + double quantization, dtype theo GPU |
| LoRA | r=8, alpha=16, dropout=0,05; cần xác minh target attention/MLP linear với model 0.6B trước train |
| Context train | Bắt đầu 1.024 token tổng prompt + completion nếu mẫu vừa; 2.048 chỉ sau đo bộ nhớ, chưa mở 4.096 ở vòng đầu |
| Batch | Microbatch 1, accumulation 16, gradient checkpointing |
| Learning rate | 1e-4 khởi điểm; tối đa một thử 5e-5 nếu validation cho thấy cần |
| Epoch | 1 trước; tối đa 3 theo validation, không train kéo dài chỉ vì train loss giảm |
| Loss | Chỉ completion JSON; kiểm label mask, EOS và phần prompt không tính loss |
| Packing | Tắt ở smoke để dễ kiểm mask; chỉ bật khi chứng minh không trộn target |
| Lưu | Checkpoint mỗi khoảng 25–50 optimizer steps; giữ tối đa 2 checkpoint tốt/cần resume |
| Tái lập | Seed cố định, manifest dataset/hash/split, config, base revision, dependency lock, GPU/driver, log metrics |

Dùng prompt-completion dataset và cấu hình loss phù hợp của [TRL SFTTrainer](https://huggingface.co/docs/trl/sft_trainer).
Nếu dùng chat dataset với assistant-only mask phải xác minh chat template hỗ trợ;
không gắn cờ rồi giả định mask đúng. Pin thư viện sau smoke, không dùng `latest`
không kiểm soát hoặc tự sửa dependency runtime của AIMarx.

Training và inference phải cùng cách serialize nguồn, schema và non-thinking
chat template. Không cắt âm thầm phần cuối gold khi quá context: loại/thu nhỏ mẫu
có ghi nhận hoặc thiết kế bước theo đoạn. Tắt telemetry dataset và auto push_to_hub.
Trước smoke, đo độ dài token của toàn bộ mẫu bằng tokenizer đã pin, báo số mẫu
vượt 1.024/2.048 và phân bố theo nhóm/split. Không sửa gold/schema hoặc loại mẫu
khó âm thầm để vừa cấu hình nhỏ; thay mẫu cần duyệt lại, mẫu test không dùng để tune.
Checkpoint để resume train cần optimizer/scheduler/RNG state; phân biệt với adapter
nhỏ dùng inference. Thử dừng/khôi phục một lượt smoke trước pilot thật.

Chỉ train một candidate chính mỗi vòng. Không sweep hàng chục tổ hợp khi chưa chứng
minh baseline yếu ở lỗi có thể học từ dữ liệu. Fine-tune không bảo đảm suy luận tốt
hơn, tiết kiệm RAM hơn hay xử lý dài hơn cùng kiến trúc/context.

## 7. Nơi train, ngân sách và điểm dừng

**Ưu tiên máy Windows theo yêu cầu anh Khang; chưa chốt backend train khả thi hoặc
duyệt phí.** Kiểm phần cứng trước; các phương án GPU bên ngoài chỉ là dự phòng
cần quyết định riêng. Việc này không ngăn chuẩn bị schema, dataset và baseline local.

| Phương án | Cách triển khai | Điều kiện trước khi chạy |
|---|---|---|
| Windows local ưu tiên | Qwen3 0.6B; khảo sát backend và bộ nhớ trước smoke | GT 710 1 GB chưa được xác nhận phù hợp; CPU LoRA chỉ sau khảo sát và chốt recipe riêng |
| GPU miễn phí, ví dụ Colab | Notebook private, dữ liệu đã duyệt; checkpoint ra kho bền vững được chọn | Kiểm GPU được cấp và hạn phiên, xác nhận quyền upload, smoke/resume được |
| GPU thuê | Một GPU phù hợp pilot; tắt máy sau job và export | Anh duyệt provider/vùng dữ liệu và trần chi phí cụ thể sau khi có báo giá |

[Colab FAQ](https://research.google.com/colaboratory/faq.html) nêu tài nguyên/giới hạn
không được bảo đảm cố định; không hứa luôn có T4 hoặc một số giờ GPU miễn phí.
Không lấy Colab làm máy chủ runtime AIMarx.

Trước lần thuê đầu, báo giá hiện hành và duyệt riêng trần thời gian/chi phí cho
smoke; nếu chưa đo tốc độ, dùng một phiên ngắn có thời hạn cứng, không tự nối dài.
Sau smoke, dự trù pilot theo **giá giờ × số giờ dự trù + disk/storage + phí truyền
dữ liệu nếu có**. Số giờ suy từ 20–50 bước smoke và tổng token/optimizer steps,
cộng phần đánh giá/export; không báo tiền chỉ từ số mẫu. Trần chi phí chưa
được duyệt nghĩa là không được khởi chạy máy trả phí; ngân sách ledger hiện tại
không tự cấp quyền thuê GPU.

Dừng khi OOM lặp, loss không hữu hạn, mask sai, test split rò, checkpoint không
resume, vượt trần thời gian/chi phí hoặc validation xấu hơn baseline. Lưu báo cáo
lỗi và artifact hợp lệ, không tự đổi sang GPU đắt hơn hoặc tải dữ liệu lên nơi khác.

## 8. Nghiệm thu chất lượng và chạy lại trên ASUS

Khóa prompt/schema, cấu hình decode và dữ liệu trước khi so sánh. Đo hai cặp:
base chưa fine-tune so với adapter/merged cùng precision trên máy train; sau đó
base GGUF Q4 so với fine-tuned GGUF Q4 trên ASUS. Nếu khác quantization phải ghi rõ,
không quy toàn bộ chênh lệch cho training.

Ngưỡng dưới đây là **đề xuất cần khóa tại TRAIN-01**, không là số liệu đã đạt:

| Chỉ tiêu trên test mù N≥120 | Cổng pilot |
|---|---|
| JSON/schema không grammar | ≥95%; công bố cả tử số/mẫu số |
| Kế hoạch đúng nghiệp vụ và thứ tự phụ thuộc | ≥90%, người chấm theo rubric |
| Hỏi đủ thông tin thiếu quan trọng | Recall ≥90% trên riêng nhóm cần hỏi |
| So với base chưa fine-tune cùng điều kiện | Giảm ≥20% số kế hoạch sai; nếu base gần hết lỗi, không lấy train loss làm lý do thay model |
| Bịa dữ kiện/hạn quan trọng | 0 ca chấp nhận trong test; có lỗi phải sửa và đánh giá lại |
| ID/nguồn/worker ngoài danh sách, vượt quyền | Backend chặn 100% ca kiểm; công bố riêng tỷ lệ proposal sai, không giấu sau validator |
| Regression 6 planning + 18 extraction cũ | Không làm xấu chức năng đang dùng; công bố từng nhóm |
| Tác dụng phụ lượng tử hóa | Đánh giá lại toàn bộ tiêu chí trên bản GGUF được đưa về máy |

Báo số mẫu theo từng nhóm, sai sót cụ thể và khoảng bất định (ví dụ Wilson cho tỷ
lệ). Không suy “an toàn 100%” ngoài bộ test. Chấm tự động dùng schema/citation/ID;
chấm ý nghĩa do người đối chiếu hoặc rubric có kiểm tra độc lập. Model judge chỉ hỗ
trợ, không tự quyết đạt. Ghi cả raw output và output sau grammar/validator.

Cổng tài nguyên đề xuất trên ASUS: một model/worker, context 2.048 rồi 4.096 nếu
đủ; đầu ra tối đa 1.024 token cho plan ngắn. Thử 2 và 4 CPU threads rồi chốt một
cấu hình. Đo RSS/PSS của Ollama runner + server + ứng dụng, MemAvailable toàn máy,
swap-in/out, OOM, p50/p95 và thời gian người dùng sửa. Tách cold-load/warm-run;
đo latency lặp trên tập hiệu năng riêng, không dùng test mù để tune.

Mục tiêu tạm: tổng model/runtime ≤3 GiB, MemAvailable còn ≥0,75 GiB, không OOM hoặc
swap tăng kéo dài; p95 ≤60 giây cho plan ngắn. Đây là cổng để thử khả năng dùng,
không phải hiệu năng đã đo. Nếu không đạt, rút context/phạm vi hoặc chọn SLM nhẹ
hơn, không âm thầm tăng swap và gọi đó là đạt. Với 120+ ca nghiệp vụ, báo đúng số
lượt model, nhiệt độ máy và tải nền khi đo.

## 9. Xuất model, rollback và bật dùng

Lưu adapter riêng + base/tokenizer revision, sau đó merge với đúng base precision
phù hợp trên máy train, export GGUF và quantize Q4_K_M. Xác minh đường export bằng
smoke ngay từ đầu, không chờ train đầy đủ rồi mới phát hiện không nạp được.
[Ollama import](https://docs.ollama.com/import) yêu cầu đúng base cho adapter và có
đường import GGUF; danh sách kiến trúc hỗ trợ adapter không đồng nghĩa mọi Qwen
adapter/QLoRA đều nạp trực tiếp được. Ưu tiên kiểm đường merged-model→GGUF thực tế.

Artifact bàn giao: adapter, manifest, checksum SHA-256, tokenizer/chat template,
config decode, báo cáo trước/sau train/quantization, model card nội bộ và cách resume.
Không đưa trọng số/dataset lớn vào Git. Đặt model thử bằng tag mới, ví dụ
`aimarx-planner-v0.1-candidate`, giữ nguyên model cũ để rollback bằng cấu hình.

Ban đầu chỉ **shadow mode**: đề xuất, chấm, người xem; không dispatch tool. Đưa vào
runtime sau khi scheduler một worker, checkpoint nghiệp vụ, gate quyền/ledger,
adapter và bước duyệt đã có test end-to-end. Training có thể chuẩn bị/chạy offline
trước adapter, nhưng không bỏ các cổng HOS-01–05 khi bật thực thi.

## 10. Gói triển khai và nhịp tăng tốc

Không cần chờ toàn bộ cloud hoàn thành mới chuẩn bị dataset. Cập nhật này cho phép
bắt đầu HOS-02/03 và chuẩn bị HOS-06 offline theo cổng dưới đây; không tuyên bố đã
triển khai HOS-04 chỉ vì model được fine-tune. Những phụ thuộc dùng thật vẫn giữ.

| Gói | Phụ trách đề xuất | Sản phẩm / điểm dừng |
|---|---|---|
| TRAIN-01 | Astra | Chốt proposal-v2, rubric, split/rights manifest, baseline protocol; schema/scorer mới có test; chưa train |
| TRAIN-02 | Claude/Opus + anh duyệt nghiệp vụ | Dataset tooling và 120 mẫu smoke được duyệt, kiểm near-duplicate/mask; không sửa ledger |
| TRAIN-03 | Astra | Chỉ Qwen3 0.6B: baseline, token-length audit, kiểm backend trên Windows, chốt tài nguyên; smoke train/export/resume sau quyền tài nguyên/dữ liệu |
| TRAIN-04 | Claude/Opus + anh duyệt | Pilot 800–1.200 gold và recipe tái lập; chỉ dùng train/validation để chọn candidate |
| TRAIN-05 | Astra, anh chấm nghiệm thu | Test mù, so base/GGUF trên ASUS, báo go/no-go; chỉ tạo candidate/shadow |

Astra phù hợp phần ML/schema/evaluation và quyết định model; Claude/Opus phù hợp
pipeline/train tooling sau hợp đồng. Đây là đề xuất phân công, **chưa khởi chạy agent
hay giao nhiều tác vụ đồng thời**. Mỗi gói ghi base SHA, file sở hữu và bàn giao,
PR riêng từ main đã merge; anh merge. Các file ledger thuộc gói khác, tránh chồng.

Ước lượng lập kế hoạch: 1–2 buổi chốt schema; 2–4 buổi cho smoke dataset/tooling;
1–2 buổi baseline và smoke train/export nếu đã có GPU. Đó là mốc thử pipeline,
không phải model đã đủ dùng. Với pilot, riêng duyệt 800–1.200 mẫu ở 1–3 phút/mẫu
đã khoảng **13–60 giờ**; phải đo tốc độ duyệt thực tế rồi chốt lịch. Số giờ GPU
chỉ ước lượng sau smoke. Tăng tốc bằng mục tiêu hẹp và batch duyệt rõ, không hứa
hoàn thành train chất lượng nghiệp vụ trong một ngày.

**Việc tiếp theo tại mốc #50:** hoàn tất duyệt TRAIN-02 và phụ thuộc #46; chuẩn bị
TRAIN-03 cho đúng 0.6B, kiểm backend và độ dài token trước smoke. TRAIN-01 đã có
schema/36 reference, không làm lại. Chưa có training job hoặc model fine-tuned.
