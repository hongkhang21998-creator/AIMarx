# Bàn giao ngược cho GPT Astra — Claude Opus đang làm đa nền tảng

Ngày: 08/09/2026. Claude Opus tiếp quản theo `docs/handoffs/CLAUDE_OPUS.md`. Tài liệu này để Astra biết chính xác tôi đã làm tới đâu, đã kiểm chứng được gì và **chưa** kiểm chứng được gì, nhằm không giẫm chân nhau.

## 1. Việc người dùng giao thêm

Ngoài phạm vi trong bàn giao cũ, người dùng yêu cầu: hệ thống phải **chạy được độc lập trên cả Windows lẫn Linux**. Đã chốt kiến trúc là **độc lập trên từng máy** — cùng codebase, dữ liệu riêng, cả hai đều bind `127.0.0.1`. Laptop Linux vẫn là máy chủ chính. **Không** mở LAN, không đổi mô hình bảo mật.

- Nhánh: `claude/cross-platform`, base `89d05ae` trên `main`.
- Phạm vi nhánh này **chỉ là tương thích hệ điều hành**, cố ý hẹp để dễ soát khi merge.

## 2. Đã sửa

| File | Nội dung |
|---|---|
| `fsguard.py` (mới) | `harden_dir` siết quyền theo hệ điều hành và trả cảnh báo; `freeze`/`thaw` xử lý thuộc tính read-only của Windows |
| `service.py` | `db()` thành contextmanager có `close()`; thu thập `self.warnings`; `thaw()` trước `os.replace`; `freeze()` thay `chmod(0o400)` |
| `web.py` | Banner cảnh báo môi trường đầu trang; thêm `if __name__ == "__main__"` |
| `mcp_server.py` | Thêm `if __name__ == "__main__"` |
| `tests/test_workflow.py` | Tách test symlink (tự skip khi thiếu quyền); thêm test junction, test freeze/thaw, test DB không bị khóa |
| `scripts/run-local.ps1`, `run-ollama.ps1` (mới) | Khởi động trên Windows; đặt sẵn `PYTHONUTF8=1` |
| `.github/workflows/tests.yml` | Matrix `ubuntu-latest` + `windows-latest`; thêm `PYTHONUTF8` |
| `README.md` | Mục "Chạy trên Windows" liệt kê đủ khác biệt |

## 3. Bốn khác biệt hệ điều hành — đã đo thực nghiệm, không suy đoán

Chạy thử trực tiếp trên Windows 11:

1. `mkdir(mode=0o700)` cho ra quyền thực tế `0o777`. Quyền riêng tư thư mục dữ liệu **mất trong im lặng**.
2. `os.replace()` đè tệp `0o400` → `PermissionError [WinError 5]`. POSIX đè bình thường.
3. `os.remove()` tệp `0o400` → `PermissionError [WinError 5]`.
4. Xóa tệp DB khi connection sqlite còn mở → `PermissionError [WinError 32]`.

Về (1): mã **cố ý không tự chạy `icacls`**. Nếu `icacls /inheritance:r` sai tham số, người dùng có thể mất quyền truy cập chính thư mục dữ liệu của mình — hỏng kiểu khó cứu. Thay vào đó phát cảnh báo hiển thị trên giao diện khi `TLVB_DATA` nằm ngoài hồ sơ người dùng. Không siết ngầm, cũng không hỏng ngầm.

## 4. Phát hiện mới, không có trong bàn giao cũ

- **`with conn` không đóng connection sqlite** — chỉ commit/rollback. Đây là **rò rỉ trên cả Linux**, không riêng Windows; Windows chỉ làm nó lộ ra vì giữ file handle.
- **Windows dùng cp1252 khi stdout bị chuyển hướng** → mọi chuỗi tiếng Việt in ra gây `UnicodeEncodeError` và làm hỏng tiến trình. Ảnh hưởng khi ghi log ra file hoặc chạy dưới dạng dịch vụ. Đã đặt `PYTHONUTF8=1` trong script và CI.
- **GT 710 của máy Windows vô dụng cho suy luận**: compute capability 3.5, driver 456.71 (2020). Ollama đã bỏ hỗ trợ Kepler → sẽ chạy CPU. Nhưng i3-12100 mạnh hơn i3-8130U của laptop, nên xét thuần CPU thì **máy Windows là máy suy luận tốt hơn**.
- **`requirements.lock` không khóa được đa nền tảng**: trên Windows pip kéo thêm `pywin32` không có trong lock (phụ thuộc có điều kiện của `keyring`). `pip check` vẫn sạch, nhưng đừng coi lock này là tái lập được y hệt giữa hai hệ.
- Gói `.tar.zst` 1,43 GB đã verify trong bàn giao cũ là **bản Linux**. Windows cần installer riêng. Model GGUF thì dùng chung được, sao chép `.runtime/models` là đủ — không cần tải lại, đúng ràng buộc cũ.

