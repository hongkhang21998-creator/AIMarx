# G01b — nghiệm thu hai ca Gemini

Ngày 09/09/2026. Baseline main: `51e0c50dbdf8b7542e937a326d465394f82d17fe`.
Phạm vi đúng TIEN_DO: kiểm G01a, ghi lỗi và dừng. Không tạo thêm ca G01c, không sửa ứng dụng hoặc đầu ra gốc.

## Kết luận

**G01b đã hoàn thành kiểm tra; G01a cần sửa trước khi nghiệm thu.** Không đồng nhất “đã tạo đủ 2 ca” với “2 ca đã đạt”. G01c tiếp tục chờ.

Nguồn đối chiếu: TIEN_DO.md, docs/handoffs/GEMINI_AI_STUDIO_WORK_PACK.md, docs/handoffs/G01a-ket-qua.json trên SHA baseline.

## Kiểm tra bằng máy

Đã JSON.parse đầu ra và kiểm khóa cấp ca, khóa initial_state, ID, category/priority, tham chiếu source/block, quote trong nguồn và value trong quote bằng JavaScript trong phiên tester.

- Đúng 2 ca, ID G01-01/G01-02; đúng 11 khóa cấp ca và 3 khóa initial_state.
- Category và priority thuộc enum đã giao.
- Cả 4/4 expected_facts có nguồn hợp lệ, quote nguyên văn và value nằm trong quote.
- Hai fact nguồn brief có source_id/block_id=null.
- G01-02 có sources=[] và 4 placeholder, trong đó đủ hai số liệu bắt buộc đang thiếu.
- Đếm gần đúng theo khoảng trắng trên JSON: 142 và 209 đơn vị; không thấy vi phạm giới hạn 350 từ. Đây không phải đếm token.

Đây là kiểm dữ liệu và hợp đồng, **không phải chạy tính năng tạo sinh**. Không chạy lại pytest/browser/Ollama vì không sửa mã và việc buổi này chỉ là nghiệm thu fixture.

## Sáu tiêu chí của gói việc

| Tiêu chí | Kết quả |
|---|---|
| JSON, khóa/ID/enum đã định nghĩa | Đạt; approval_state chưa có enum trong đề bài |
| Quote/value và tham chiếu nguồn | Đạt 4/4 |
| Soạn mới không có nguồn | Đạt ở đặc tả ca G01-02; chưa chứng minh ứng dụng chạy được |
| Số liệu thiếu thành placeholder | Đạt ở dữ liệu mẫu |
| Assertions quan sát được, không đoán API/DB | Cần sửa G01-01: assertion nhắm nhầm expected_facts |
| Người dùng duyệt, không tự phát hành | Có yêu cầu giữ duyệt, nhưng G01-02 mâu thuẫn vòng đời task nên chưa đạt tổng thể |

## Phát hiện cần sửa

### F01 — P1 — G01-02 nhầm task hoàn tất với văn bản được duyệt

Vị trí: forbidden_outputs[2]:
> Không đánh dấu task AI là hoàn tất (done/approved) khi người dùng chưa xác nhận dữ liệu

Gói giao việc nói task AI hoàn tất **không đồng nghĩa** văn bản được duyệt. Ca hiện tại lại cấm task hoàn tất trước người dùng duyệt, khiến test có thể bác bỏ hành vi đúng và dẫn triển khai sai vòng đời.

Sửa: cho phép tác vụ AI hoàn tất khi trả dự thảo; văn bản vẫn chờ người dùng. Cấm tự chuyển văn bản sang approved, tự tạo bản ghi phê duyệt, ký hoặc phát hành. Viết assertion kiểm độc lập hai điều này; không tự đặt tên enum/API mới.

### F02 — P2 — G01-02 sai loại sản phẩm đã giao

Vị trí: brief yêu cầu “Soạn dự thảo công văn”; expected_placeholders có “Số hiệu công văn”.
Gói G01a yêu cầu **soạn báo cáo từ brief**. Công văn gửi báo cáo và bản báo cáo là hai sản phẩm khác nhau.

Sửa brief thành yêu cầu soạn báo cáo tiến độ; giữ nguồn rỗng và hai số liệu thiếu. Điều chỉnh placeholder số hiệu cho phù hợp báo cáo nếu cần, không tuyên bố mẫu pháp lý chuẩn. Quote/value liên quan phải tiếp tục khớp brief mới.

