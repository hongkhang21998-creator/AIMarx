# AGENT-WORKFLOW-01 — handoff

Nhánh `codex/agent-training-workflow`, base `48806de`. Phạm vi sở hữu:
`agent_workflow.py`, test mới, tài liệu workflow và các dòng liên kết/nhật ký.

Kết quả là hợp đồng mã hóa cho luồng localhost → model gateway → remote Qwen 3B
→ localhost, tám vai trò và điều kiện xuất mẫu train. Không có network call,
tunnel, secret, migration DB, route UI/API hoặc thay đổi hành vi production.

PR tích hợp tiếp theo phải tách riêng: adapter HTTP phía gateway, endpoint worker
Colab dùng token phiên, queue concurrency 1, timeout/idempotency và test synthetic
qua cổng consent/ledger PSC-01. Không dùng tài liệu nghiệp vụ thật trước khi đường
gửi dữ liệu được người dùng xem trước và cấp grant.
