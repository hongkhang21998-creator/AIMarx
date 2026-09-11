# PLAN-EVAL-02 — kết quả bàn giao

- Ngày, người phụ trách: 11/09/2026 — Luna.
- Base: `origin/main` tại `1133f9a8d6034732cfeefaa5643e47173d508684`; sở hữu đúng `evals/planning/score.py`, `tests/test_planning_score.py`, tài liệu này.
- Đã làm: scorer offline thuần dữ liệu; kiểm schema, source ID/quote nguyên văn, citation trùng, bước nguy hiểm; output thiếu/sai kiểu bị fail.
- Semantic (`requested_product`, độ liên quan citation, thiếu thông tin, bước, cấm, `cloud_eligible`) luôn trả `needs_human_review`, không suy diễn từ substring.
- Kiểm tra: `./.venv/bin/pytest -q tests/test_planning_score.py` → 10 passed; không model/API/network, không sửa fixture.
- Giới hạn: safety check là hàng rào từ khóa hẹp, không thay đánh giá người; `passed` chỉ là objective checks, còn `status=needs_human_review` phải được giữ.
- Trạng thái: đạt; dừng tại đây để Astra review/tích hợp và tạo PR, người dùng merge.