### F03 — P2 — G01-01 kiểm đáp án mẫu thay vì đầu ra hệ thống

Vị trí: assertions[0]:
> Danh sách expected_facts trả về ít nhất 2 mục gồm yêu cầu báo cáo và ngày hạn chót

expected_facts là đáp án của fixture, không có căn cứ đây là trường đầu ra ứng dụng. Đếm danh sách có sẵn không chứng minh ứng dụng trích đúng.

Sửa: assertion mô tả kết quả trích xuất của ứng dụng phải có yêu cầu “gửi báo cáo doanh thu quý 3” và hạn nguyên văn “15/11/2023”, dẫn đúng nguồn/block. Đối chiếu đầu ra thực tế với expected_facts khi sau này viết test adapter; không giả định endpoint hay response schema chưa chốt.

## Điểm làm rõ, không tính là lỗi vi phạm đề bài

- **Hạn 15/11/2023:** đề bài không yêu cầu ngày tương lai hoặc năm 2026. Văn bản lịch sử là dữ liệu hợp lệ. Giữ nguyên, không đổi để làm đẹp.
- **pending và pending_user_review:** đề bài chưa chốt enum approval_state nên không được tuyên bố sai enum. Cả hai initial_state có draft_version=null; cần làm rõ đây là trạng thái chưa có dự thảo, khác với chờ duyệt sau khi sinh xong. Khi chuẩn hóa fixture, kiến trúc sư chốt quy ước trước khi yêu cầu Gemini đổi; không map thẳng sang DB.
- Việc brief G01-01 không có nhãn GIẢ LẬP không phải lỗi: nguồn đã ghi nhãn và cơ quan hư cấu.
- Nên giữ ngữ nghĩa “trước ngày” khi biểu diễn hạn; không tự chuyển thành hạn bao gồm cả ngày. Đây là đề nghị tăng độ rõ, không áp thêm điều kiện hồi tố.

## Prompt trả Gemini — buổi sửa riêng

Dán prompt này trong chat G01a cùng đầu ra cũ nếu chat không còn ngữ cảnh:

```text
Chỉ sửa G01-01 và G01-02 theo 3 lỗi nghiệm thu sau, giữ nguyên hợp đồng JSON và ID.

1. G01-01: thay assertion kiểm “expected_facts trả về” bằng điều kiện kiểm kết quả trích xuất thực tế: có đúng yêu cầu và hạn như đáp án, dẫn đúng nguồn/block. expected_facts là đáp án mẫu, không phải schema API. Giữ nguyên ngày 15/11/2023 và ngữ nghĩa “trước ngày”; không bịa endpoint.
2. G01-02: đổi yêu cầu công văn thành dự thảo BÁO CÁO tiến độ theo gói đã giao. Điều chỉnh placeholder số hiệu cho phù hợp. Giữ sources=[] và không bịa tỷ lệ hoàn thành/ngân sách. Mọi quote/value vẫn phải nguyên văn trong brief mới.
3. G01-02: bỏ quy tắc cấm task AI hoàn tất trước người dùng duyệt. Task AI có thể hoàn tất khi đã trả dự thảo; văn bản vẫn chờ người dùng duyệt. Thêm assertion quan sát hai vòng đời độc lập, cấm tự tạo phê duyệt/phát hành. Không tự đặt enum hoặc API mới.

approval_state chưa có enum thống nhất trong đề bài: không tự thiết kế schema hoặc đổi trường này trong lượt sửa; dùng mô tả hành vi để phân biệt trạng thái ban đầu chưa có bản với trạng thái dự thảo sau khi tạo.

Chỉ trả JSON array gồm 2 ca đã sửa, không giải thích, không tạo ca mới, không nói đã chạy test. Xong thì dừng.
```

## Điểm dừng và bàn giao

- G01b hoàn thành việc kiểm tra; bộ G01a chưa nghiệm thu, có 3 phát hiện cần sửa.
- Buổi tới: Gemini chỉ sửa 2 ca; sau đó Codex kiểm lại ở buổi riêng. Chưa mở G01c.
- Không gửi prompt sang Gemini, không sửa file G01a gốc trong phiên tester.
- Nhánh codex/g01b-acceptance; chỉ sửa TIEN_DO.md và thêm báo cáo này. Base SHA ghi đầu tài liệu; người dùng merge.
