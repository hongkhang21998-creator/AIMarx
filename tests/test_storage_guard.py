"""Chặn khởi động khi kho không nằm trên ổ bắt buộc (docs/SNAPSHOT_CONTRACT.md mục 3.2).

Không đụng ổ thật: điểm gắn và mã thiết bị được giả lập bằng monkeypatch, nên
test chạy như nhau trên Linux, Windows và CI không có ổ Data1000.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import tro_ly_van_ban.storage_guard as guard
from tro_ly_van_ban import mcp_server
from tro_ly_van_ban.service import Service
from tro_ly_van_ban.storage_guard import StorageUnavailable
from tro_ly_van_ban.web import create_app


@pytest.fixture
def mount(tmp_path, monkeypatch):
    """tmp_path/drive đóng vai ổ Data1000 đang gắn; mọi thứ bên trong cùng thiết bị."""
    drive = tmp_path / "drive"
    drive.mkdir()
    real = os.path.ismount
    monkeypatch.setattr(guard.os.path, "ismount", lambda p: Path(p) == drive or real(p))
    return drive


@pytest.mark.parametrize("required_mount", [None, ""])
def test_without_required_mount_behaviour_is_unchanged(tmp_path, monkeypatch, required_mount):
    # CI, Windows và máy không có ổ ngoài: đường tương đối vẫn chạy như trước.
    monkeypatch.chdir(tmp_path)
    Service("data", "demo", required_mount=required_mount)
    assert (tmp_path / "data" / "state.sqlite3").is_file()


def test_data_on_mounted_drive_is_accepted_and_created(mount):
    service = Service(mount / "AIMarx" / "data", "demo", required_mount=str(mount))
    assert service.root == (mount / "AIMarx" / "data").resolve()
    assert (mount / "AIMarx" / "data" / "state.sqlite3").is_file()


def test_unmounted_drive_refuses_and_creates_nothing(tmp_path):
    # Ổ đã rút: đường cũ vẫn là chuỗi hợp lệ nhưng không còn là điểm gắn.
    gone = tmp_path / "Data1000"
    data = gone / "AIMarx" / "workspace" / "data"
    with pytest.raises(StorageUnavailable, match="chưa được gắn"):
        Service(data, "demo", required_mount=str(gone))
    assert not gone.exists(), "không được mkdir khi ổ vắng mặt"


def test_mount_point_that_exists_but_is_not_mounted_is_refused(tmp_path):
    # Thư mục điểm gắn còn đó (ví dụ người khác tạo lại) nhưng không có ổ nào gắn vào.
    empty = tmp_path / "Data1000"
    empty.mkdir()
    with pytest.raises(StorageUnavailable):
        Service(empty / "data", "demo", required_mount=str(empty))
    assert list(empty.iterdir()) == []


@pytest.mark.parametrize("data", ["data", os.path.join("AIMarx", "data")])
def test_relative_data_root_is_refused_when_mount_is_required(mount, monkeypatch, data):
    # Đường tương đối phụ thuộc thư mục đang đứng: chạy từ bản laptop là dùng nhầm kho cũ.
    monkeypatch.chdir(mount)
    with pytest.raises(StorageUnavailable, match="tuyệt đối"):
        Service(data, "demo", required_mount=str(mount))
    assert not (mount / data).exists()


def test_relative_mount_is_refused(tmp_path):
    with pytest.raises(StorageUnavailable, match="tuyệt đối"):
        Service(tmp_path / "data", "demo", required_mount="Data1000")


def test_data_outside_mount_is_refused(mount, tmp_path):
    laptop = tmp_path / "laptop" / "data"
    with pytest.raises(StorageUnavailable, match="không nằm trên ổ"):
        Service(laptop, "demo", required_mount=str(mount))
    assert not laptop.exists()


def test_dotdot_escape_is_resolved_before_comparing(mount, tmp_path):
    sneaky = mount / ".." / "laptop" / "data"
    with pytest.raises(StorageUnavailable, match="không nằm trên ổ"):
        Service(sneaky, "demo", required_mount=str(mount))
    assert not (tmp_path / "laptop").exists()


def test_same_path_on_a_different_device_is_refused(mount, monkeypatch):
    # Thư mục cùng tên nằm dưới điểm gắn nhưng thuộc thiết bị khác.
    real = guard._device
    other = mount / "other-disk"
    other.mkdir()
    monkeypatch.setattr(guard, "_device", lambda p: -1 if Path(p) == other else real(p))
    with pytest.raises(StorageUnavailable, match="ổ khác"):
        Service(other / "data", "demo", required_mount=str(mount))
    assert not (other / "data").exists()


def test_web_entry_point_reads_required_mount_from_env(tmp_path, monkeypatch):
    gone = tmp_path / "Data1000"
    monkeypatch.setenv("TLVB_DATA", str(gone / "data"))
    monkeypatch.setenv("TLVB_REQUIRED_MOUNT", str(gone))
    with pytest.raises(StorageUnavailable):
        create_app()
    assert not gone.exists()


def test_mcp_entry_point_reads_required_mount_from_env(tmp_path, monkeypatch):
    gone = tmp_path / "Data1000"
    monkeypatch.setenv("TLVB_DATA", str(gone / "data"))
    monkeypatch.setenv("TLVB_REQUIRED_MOUNT", str(gone))
    with pytest.raises(StorageUnavailable):
        mcp_server.main()
    assert not gone.exists()


def test_empty_required_mount_env_means_not_required(tmp_path, monkeypatch):
    # `TLVB_REQUIRED_MOUNT=` rỗng trong .env không được biến thành "mọi thứ bị chặn".
    monkeypatch.setenv("TLVB_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("TLVB_REQUIRED_MOUNT", "")
    create_app()
    assert (tmp_path / "data" / "state.sqlite3").is_file()


@pytest.mark.skipif(sys.platform == "win32" or shutil.which("bash") is None, reason="script bash")
def test_run_local_sh_loads_only_tlvb_lines_and_cli_wins(tmp_path):
    """Chạy đúng phần đọc .env của run-local.sh, thay lệnh exec bằng in env."""
    repo = Path(__file__).resolve().parents[1]
    script = (repo / "scripts" / "run-local.sh").read_text(encoding="utf-8")
    assert script.count("exec .venv/bin/tro-ly-van-ban") == 1
    probe = tmp_path / "scripts" / "run-local.sh"
    probe.parent.mkdir()
    probe.write_text(script.replace("exec .venv/bin/tro-ly-van-ban", 'env | grep -E "^(TLVB_|PWNED)" | sort'), encoding="utf-8")
    marker = tmp_path / "pwned"
    (tmp_path / ".env").write_text(
        "TLVB_DATA=/run/media/asus/Data1000/AIMarx/workspace/data\r\n"
        "TLVB_REQUIRED_MOUNT=/run/media/asus/Data1000\n"
        "TLVB_MODE=ollama\n"
        "# TLVB_PORT=1\n"
        "PWNED=1\n"
        f"TLVB_X=$(touch {marker})\n"
        "TLVB_PORT=8799",  # dòng cuối không có xuống dòng
        encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("TLVB_")}
    env["TLVB_MODE"] = "demo"
    out = subprocess.run(["bash", str(probe)], env=env, capture_output=True, text=True, check=True).stdout.splitlines()
    assert out == [
        "TLVB_DATA=/run/media/asus/Data1000/AIMarx/workspace/data",
        "TLVB_MODE=demo",
        "TLVB_PORT=8799",
        "TLVB_REQUIRED_MOUNT=/run/media/asus/Data1000",
        f"TLVB_X=$(touch {marker})",
    ]
    assert not marker.exists(), ".env bị chạy như mã lệnh"
