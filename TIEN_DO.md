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

Gemini đã có kết nối repo ở mức **đọc một chiều** từ 09/09/2026; xem mục "Kết nối AI Studio và GitHub" bên dưới. Đầu ra vẫn do anh đưa về để kiểm tra; **không coi trả lời trong AI Studio là đã sửa file hoặc chạy test**.

## Kết nối AI Studio và GitHub (09/09/2026)

Ghi nhận thay đổi so với câu "Gemini chưa có kết nối repo" ở bản trước.

- GitHub App **Google AI Studio** (`google-gemini`) đã cài trên tài khoản cá nhân `hongkhang21998-creator`, phạm vi **chỉ repo `tro-ly-van-ban`**; cố ý không chọn "All repositories".
- Quyền cố định của app, không giảm bớt được: đọc commit statuses/issues/metadata; **đọc và ghi** actions, administration, code, pull requests, workflows.
- Trước đó app chỉ cài trên tổ chức `Huong-dong-team`, nên repo private của tài khoản cá nhân không hiện trong danh sách import. Repo `Khang` hiện ra chỉ vì nó công khai.
- Thu hồi khi cần: GitHub → Settings → Applications → Installed GitHub Apps → Google AI Studio → Configure → Uninstall.

**Kết nối là một chiều.** AI Studio ghi rõ "Imported code won't stay synced with GitHub". Đã rà toàn bộ thanh công cụ của app: chỉ có Remix, Share, Publish, Settings; **không có nút đẩy ngược về GitHub**, cũng không có export. Import chỉ kéo một bản sao tại thời điểm bấm.

**App đã tạo nhưng không chạy được.** App `tro-ly-van-ban` trong My apps báo "Your application failed to start". AI Studio chỉ hỗ trợ web và Android app, và "will convert other apps automatically": nó tự sinh `package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`, `src/types.ts`, `src/index.css` để ép backend Python/FastAPI thành app Vite/TypeScript. Đã dừng tay giữa chừng. Anh quyết định để nguyên, tính sau.

**Đã kiểm chứng repo không bị ghi gì**, ba cách độc lập sau khi cài app: SHA của cả 11 nhánh không đổi; không có tag nào; 12 sự kiện gần nhất đều do `hongkhang21998-creator`, mới nhất 03:13 UTC trong khi app được cài khoảng 07:00 UTC.

Kết luận cho quy trình: **không đổi phân công**. Gemini vẫn không ghi vào repo; đầu ra vẫn do anh đưa về để Codex kiểm tra.

## Phân công code tuần 07–13/09/2026

Chỉ đạo mới nhất của anh Khang ngày 09/09: **Gemini làm phần code nhỏ, Claude vẫn giữ lõi**. Chỉ đạo này thay thế lựa chọn chuyển toàn bộ code sang Gemini trước đó.

- **Codex:** đặc tả, giao phạm vi file, tiêu chí nghiệm thu, kiểm thử đầu ra và phối hợp tích hợp.
- **Gemini qua AI Studio:** hàm thuần, công cụ kiểm dữ liệu giả lập, unit test nhỏ hoặc phần hiển thị đã tách riêng và có hợp đồng rõ. Mỗi gói một hành vi, ưu tiên 1–2 file; không tự mở rộng.
- **Claude:** service và state machine, DB/migration, lock/concurrency, job/outbox, adapter Swarm/API, quyền truy cập, phiên bản, phê duyệt và tích hợp mã lõi.
- **Anh Khang:** nghiệm thu nghiệp vụ và merge PR.

Trước mỗi gói Gemini, Codex cung cấp: mục tiêu; base SHA và đúng file cần đọc/được sửa; chữ ký hàm/schema; ví dụ đầu vào/đầu ra; ca đạt/trượt; lệnh kiểm tra; điểm dừng. Nếu phần UI/test nằm trong file Claude đang giữ thì chưa giao, phải tách phạm vi trước. Không để Gemini đổi Python/FastAPI sang Vite/TypeScript.

Ứng viên gói code đầu sau khi sửa và nghiệm thu lại G01a: một công cụ Python kiểm JSON fixture và quote/value, kèm test nhỏ dùng thư viện chuẩn, không truy cập DB/model/mạng. Đây là đề xuất chưa bắt đầu; Codex phải chốt hợp đồng riêng trước khi Gemini viết. Công cụ chỉ kiểm cấu trúc/nguồn, không thay kiểm ngữ nghĩa của tester.

Giữ nhịp **mỗi buổi một đầu việc nhỏ cho cả dự án**. Việc trước mắt vẫn là sửa hai ca G01a; không vừa sửa ca vừa mở gói code mới. Đầu ra Gemini phải được chạy kiểm tra thực tế trước khi đưa vào PR; không coi lời “test pass” trong chat là bằng chứng.

