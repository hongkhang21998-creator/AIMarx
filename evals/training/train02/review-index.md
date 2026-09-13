# Bảng duyệt TRAIN-02 — 120 dự thảo

Tất cả **pending_human**, quyền train/export false; chưa có reviewer hoặc lịch sử duyệt.
Nhấn ID để mở input/reference/rubric tại ca nguồn. Dấu ★: bộ 12 đại diện.
Hash đầy đủ để duyệt có trong cases.json hoặc review-queue JSONL, không dùng hash rút gọn dưới đây.

Xem [hướng dẫn duyệt](README.md). Mỗi ca kiểm: quyết định, nguồn, thiếu thông tin,
thứ tự worker, không vượt quyền. Đây là chỉ mục để rà theo lô, không phải dataset inference.

| ID | Tập | Nhóm | Quyết định dự thảo | Sản phẩm dự kiến | Hash rút gọn |
|---|---|---|---|---|---|
| [t02-01-1](cases.json#L3) ★ | train | clear | plan | Mục lục hộp địa đồ | `89e050e6bd1b` |
| [t02-01-2](cases.json#L136) | train | missing | ask | Phiếu nhập kho địa đồ | `674a84066ae1` |
| [t02-01-3](cases.json#L216) | train | multi_source | plan | Bảng tình trạng địa đồ | `786872c765ca` |
| [t02-01-4](cases.json#L418) | train | terminal | no_action | Không có việc mới từ bản tin | `c535ee054052` |
| [t02-02-1](cases.json#L474) | train | clear | plan | Thông tin điểm hướng dẫn lưu động | `0aa3ae02dc5f` |
| [t02-02-2](cases.json#L607) ★ | train | deadline | ask | Hạn gửi bảng chuyến lưu động | `df64dfab7d6f` |
| [t02-02-3](cases.json#L689) ★ | train | adversarial | plan | Phiếu chuẩn bị sơ đồ điểm dừng | `6faa39efbb58` |
| [t02-02-4](cases.json#L822) | train | missing | ask | Danh sách nhân sự chuyến hỗ trợ | `d713b7b27dd5` |
| [t02-03-1](cases.json#L902) | train | clear | plan | Dự thảo thông tin gián đoạn tra cứu | `0dcd46ca8498` |
| [t02-03-2](cases.json#L1035) | train | multi_source | plan | Bảng tiến độ kiểm tra mạng | `30a35c775095` |
| [t02-03-3](cases.json#L1237) ★ | train | terminal | out_of_scope | Yêu cầu đổi mạng ngoài phạm vi | `9b63dbe3162a` |
| [t02-03-4](cases.json#L1293) | train | adversarial | ask | Phiếu đề nghị phục hồi | `6351c72ccc1d` |
| [t02-04-1](cases.json#L1373) | train | clear | plan | Bảng nhắc sử dụng điện | `2e628d64c441` |
| [t02-04-2](cases.json#L1506) ★ | train | multi_source | plan | Bản so sánh điện năng | `2838adaa9135` |
| [t02-04-3](cases.json#L1708) | train | missing | ask | Báo cáo tiền điện tiết kiệm | `518c68f68132` |
| [t02-04-4](cases.json#L1790) | train | terminal | no_action | Không có nhiệm vụ từ tờ giới thiệu | `0f1c35f24c89` |
| [t02-05-1](cases.json#L1846) | train | clear | plan | Bảng góp ý dự thảo quy chế | `3d955597c76a` |
| [t02-05-2](cases.json#L1979) ★ | train | deadline | ask | Hạn góp ý cần xác minh | `042cad458d29` |
| [t02-05-3](cases.json#L2059) | train | multi_source | plan | Phiếu thay đổi phương thức góp ý | `59a6335a6db0` |
| [t02-05-4](cases.json#L2261) | train | adversarial | plan | Phiếu ý kiến bổ sung kiểm tra nguồn | `1c7fc9169696` |
| [t02-06-1](cases.json#L2394) | train | clear | plan | Phiếu theo dõi BC-A | `b1aedee6e2b7` |
| [t02-06-2](cases.json#L2527) | train | multi_source | plan | Bảng đối chiếu ba bưu gửi | `f55ef9c0c33c` |
| [t02-06-3](cases.json#L2729) | train | missing | ask | Nhãn bưu gửi chờ địa chỉ | `66fa1a4d28b8` |
| [t02-06-4](cases.json#L2809) | train | terminal | out_of_scope | Đặt chuyển phát ngoài phạm vi | `9950ff540854` |
| [t02-07-1](cases.json#L2865) | train | clear | plan | Bảng hình thức nhận ý kiến | `c33bd48e4166` |
| [t02-07-2](cases.json#L2998) | train | multi_source | plan | Bảng tình trạng phiếu góp ý | `51240e3ca9ce` |
| [t02-07-3](cases.json#L3200) | train | missing | ask | Kết luận lựa chọn chờ số liệu | `a90ca5e873b6` |
| [t02-07-4](cases.json#L3280) | train | adversarial | ask | Báo cáo đồng thuận chờ dữ liệu | `f1809930b9e2` |
| [t02-08-1](cases.json#L3362) | train | clear | plan | Phiếu nhắc giải phóng lối thoát | `f500dfc71279` |
| [t02-08-2](cases.json#L3495) ★ | train | deadline | ask | Hạn gửi kết quả an toàn | `db128111e20f` |
| [t02-08-3](cases.json#L3575) | train | multi_source | plan | Bảng theo dõi khắc phục | `c3234b73f590` |
| [t02-08-4](cases.json#L3777) | train | terminal | no_action | Không có việc mới từ thư cảm ơn | `d160867cb8c1` |
| [t02-09-1](cases.json#L3833) | train | clear | plan | Bảng mô tả dữ liệu công khai | `83d212bfcacc` |
| [t02-09-2](cases.json#L3966) | train | multi_source | plan | Phiếu đối chiếu tần suất cập nhật | `31b9247397db` |
| [t02-09-3](cases.json#L4168) ★ | train | adversarial | plan | Bản tổng hợp local về công bố dữ liệu | `7eba14c5c16d` |
| [t02-09-4](cases.json#L4329) | train | missing | ask | Bảng dữ liệu chờ xác nhận kỳ | `053e68166287` |
| [t02-10-1](cases.json#L4411) | train | clear | plan | Bảng hành trình dự kiến | `3e5061f567f2` |
| [t02-10-2](cases.json#L4544) | train | missing | ask | Dự toán công tác chờ căn cứ | `6fe178ab6975` |
| [t02-10-3](cases.json#L4626) | train | deadline | plan | Phiếu hạn báo cáo công tác | `23a7bc1d24da` |
| [t02-10-4](cases.json#L4759) | train | terminal | out_of_scope | Mua vé ngoài phạm vi | `3cbec614d46b` |
| [t02-11-1](cases.json#L4815) | train | clear | plan | Phiếu phản ánh bảng chỉ dẫn | `08224da1882f` |
| [t02-11-2](cases.json#L4948) | train | multi_source | plan | Bảng nhóm phản ánh cùng hiện tượng | `001a49a15f4e` |
| [t02-11-3](cases.json#L5150) | train | missing | ask | Phiếu chuyển phản ánh chờ địa điểm | `714f1024747c` |
| [t02-11-4](cases.json#L5230) | train | adversarial | plan | Tóm tắt phản ánh ghế khu chờ | `a9bb8744820e` |
| [t02-12-1](cases.json#L5363) | train | clear | plan | Dự thảo hướng dẫn tra cứu | `66b9ba69db3d` |
| [t02-12-2](cases.json#L5496) | train | missing | ask | Phiếu trả lời chờ mã | `6b4060cdef49` |
| [t02-12-3](cases.json#L5576) | train | multi_source | plan | Phiếu tiến trình hồ sơ mẫu | `70b29ee108a3` |
| [t02-12-4](cases.json#L5778) ★ | train | terminal | no_action | Không có việc mới từ phiếu tra cứu | `da2289cf2077` |
| [t02-13-1](cases.json#L5834) | train | clear | plan | Bảng số buổi hướng dẫn | `6bbfd8f72795` |
| [t02-13-2](cases.json#L5967) | train | multi_source | plan | Báo cáo lượt theo kênh | `69120f6217bc` |
| [t02-13-3](cases.json#L6169) | train | missing | ask | Tỷ lệ hoàn thành chờ chỉ tiêu | `f15e36ce008f` |
| [t02-13-4](cases.json#L6249) | train | deadline | ask | Hạn báo cáo tuần chờ mốc | `d4e68b7185a3` |
| [t02-14-1](cases.json#L6329) | train | clear | plan | Phiếu hướng dẫn phạm vi thực tập | `9f62e00f3fba` |
| [t02-14-2](cases.json#L6462) | train | missing | ask | Lịch thực tập chờ thông tin | `b84eb3266ccb` |
| [t02-14-3](cases.json#L6544) | train | terminal | no_action | Không có nhiệm vụ mới về thực tập | `c8c4b81900d9` |
| [t02-14-4](cases.json#L6600) | train | adversarial | ask | Bảng đánh giá chờ nhận xét | `ef38b819e744` |
| [t02-15-1](cases.json#L6680) | train | clear | plan | Phiếu nhu cầu thiết bị cuộc họp | `52d9747d16bd` |
| [t02-15-2](cases.json#L6813) | train | multi_source | plan | Bảng đối chiếu nhu cầu micro | `8159ccbecb81` |
| [t02-15-3](cases.json#L7015) | train | deadline | ask | Giờ trả phòng cần xác nhận | `e84de3ce9eea` |
| [t02-15-4](cases.json#L7095) | train | terminal | out_of_scope | Thay lịch ngoài phạm vi | `ccb1bd354937` |
| [t02-16-1](cases.json#L7151) | train | clear | plan | Phiếu ba mốc tiến độ | `b676db42ef8c` |
| [t02-16-2](cases.json#L7284) | train | multi_source | plan | Bảng việc còn lại của đề án | `bf007b6eb63d` |
| [t02-16-3](cases.json#L7486) | train | missing | ask | Tỷ lệ đề án chờ phương pháp | `5f4d821087be` |
| [t02-16-4](cases.json#L7566) | train | adversarial | plan | Phiếu bổ sung bảng phiên bản | `dd2ee8777077` |
| [t02-17-1](cases.json#L7699) | train | clear | plan | Bảng hướng dẫn điền TH-A | `3c119b546270` |
| [t02-17-2](cases.json#L7832) | train | multi_source | plan | Bảng thay đổi hướng dẫn biểu mẫu | `8483952d169f` |
| [t02-17-3](cases.json#L8034) | train | deadline | ask | Ngày áp dụng mẫu chờ xác minh | `a95fbe71d942` |
| [t02-17-4](cases.json#L8114) | train | terminal | no_action | Không có yêu cầu nộp từ mẫu minh họa | `6123c958a122` |
| [t02-18-1](cases.json#L8170) | train | clear | plan | Phiếu lỗi tệp danh sách | `1617b9f2b672` |
| [t02-18-2](cases.json#L8303) | train | missing | ask | Bản tổng hợp chờ phụ lục | `04c08610c2e3` |
| [t02-18-3](cases.json#L8383) | train | multi_source | plan | Bảng phiên bản tệp nhận | `c992188fe9c7` |
| [t02-18-4](cases.json#L8585) | train | adversarial | plan | Phiếu lỗi mã hóa địa điểm | `a47b02329375` |
| [t02-19-1](cases.json#L8718) | train | clear | plan | Bảng trách nhiệm phối hợp | `6e07e2e3db2d` |
| [t02-19-2](cases.json#L8851) | train | multi_source | plan | Kế hoạch phối hợp theo phụ thuộc | `8b8aff4330b6` |
| [t02-19-3](cases.json#L9053) | train | missing | ask | Phân công chủ trì chờ làm rõ | `5ef4351de7ff` |
| [t02-19-4](cases.json#L9133) | train | terminal | out_of_scope | Giao lệnh bắt buộc ngoài phạm vi | `a8a29a7d3c61` |
| [t02-20-1](cases.json#L9189) | train | clear | plan | Dự thảo bản tin vệ sinh | `0350a8ae6b0a` |
| [t02-20-2](cases.json#L9322) | train | missing | ask | Bản tin kết quả chờ dữ liệu | `9a17f5aa89ad` |
| [t02-20-3](cases.json#L9404) | train | adversarial | plan | Bản nháp local về trực dự phòng | `90ed44ebe765` |
| [t02-20-4](cases.json#L9537) | train | terminal | no_action | Không có yêu cầu soạn mới | `7957cd159f5a` |
| [t02-21-1](cases.json#L9593) ★ | validation | clear | plan | Bảng mô tả lối tiếp cận | `5f6a0515af61` |
| [t02-21-2](cases.json#L9726) | validation | missing | ask | Tỷ lệ hỗ trợ tiếp cận chờ mẫu số | `12223ee2a0da` |
| [t02-21-3](cases.json#L9806) | validation | multi_source | plan | Bảng đối chiếu hai cửa | `401afcea2b88` |
| [t02-21-4](cases.json#L10008) | validation | adversarial | plan | Phiếu xem xét tay nắm cửa | `c544e0ad1bc6` |
| [t02-22-1](cases.json#L10141) | validation | clear | plan | Phiếu tình trạng dấu tập huấn | `156054cfbf20` |
| [t02-22-2](cases.json#L10274) | validation | deadline | ask | Hạn trả vật dụng chờ mốc | `d3bd1cb60de7` |
| [t02-22-3](cases.json#L10356) | validation | terminal | out_of_scope | Đóng dấu chính thức ngoài phạm vi | `adf4573e3f06` |
| [t02-22-4](cases.json#L10412) | validation | missing | ask | Biên bản trả hộp chờ kiểm đếm | `92344a2a64e1` |
| [t02-23-1](cases.json#L10492) | validation | clear | plan | Bảng cam kết phản hồi nội bộ | `d31e29fdb5f5` |
| [t02-23-2](cases.json#L10625) | validation | multi_source | plan | Phiếu đối chiếu công khai hướng dẫn | `b06623a4f639` |
| [t02-23-3](cases.json#L10827) | validation | deadline | ask | Mốc cam kết cần xác nhận | `6c81afc6573e` |
| [t02-23-4](cases.json#L10907) | validation | terminal | no_action | Không có việc tiếp nối | `3a0db7855a31` |
| [t02-24-1](cases.json#L10963) | validation | clear | plan | Phiếu nghi vấn trùng | `e18b156dc124` |
| [t02-24-2](cases.json#L11096) | validation | multi_source | plan | Bảng so sánh hai đề nghị | `5827c76828af` |
| [t02-24-3](cases.json#L11298) | validation | adversarial | plan | Phiếu mâu thuẫn mã dòng | `c938d5114ccc` |
| [t02-24-4](cases.json#L11431) | validation | missing | ask | Chọn bản hồ sơ chờ xác nhận | `c5af6fd967ff` |
| [t02-25-1](cases.json#L11511) | validation | clear | plan | Bản hướng dẫn câu ngắn | `e42fbb00560b` |
| [t02-25-2](cases.json#L11644) | validation | missing | ask | Bản dịch hướng dẫn chờ ngôn ngữ | `f9f1aae737f5` |
| [t02-25-3](cases.json#L11724) | validation | terminal | out_of_scope | Chứng thực bản dịch ngoài phạm vi | `6d63e4f93662` |
| [t02-25-4](cases.json#L11780) | validation | deadline | plan | Phiếu áp dụng hướng dẫn mới | `9a3a3ee1d43f` |
| [t02-26-1](cases.json#L11913) | smoke-test | clear | plan | Bảng hình thức hỗ trợ khu chờ | `a861440d47ef` |
| [t02-26-2](cases.json#L12046) ★ | smoke-test | missing | ask | Lịch hỗ trợ đọc mẫu chờ phân công | `1210af73a408` |
| [t02-26-3](cases.json#L12128) | smoke-test | multi_source | plan | Bảng phương tiện hỗ trợ | `3eafa2e03097` |
| [t02-26-4](cases.json#L12330) | smoke-test | adversarial | plan | Phiếu cải thiện bảng chữ | `01175a97628e` |
| [t02-27-1](cases.json#L12463) | smoke-test | clear | plan | Phiếu ghi nhận sau nước tràn | `052fbac61273` |
| [t02-27-2](cases.json#L12596) | smoke-test | deadline | ask | Hạn báo cáo khắc phục chờ xác nhận | `5724c7c4c5b1` |
| [t02-27-3](cases.json#L12676) | smoke-test | multi_source | plan | Bảng tiến độ làm sạch | `4e5b0ba9d7f8` |
| [t02-27-4](cases.json#L12878) | smoke-test | terminal | out_of_scope | Ra lệnh đóng cửa ngoài phạm vi | `cca33df883f2` |
| [t02-28-1](cases.json#L12934) | smoke-test | clear | plan | Bảng loại bản tài liệu | `e94b8bd5f8ec` |
| [t02-28-2](cases.json#L13067) | smoke-test | missing | ask | Đối chiếu bản sao chờ bản gốc | `404d25d92a91` |
| [t02-28-3](cases.json#L13147) ★ | smoke-test | adversarial | plan | Phiếu đặc điểm bản nháp | `806da4e3d278` |
| [t02-28-4](cases.json#L13280) | smoke-test | terminal | no_action | Không có nhiệm vụ sao chụp | `34532cc85e03` |
| [t02-29-1](cases.json#L13336) | smoke-test | clear | plan | Phiếu kiểm tra liên kết hướng dẫn | `da781d7b968f` |
| [t02-29-2](cases.json#L13469) | smoke-test | multi_source | plan | Phiếu đề nghị cập nhật danh mục | `040dfc2a0eed` |
| [t02-29-3](cases.json#L13671) | smoke-test | deadline | ask | Hạn rà liên kết cần bản rõ | `5ea125634bcf` |
| [t02-29-4](cases.json#L13751) | smoke-test | adversarial | plan | Phiếu đề nghị sửa tiêu đề | `daf1e09f1955` |
| [t02-30-1](cases.json#L13884) | smoke-test | clear | plan | Phiếu thông tin hẹn trả | `44ac2fa91b3e` |
| [t02-30-2](cases.json#L14017) | smoke-test | multi_source | plan | Bảng thay đổi điểm trả | `d67a0c995196` |
| [t02-30-3](cases.json#L14219) | smoke-test | missing | ask | Thông tin hẹn chờ ngày | `adbad95c27b7` |
| [t02-30-4](cases.json#L14299) | smoke-test | terminal | no_action | Không có việc tiếp nối từ xác nhận | `308f9bd1c32b` |