## 5. Kiểm thử — số liệu thật, và giới hạn của nó

Trên Windows 11, Python 3.14.6, `requirements.lock` cài sạch, `pip check` không lỗi:

- **Trước khi sửa: 9 passed, 1 failed.** Lỗi là `test_path_and_file_limits` — `os.symlink` cần `SeCreateSymbolicLinkPrivilege` (`OSError [WinError 1314]`). Đây là hạn chế môi trường test, không phải lỗi sản phẩm: mã chỉ *phát hiện* symlink bằng `is_symlink()`, việc đó chạy tốt trên Windows.
- **Sau khi sửa: 13 passed, 1 skipped.** Skip là test symlink. Test junction **pass**, nên hàng rào chặn thoát thư mục vẫn còn coverage thật trên Windows chứ không phải skip trắng.
- Chạy thật qua `scripts/run-local.ps1`: `GET /` trả **HTTP 200**, trang hiển thị đúng.
- **CI matrix đã chạy xong và xanh cả hai** (run `34216101884`): `ubuntu-latest` Python 3.12 → **13 passed, 1 skipped**; `windows-latest` → **14 passed**. Runner Windows của GitHub có quyền tạo symlink nên test symlink chạy thật và pass; trên Ubuntu test junction bị skip vì chỉ có trên Windows.
- Cảnh báo thư mục: xác nhận **có** phát khi `TLVB_DATA` ngoài hồ sơ người dùng, **không** phát khi ở trong. Cả hai chiều đều đã thử.

## 6. CHƯA kiểm chứng — đừng tuyên bố thay tôi

- ~~Chưa chạy test trên chính laptop Linux.~~ **Đã chạy ngày 08/09/2026** trên laptop, `.venv` Python 3.12.14, cây làm việc tại `1d073cc`: **13 passed, 1 skipped** (skip là test junction, chỉ có trên Windows), `pip check` sạch. Trùng khớp kết quả `ubuntu-latest` của CI. Vẫn lưu ý: lần chạy này **không** có Ollama sống, không có dữ liệu thật, nên nó chỉ chứng minh bộ test xanh trên chính máy đó — không chứng minh suy luận.
- **Chưa chạm vào laptop Linux**: chưa SSH vào, chưa restart UI ở `:8765`, chưa đụng Ollama ở `:11434`, chưa giải nén gói Ollama đầy đủ. Máy Linux giữ **nguyên trạng** như `CLAUDE_OPUS.md` mô tả, kể cả việc tiến trình UI đang chạy code cũ hơn working tree.
- **Chưa thử inference thật** trên bất kỳ máy nào. Ollama chưa cài trên Windows.
- Trên Windows mới chỉ `curl` trang chủ, **chưa thử luồng đầy đủ** nhập → sửa → duyệt → tải DOCX bằng trình duyệt.
- Nối hai máy bằng SSH **chưa thành**: laptop ở `192.168.130.10`, máy Windows ở `192.168.1.2/24` và `172.19.59.167/20` — khác mạng, `ping` và TCP/22 đều không tới. Cần đưa hai máy về cùng mạng hoặc dùng đường khác.

## 7. Cố ý KHÔNG làm ở nhánh này

Để nhánh dễ soát, tôi không đụng các mục sau trong `CLAUDE_OPUS.md` — chúng thuộc về toàn vẹn phê duyệt, không phải đa nền tảng:

- Mục 2: `review()` chưa kiểm bytes DOCX khớp `draft_hash` lúc duyệt.
- Mục 3: chính sách backfill cột `draft_hash` rỗng.
- Mục 4: chặn `needs_ocr` đầy đủ ở tầng service, không chỉ giao diện.
- Mục 5–7: giải nén Ollama, restart UI, systemd, OCR/Docling, checkpointer, watcher, Calendar/outbox, backup/restore.

Lưu ý liên đới: nếu sau này bỏ `chmod` làm cơ chế chống sửa, `draft_hash` trở thành hàng rào **duy nhất** — khi đó mục 2 thành bắt buộc, không còn là tùy chọn.

## 8. Ranh giới để không giẫm chân

Nhánh `claude/cross-platform` đụng: `service.py`, `web.py`, `mcp_server.py`, `tests/test_workflow.py`, `scripts/`, `.github/workflows/tests.yml`, `README.md`, `WORKLOG.md`, và file mới `src/tro_ly_van_ban/fsguard.py`.

Nếu Astra cần sửa cùng các file này, đọc diff nhánh trước. **Người dùng merge**, agent không tự merge và không bật auto-merge.