Nhật ký cập nhật phân công: chỉ sửa TIEN_DO.md trong PR #15 đang mở để không tạo thêm PR tài liệu trùng. Chưa giao tác vụ chạy cho Gemini/Claude, chưa sửa mã. Phân công này áp dụng trong tuần nêu trên; tuần sau xem lại cùng anh.

## Bảng tiến độ

Trạng thái “đã chuẩn bị” không có nghĩa đã triển khai hoặc nghiệm thu.

| Mã | Buổi | Một đầu việc | Người chính | Điểm dừng | Trạng thái |
|---|---|---|---|---|---|
| P00 | 09/09/2026 | Ghi nhịp làm việc và gói Gemini vào repo | Codex | PR tài liệu được tạo, bàn giao cho anh | Đã merge vào main qua PR #12 |
| G01a | 09/09/2026 | Gemini tạo đúng 2 ca: trích xuất hạn rõ; soạn mới thiếu số liệu | Gemini | Trả JSON 2 ca rồi dừng | Đã kiểm G01b: cần sửa 3 điểm trước nghiệm thu; giữ JSON gốc |
| G01b | 09/09/2026 | Kiểm tra 2 ca G01a | Codex | Kết luận đạt hoặc ghi đúng lỗi cần sửa | Đã kiểm tra; G01a cần sửa, xem [báo cáo](docs/qa/2026-09-09/G01b-nghiem-thu.md) |
| G01c | Khi 2 ca đầu đạt | Tạo thêm 3 ca: nguồn mâu thuẫn, hạn tương đối, thiếu người ký | Gemini | 3 ca JSON rồi dừng | Chờ sửa và nghiệm thu lại G01a; chưa bắt đầu |
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

## Bàn giao buổi 09/09/2026

- Ngày, mã việc, người phụ trách: 09/09/2026 — G01a do Gemini; ghi nhận kết nối AI Studio do Claude.
- Nhánh, base SHA và phạm vi file: `claude/tien-do-ket-noi-aistudio`, base `b3b34c1`; chỉ đụng `TIEN_DO.md` và thêm `docs/handoffs/G01a-ket-qua.json`. Không sửa mã nguồn.
- Đã làm: chạy G01a trên AI Studio đúng gói việc (Phần A vào System Instructions, Phần B vào chat, không upload repo), model Gemini 3.1 Pro Preview, thinking High, grounding và URL context tắt; nhận đủ JSON 2 ca. Cài GitHub App AI Studio giới hạn một repo và ghi nhận giới hạn một chiều.
- Kiểm tra thực tế và bằng chứng: quote của G01-01 là chuỗi con chính xác của block `b-01`; G01-02 có `sources: []` và 4 placeholder cho số liệu thiếu. Repo không bị ghi: 11 nhánh giữ nguyên SHA, không tag, không sự kiện từ actor Google.
- Chưa kiểm tra hoặc còn lỗi: **chưa nghiệm thu G01a — đó là việc của Codex ở G01b**. Hai điểm Codex nên xem: `approval_state` không nhất quán giữa hai ca (`pending` với `pending_user_review`); G01-01 dùng hạn `15/11/2023` lệch bối cảnh 2026. App AI Studio không build được, để nguyên theo yêu cầu của anh.
- Việc nhỏ tiếp theo: G01b — Codex nghiệm thu 2 ca theo sáu tiêu chí trong gói việc.
- Trạng thái: chờ kiểm tra.
- Dừng ở đây; chỉ tiếp tục khi anh yêu cầu.

## Bàn giao G01b — 09/09/2026

- Codex hoàn thành kiểm tra trên main `51e0c50dbdf8b7542e937a326d465394f82d17fe`; nhánh `codex/g01b-acceptance`.
- Phạm vi: TIEN_DO.md và docs/qa/2026-09-09/G01b-nghiem-thu.md; không sửa đầu ra gốc/code.
- JSON/khóa/enum đã định nghĩa đạt; 4/4 fact khớp nguồn; G01-02 có sources=[] và placeholder.
- Chưa nghiệm thu bộ: G01-02 nhầm task hoàn tất với văn bản được duyệt, sai loại báo cáo; G01-01 assertion kiểm nhầm đáp án mẫu.
- Ngày 2023 không vi phạm đề bài; approval_state chưa có enum nên cần làm rõ hợp đồng, không kết luận sai enum.
- Buổi tới chỉ sửa 2 ca bằng prompt trong báo cáo; chưa gửi Gemini hoặc mở G01c.
- Kiểm tra này là nghiệm thu dữ liệu, không chạy tính năng tạo sinh hoặc pytest.
- Dừng tại đây; người dùng merge PR và quyết định buổi tiếp theo.
