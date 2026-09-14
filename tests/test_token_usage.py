import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import httpx
import pytest
from fastapi.testclient import TestClient
from tro_ly_van_ban import model
from tro_ly_van_ban.service import Service, Conflict
from tro_ly_van_ban.token_usage import capture_usage
from tro_ly_van_ban.web import create_app


@pytest.fixture
def service(tmp_path):
    return Service(tmp_path / "store", mode="ollama")


def reply(monkeypatch, **overrides):
    payload = {"message": {"content": '{"cac_viec":[],"thong_tin_thieu":[]}'},
               "prompt_eval_count": 100, "eval_count": 20,
               "eval_duration": 2_000_000_000, "total_duration": 4_000_000_000}
    payload.update(overrides)
    def post(self, url, **kwargs):
        assert url == "http://127.0.0.1:11434/api/chat"
        assert kwargs["json"]["stream"] is False
        return httpx.Response(200, json=payload, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx.Client, "post", post)


def run(service):
    doc = service.ingest("private-name.txt", "Đề nghị gửi báo cáo.".encode())
    service.run(doc)
    return doc


def test_graph_counts_each_real_call_and_persists_restart(service, monkeypatch):
    reply(monkeypatch)
    doc = run(service)
    service.run(doc, expected_version=1)
    restored = Service(service.root)
    data = restored.token_usage.summary("all")
    assert data["totals"]["calls"] == 2
    assert data["totals"]["input_tokens"] == 200
    assert data["totals"]["output_tokens"] == 40
    assert data["totals"]["timed_ns"] == 4_000_000_000
    assert data["totals"]["incomplete"] == 0
    assert all(row["state"] == "received" for row in data["recent"])
    assert "private-name" not in json.dumps(data)
    with service.db() as conn:
        assert "Đề nghị" not in str([tuple(row) for row in conn.execute("SELECT * FROM ollama_usage")])


def test_invalid_generated_content_still_consumed_tokens(service, monkeypatch):
    reply(monkeypatch, message={"content": "not JSON"})
    with pytest.raises(ValueError):
        run(service)
    data = service.token_usage.summary("all")
    assert data["totals"]["input_tokens"] == 100
    assert data["totals"]["output_tokens"] == 20
    assert data["recent"][0]["state"] == "received"
    assert service.get(service.listing()[0]["id"])["latest"] is None


def test_evidence_rejected_still_counted(service, monkeypatch):
    reply(monkeypatch, message={"content": json.dumps({"cac_viec": [
        {"viec_can_lam": {"ma_doan": "b1", "gia_tri": "bịa đặt"}}], "thong_tin_thieu": []})})
    with pytest.raises(ValueError):
        run(service)
    assert service.token_usage.summary("all")["totals"]["output_tokens"] == 20
    assert service.get(service.listing()[0]["id"])["latest"] is None


def test_network_failure_unknown_not_zero(service, monkeypatch):
    def offline(*args, **kwargs):
        raise httpx.ConnectError("offline")
    monkeypatch.setattr(httpx.Client, "post", offline)
    with pytest.raises(model.ModelUnavailable):
        run(service)
    data = service.token_usage.summary("all")
    assert data["totals"]["calls"] == data["totals"]["incomplete"] == data["totals"]["failed"] == 1
    assert data["totals"]["input_tokens"] is None
    assert data["totals"]["output_tokens"] is None


@pytest.mark.parametrize("bad", [None, -1, True, 1.5, "100", 10**30])
def test_bad_metrics_remain_unknown(service, monkeypatch, bad):
    reply(monkeypatch, prompt_eval_count=bad, eval_count=bad, eval_duration=bad)
    run(service)
    totals = service.token_usage.summary("all")["totals"]
    assert totals["input_tokens"] is totals["output_tokens"] is totals["timed_ns"] is None
    assert totals["incomplete"] == 1


def test_zero_is_known_and_optional_duration_missing(service, monkeypatch):
    reply(monkeypatch, prompt_eval_count=0, eval_count=0, eval_duration=None)
    run(service)
    totals = service.token_usage.summary("all")["totals"]
    assert totals["input_tokens"] == totals["output_tokens"] == totals["incomplete"] == 0
    assert totals["timed_ns"] is None


