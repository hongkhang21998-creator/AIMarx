import importlib.util
import json
from pathlib import Path
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "check_direct_push.py"
spec = importlib.util.spec_from_file_location("check_direct_push", SCRIPT)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

SHA = "e" * 40
REPO = "owner/repo"


def merged(sha=SHA, base="main", number=24):
    return {"number": number, "merged_at": "2026-09-11T01:49:25Z", "merge_commit_sha": sha, "base": {"ref": base}}


@pytest.fixture
def github(monkeypatch, tmp_path):
    """Gia lap GitHub API: ghi lai moi loi goi, tra loi theo bang dinh san."""
    state = {"pulls": [], "issues": [], "calls": [], "pulls_sequence": None}

    def api(method, path, body=None):
        state["calls"].append((method, path, body))
        if path.endswith("/pulls"):
            if state["pulls_sequence"]:
                return state["pulls_sequence"].pop(0)
            return state["pulls"]
        if method == "GET" and "/issues" in path:
            return state["issues"]
        if method == "POST" and path.endswith("/issues"):
            return {"number": 99, "html_url": "https://example/99"}
        raise AssertionError(path)

    monkeypatch.setattr(guard, "api", api)
    monkeypatch.setattr(guard.time, "sleep", lambda s: None)

    def run(event, name="push", **env):
        path = tmp_path / "event.json"
        path.write_text(json.dumps(event), encoding="utf-8")
        monkeypatch.setenv("GITHUB_REPOSITORY", REPO)
        monkeypatch.setenv("GITHUB_EVENT_PATH", str(path))
        monkeypatch.setenv("GITHUB_EVENT_NAME", name)
        monkeypatch.setenv("GITHUB_TOKEN", "x")
        for key in ("DRY_RUN", "CHECK_SHA"):
            monkeypatch.setenv(key, env.get(key, ""))
        return guard.main()

    state["run"] = run
    return state


def created(state):
    return [body for method, path, body in state["calls"] if method == "POST"]


def push(**extra):
    return {"after": SHA, "pusher": {"name": "khang"}, "sender": {"login": "khang"},
            "repository": {"owner": {"login": "khang"}},
            "commits": [{"id": SHA, "message": "refactor: clean up\n\nchi tiet", "author": {"name": "khang"}}], **extra}


def test_pr_merge_is_silent(github):
    github["pulls"] = [merged()]
    assert github["run"](push()) == 0
    assert created(github) == []


def test_direct_push_opens_assigned_issue(github):
    assert github["run"](push()) == 0
    [body] = created(github)
    assert SHA[:7] in body["title"]
    assert body["assignees"] == ["khang"]
    assert "không phải merge commit" in body["body"]
    assert "refactor: clean up" in body["body"]


def test_commit_in_open_or_other_base_pr_still_alerts(github):
    # Commit thuoc PR chua merge, hoac PR merge vao nhanh khac, khong phai bang chung da qua PR vao main.
    github["pulls"] = [{**merged(), "merged_at": None}, merged(base="claude/qa-p1"), merged(sha="f" * 40)]
    github["run"](push())
    assert len(created(github)) == 1


def test_force_push_alerts_even_when_head_is_a_pr_merge(github):
    github["pulls"] = [merged()]
    github["run"](push(forced=True))
    [body] = created(github)
    assert "Force-push" in body["body"]


def test_late_pr_link_is_retried_not_reported(github):
    # Ngay sau merge, lien ket commit-PR co the chua hien; bao nham se day nguoi dung lo canh bao.
    github["pulls_sequence"] = [[], [], [merged()]]
    assert github["run"](push()) == 0
    assert created(github) == []


def test_no_duplicate_issue_on_rerun(github):
    github["issues"] = [{"number": 7, "title": f"Cảnh báo: main nhận commit không qua PR — {SHA[:7]}"}]
    github["run"](push())
    assert created(github) == []


def test_dry_run_dispatch_reports_without_creating(github, capsys):
    assert github["run"]({"repository": {"owner": {"login": "khang"}}}, name="workflow_dispatch",
                         CHECK_SHA=SHA, DRY_RUN="true") == 0
    assert created(github) == []
    assert "CẢNH BÁO" in capsys.readouterr().out


def test_invalid_sha_is_rejected(github):
    assert github["run"]({}, name="workflow_dispatch", CHECK_SHA="ef9c818") == 2
    assert github["calls"] == []
