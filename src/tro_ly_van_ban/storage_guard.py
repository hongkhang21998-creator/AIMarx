"""Chặn khởi động khi kho dữ liệu không nằm trên ổ bắt buộc.

Anh Khang chốt ngày 11/09/2026: DB local bắt buộc nằm trên ổ Data1000. Ổ đó gắn
dưới `/run/media/...`, mà `/run` là tmpfs. Rút ổ rồi khởi động lại thì
`Service` sẽ `mkdir(parents=True)` trên đường cũ; hôm nay lệnh đó chỉ tình cờ
thất bại nhờ quyền thư mục do udisks đặt. Nếu quyền đổi, ứng dụng dựng một DB
rỗng trong RAM mà không báo gì — và ledger sau này sẽ mất sổ, reset hạn mức.

Không đặt `required_mount` thì không kiểm gì: CI, Windows và máy không có ổ
ngoài vẫn chạy như cũ.
"""
import os
from pathlib import Path


class StorageUnavailable(RuntimeError):
    """Kho dữ liệu không nằm trên ổ bắt buộc; không được tạo kho mới."""


def _device(path: Path) -> int:
    return os.stat(path).st_dev


def check_data_root(data_root, required_mount) -> None:
    """Kiểm kho trước khi ai kịp tạo thư mục; sai thì ném StorageUnavailable.

    Ba điều kiện, theo docs/SNAPSHOT_CONTRACT.md mục 3.2:
    1. `data_root` tuyệt đối và sau khi resolve nằm dưới `required_mount`. Đường
       tương đối bị từ chối: nó phụ thuộc thư mục đang đứng, nên chạy nhầm từ
       bản sao khác là dùng nhầm kho khác.
    2. `required_mount` đang thật sự là điểm gắn ổ.
    3. Thư mục gần nhất đang tồn tại trên đường tới kho nằm cùng thiết bị với
       điểm gắn. Bắt ca thư mục cùng tên nhưng nằm trên ổ khác.
    """
    if required_mount is None or required_mount == "":
        return
    mount = Path(required_mount)
    root = Path(data_root)
    if not mount.is_absolute() or not root.is_absolute():
        raise StorageUnavailable("TLVB_DATA và TLVB_REQUIRED_MOUNT phải là đường dẫn tuyệt đối; không tạo kho mới")
    if not os.path.ismount(mount):
        raise StorageUnavailable(f"Ổ bắt buộc chưa được gắn tại {mount}; gắn ổ rồi chạy lại. Không tạo kho mới")
    resolved = root.resolve()
    if not resolved.is_relative_to(mount.resolve()):
        raise StorageUnavailable(f"Kho dữ liệu {root} không nằm trên ổ bắt buộc {mount}; không tạo kho mới")
    existing = resolved
    while not existing.exists():
        existing = existing.parent
    if _device(existing) != _device(mount):
        raise StorageUnavailable(f"Kho dữ liệu {root} nằm trên ổ khác với {mount}; không tạo kho mới")
