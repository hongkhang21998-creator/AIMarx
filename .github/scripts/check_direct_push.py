"""Cảnh báo khi main nhận commit không đi qua PR.

Repo riêng tư trên GitHub Free không có branch protection, nên main vẫn nhận
push thẳng. Script này không chặn được; nó chỉ bảo đảm mỗi lần như vậy đều
thành một issue giao cho chủ repo, thay vì chờ ai đó tình cờ phát hiện.

Quy tắc: `after` của lần push phải là `merge_commit_sha` của một PR đã merge
vào main. Đúng cho cả merge commit, squash và rebase. Force-push luôn bị báo,
kể cả khi đầu mút trùng một PR, vì nó viết lại lịch sử.

Chỉ dùng thư viện chuẩn để workflow không phải cài gì.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://api.github.com"


def api(method, path, body=None):
    request = urllib.request.Request(
        API + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "tro-ly-van-ban-direct-push-guard",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read() or b"null")


def merged_pr(repo, sha, attempts=4, wait=10):
    """Trả PR đã merge vào main có merge_commit_sha đúng bằng sha, hoặc None.

    Thử lại vài lần: ngay sau khi merge, liên kết commit–PR đôi khi chưa kịp
    hiện, và báo nhầm thì người dùng sẽ học cách lờ cảnh báo đi.
    """
    for attempt in range(attempts):
        for pr in api("GET", f"/repos/{repo}/commits/{sha}/pulls") or []:
            if pr.get("merged_at") and pr.get("merge_commit_sha") == sha and pr["base"]["ref"] == "main":
                return pr
        if attempt + 1 < attempts:
            time.sleep(wait)
    return None


def reasons_for(event, pr):
    reasons = []
    if event.get("forced"):
        reasons.append("Force-push: lịch sử main đã bị viết lại.")
    if pr is None:
        reasons.append("Commit đầu mút không phải merge commit của PR nào đã merge vào main.")
    return reasons


def already_reported(repo, sha):
    for issue in api("GET", f"/repos/{repo}/issues?state=all&per_page=100") or []:
        if sha[:7] in issue.get("title", ""):
            return issue
    return None


def issue_body(event, sha, reasons, repo):
    lines = ["Main vừa nhận thay đổi **không đi qua PR**. Workflow này chỉ cảnh báo, không chặn được.", ""]
    lines += ["**Lý do:**"] + [f"- {r}" for r in reasons] + [""]
    lines += [
        f"- Commit đầu mút: `{sha}`",
        f"- Người đẩy (theo GitHub): `{(event.get('pusher') or {}).get('name', '?')}`"
        f" / sender `{(event.get('sender') or {}).get('login', '?')}`",
    ]
    if event.get("compare"):
        lines.append(f"- So sánh: {event['compare']}")
    commits = event.get("commits") or []
    if commits:
        lines += ["", f"**{len(commits)} commit trong lần đẩy:**"]
        for c in commits[:30]:
            first = (c.get("message") or "").splitlines()[0][:120]
            lines.append(f"- `{c.get('id', '')[:7]}` {first} — {(c.get('author') or {}).get('name', '?')}")
    lines += [
        "",
        "**Nếu anh không làm việc này:**",
        "1. Vào github.com → Settings → Applications, Personal access tokens, SSH keys, Sessions; thu hồi thứ không nhận ra.",
        "2. Hoàn tác bằng một PR `git revert`, không force-push.",
        "",
        "Nếu là cố ý thì đóng issue kèm một dòng lý do.",
        "",
        f"_Tạo tự động bởi `.github/workflows/canh-bao-push-main.yml` trên {repo}._",
    ]
    return "\n".join(lines)


def main():
    repo = os.environ["GITHUB_REPOSITORY"]
    event_name = os.environ.get("GITHUB_EVENT_NAME", "push")
    dry_run = os.environ.get("DRY_RUN", "").lower() == "true"
    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as f:
        event = json.load(f)

    if event_name == "workflow_dispatch":
        sha = os.environ.get("CHECK_SHA", "").strip()
        event = {"repository": event.get("repository"), "sender": event.get("sender")}
    else:
        sha = event.get("after", "")
        if event.get("deleted"):
            print("Nhánh bị xoá; không có commit để kiểm.")
            return 0
    if len(sha) != 40:
        print(f"SHA không hợp lệ: {sha!r}")
        return 2

    pr = merged_pr(repo, sha)
    reasons = reasons_for(event, pr)
    if not reasons:
        print(f"OK: {sha[:7]} là merge commit của PR #{pr['number']}.")
        return 0

    title = f"Cảnh báo: main nhận commit không qua PR — {sha[:7]}"
    print("CẢNH BÁO:", title, *reasons, sep="\n  ")
    if dry_run:
        print("DRY_RUN: không tạo issue.")
        return 0
    existing = already_reported(repo, sha)
    if existing:
        print(f"Đã có issue #{existing['number']} cho commit này; không tạo trùng.")
        return 0
    owner = ((event.get("repository") or {}).get("owner") or {}).get("login") or repo.split("/")[0]
    body = issue_body(event, sha, reasons, repo)
    try:
        issue = api("POST", f"/repos/{repo}/issues", {"title": title, "body": body, "assignees": [owner]})
    except urllib.error.HTTPError as exc:
        # Gan nguoi nhan co the bi tu choi; van phai tao duoc issue.
        print(f"Tạo issue kèm assignee lỗi {exc.code}; thử lại không assignee.")
        issue = api("POST", f"/repos/{repo}/issues", {"title": title, "body": body})
    print(f"Đã tạo issue #{issue['number']}: {issue['html_url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