def test_demo_manual_stale_and_oversize_do_not_count(service, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("must not call HTTP")
    monkeypatch.setattr(httpx.Client, "post", forbidden)
    service.mode = "demo"
    doc = run(service)
    latest = service.get(doc)["latest"]
    service.save(doc, json.loads(latest["content"]), expected_version=1)
    service.mode = "ollama"
    with pytest.raises(Conflict):
        service.run(doc, expected_version=1)
    large = service.ingest("large.txt", ("Tài liệu dài " * 500).encode())
    with pytest.raises(ValueError):
        service.run(large)
    assert service.token_usage.summary("all")["totals"]["calls"] == 0


def test_pending_survives_restart_and_finish_is_idempotent(service):
    request_id = service.token_usage.start("m")
    restored = Service(service.root)
    assert restored.token_usage.summary("all")["totals"]["pending"] == 1
    restored.token_usage.finish(request_id, {"prompt_eval_count": 10, "eval_count": 2}, "received")
    restored.token_usage.finish(request_id, {"prompt_eval_count": 500, "eval_count": 500}, "received")
    assert restored.token_usage.summary("all")["totals"]["input_tokens"] == 10


def test_utc7_boundaries_filters_and_recent_limit(service):
    now = datetime(2026, 9, 14, 1, tzinfo=timezone.utc)
    with service.db() as conn:
        for i in range(60):
            conn.execute("INSERT INTO ollama_usage VALUES(?,?,?,'received',10,2,100,200)",
                         (str(i), "2026-09-13T17:00:00+00:00", "m"))
        for key, date in [("yesterday", "2026-09-13T16:59:59+00:00"),
                          ("old", "2026-01-01T00:00:00+00:00"),
                          ("future", "2026-09-15T00:00:00+00:00")]:
            conn.execute("INSERT INTO ollama_usage VALUES(?,?,?,'received',10,2,100,200)", (key, date, "m"))
    today = service.token_usage.summary("today", now)
    assert today["totals"]["calls"] == 60
    assert len(today["recent"]) == 50
    assert today["activity"][0]["calls"] == 60
    assert service.token_usage.summary("7d", now)["totals"]["calls"] == 61
    assert service.token_usage.summary("30d", now)["totals"]["calls"] == 61
    assert service.token_usage.summary("all", now)["totals"]["calls"] == 62
    assert len(service.token_usage.summary("all", now)["activity"]) == 84
    with pytest.raises(ValueError):
        service.token_usage.summary("bad")


def test_context_isolated_across_stores_and_reset_after_failure(service, tmp_path, monkeypatch):
    reply(monkeypatch)
    second = Service(tmp_path / "second")
    def call(store, name):
        with capture_usage(store):
            model.chat([], name, {})
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(call, service.token_usage, "one")
        b = pool.submit(call, second.token_usage, "two")
        a.result()
        b.result()
    assert service.token_usage.summary("all")["models"][0]["model"] == "one"
    assert second.token_usage.summary("all")["models"][0]["model"] == "two"
    with pytest.raises(RuntimeError), capture_usage(service.token_usage):
        raise RuntimeError()
    model.chat([], "uncaptured", {})
    assert service.token_usage.summary("all")["totals"]["calls"] == 1


def test_dashboard_filters_xss_and_empty_state(service, monkeypatch):
    client = TestClient(create_app(service), base_url="http://127.0.0.1")
    empty = client.get("/usage")
    assert empty.status_code == 200
    assert "Chưa có hoạt động" in empty.text
    assert 'href="/usage"' in client.get("/").text
    reply(monkeypatch)
    service.model = '<script>alert("x")</script>'
    run(service)
    for period in ("today", "7d", "30d", "all"):
        page = client.get(f"/usage?period={period}&theme=light")
        assert page.status_code == 200
        assert 'data-theme="light"' in page.text
        assert "&lt;script&gt;" in page.text
        assert "<script>" not in page.text
        assert "100" in page.text and "20" in page.text
        assert "10.0" in page.text
        assert "Content-Security-Policy" in page.headers
    assert client.get("/usage?period=unknown").status_code == 400
    assert 'data-theme="dark"' in client.get('/usage?theme=%22%3E').text
