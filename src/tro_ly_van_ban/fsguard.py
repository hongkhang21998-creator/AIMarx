"""Khác biệt quyền tệp giữa Windows và POSIX.

POSIX: chmod có hiệu lực. Windows: tham số mode của mkdir bị bỏ qua, và
thuộc tính read-only chặn cả os.replace lẫn os.remove. Mọi chỗ mất tính
chất an toàn phải phát cảnh báo, không được im lặng.
"""
import os
import stat
import sys
from pathlib import Path

WINDOWS = sys.platform == "win32"


def harden_dir(path: Path) -> str:
    """Siết thư mục về riêng tư. Trả về cảnh báo; chuỗi rỗng nghĩa là đã siết."""
    if not WINDOWS:
        path.chmod(0o700)
        return ""
    profile = os.environ.get("USERPROFILE", "")
    try:
        inside = bool(profile) and path.resolve().is_relative_to(Path(profile).resolve())
    except OSError:
        inside = False
    if inside:
        return ""
    return (f"Windows bỏ qua quyền 0700 nên thư mục dữ liệu {path} nằm ngoài hồ sơ người dùng "
            "có thể bị tài khoản khác trên máy đọc. Hãy chuyển vào thư mục hồ sơ, "
            "hoặc siết thủ công bằng icacls trước khi nạp văn bản thật.")


def freeze(path: Path) -> None:
    """Đặt tệp về chỉ đọc."""
    path.chmod(stat.S_IRUSR)


def thaw(path: Path) -> None:
    """Bỏ chỉ đọc; bắt buộc trên Windows trước khi ghi đè hoặc xóa."""
    if path.exists():
        path.chmod(stat.S_IWRITE | stat.S_IREAD)
