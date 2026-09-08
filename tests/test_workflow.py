import asyncio
import json
import re
from io import BytesIO
import httpx
import pytest
from docx import Document
from pypdf import PdfWriter
from fastapi.testclient import TestClient
from fastmcp import Client
from tro_ly_van_ban.domain import Extraction, validate_evidence
from tro_ly_van_ban.service import Service
from tro_ly_van_ban.model import ModelUnavailable
from tro_ly_van_ban.mcp_server import create_mcp
from tro_ly_van_ban.web import create_app


@pytest.fixture
def service(tmp_path):
    return Service(tmp_path, mode="demo")


def sample(service):
    return service.ingest("mau.txt", "Số: 12/ABC\nGửi báo cáo trước ngày 20/09/2026.".encode())


def content():
    return {"number": {"value": "12/ABC", "block_id": "b1", "quote": "Số: 12/ABC"}, "tasks": [{"request": {"value": "Gửi báo cáo", "block_id": "b2", "quote": "Gửi báo cáo trước ngày 20/09/2026."}, "deadline": {"value": "20/09/2026", "block_id": "b2", "quote": "Gửi báo cáo trước ngày 20/09/2026."}}]}


def test_dedup_persistence_and_version_bound_approval(service):
    doc_id = sample(service)
    assert service.ingest("renamed.txt", "Số: 12/ABC\nGửi báo cáo trước ngày 20/09/2026.".encode()) == doc_id
    assert len(service.listing()) == 1
    service.save(doc_id, content())
    old = service.get(doc_id)["latest"]
    service.save(doc_id, content(), expected_version=1)
    with pytest.raises(ValueError):
        service.review(doc_id, 1, old["hash"], "approved", "")
    latest = service.get(doc_id)["latest"]
    service.review(doc_id, 2, latest["hash"], "approved", "Đã đối chiếu")
    reopened = Service(service.root, mode="demo")
    assert reopened.get(doc_id)["state"] == "approved"
    assert reopened.tasks()[0]["deadline"]["value"] == "20/09/2026"
    assert reopened.get(doc_id)["approvals"][0]["reason"] == "Đã đối chiếu"
    assert Document(service.path("drafts", f"{doc_id}-2.docx")).paragraphs
    with pytest.raises(ValueError):
        service.save(doc_id, content(), expected_version=1)


def test_fabricated_source_rejected(service):
    doc_id = sample(service)
    value = content()
    value["number"]["value"] = "99/FAKE"
    with pytest.raises(ValueError):
        service.save(doc_id, value)
    value = content()
    value["number"]["block_id"] = "../other"
    with pytest.raises(ValueError):
        service.save(doc_id, value)
    assert service.get(doc_id)["latest"] is None


def test_missing_model_persisted(service, monkeypatch):
    service.mode = "ollama"
    def offline(*args, **kwargs):
        raise httpx.ConnectError("offline")
    monkeypatch.setattr(httpx.Client, "post", offline)
    doc_id = sample(service)
    with pytest.raises(ModelUnavailable):
        service.run(doc_id)
    assert Service(service.root).get(doc_id)["state"] == "model_unavailable"


def test_demo_and_scan(service):
    doc_id = sample(service)
    service.run(doc_id)
    value = json.loads(service.get(doc_id)["latest"]["content"])
    assert value["tasks"] == []
    assert "DEMO" in value["missing"][0]
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    data = BytesIO()
    writer.write(data)
    scan = service.ingest("scan.pdf", data.getvalue())
    assert service.get(scan)["state"] == "needs_ocr"
    with pytest.raises(ValueError):
        service.run(scan)


def test_web_csrf_origin_and_review(service):
    with TestClient(create_app(service), base_url="http://127.0.0.1") as client:
        page = client.get("/")
        csrf = re.search('name="csrf" value="([^"]+)"', page.text).group(1)
        assert client.post("/upload", files={"file": ("x.txt", b"test")}).status_code == 403
        assert client.post("/upload", data={"csrf": csrf}, headers={"origin": "https://evil.example"}, files={"file": ("x.txt", b"test")}).status_code == 403
        response = client.post("/upload", data={"csrf": csrf}, files={"file": ("x.txt", b"test")})
        assert response.status_code == 200
        assert "x.txt" in response.text


def test_mcp_client_and_no_approval_tool(service):
    doc_id = sample(service)
    async def run():
        async with Client(create_mcp(service)) as client:
            names = {t.name for t in await client.list_tools()}
            assert names == {"list_documents", "read_document", "get_evidence"}
            result = await client.call_tool("get_evidence", {"document_id": doc_id, "block_ids": ["b1"]})
            assert "12/ABC" in str(result)
    asyncio.run(run())


def test_path_and_file_limits(service, tmp_path):
    with pytest.raises(ValueError):
        service.path("originals", "../../escape")
    with pytest.raises(ValueError):
        service.ingest("old.doc", b"anything")
    with pytest.raises(ValueError):
        service.ingest("huge.txt", b"x" * (10 * 1024 * 1024 + 1))
    outside = tmp_path / "outside"
    outside.write_text("keep")
    link = service.root / "originals" / "link"
    link.symlink_to(outside)
    with pytest.raises(ValueError):
        service.path("originals", "link")


def test_edit_form_and_reject_flow(service):
    doc_id = sample(service)
    service.run(doc_id)
    with TestClient(create_app(service), base_url="http://127.0.0.1") as client:
        response = client.get(f"/documents/{doc_id}")
        csrf = re.search('name="csrf" value="([^"]+)"', response.text).group(1)
        response = client.post(f"/documents/{doc_id}/edit", data={
            "csrf": csrf, "version": 1, "number": "12/ABC", "number_block": "b1",
            "request_0": "Gửi báo cáo", "request_0_block": "b2",
            "deadline_0": "20/09/2026", "deadline_0_block": "b2",
        })
        assert response.status_code == 200
        latest = service.get(doc_id)["latest"]
        assert latest["version"] == 2
        response = client.post(f"/documents/{doc_id}/review", data={
            "csrf": csrf, "version": 2, "hash": latest["hash"], "action": "rejected", "reason": "Cần sửa",
        })
        assert service.get(doc_id)["state"] == "rejected"
        assert service.tasks()[0]["state"] == "rejected"
        with pytest.raises(ValueError):
            service.review(doc_id, 2, latest["hash"], "approved", "")


def test_docx_parser_and_bad_input(service):
    document = Document()
    document.add_paragraph("Yêu cầu báo cáo.")
    document.add_table(rows=1, cols=1).cell(0, 0).text = "Dữ liệu bảng"
    stream = BytesIO()
    document.save(stream)
    doc_id = service.ingest("test.docx", stream.getvalue())
    blocks = service.get(doc_id)["blocks"]
    assert blocks[0]["location"] == "Đoạn 1"
    assert blocks[1]["location"] == "Bảng 1, hàng 1"
    with pytest.raises(ValueError, match="Không đọc được file"):
        service.ingest("broken.pdf", b"broken")


def test_large_model_input_does_not_call_network(service, monkeypatch):
    service.mode = "ollama"
    doc_id = service.ingest("long.txt", ("dữ liệu " * 1000).encode())
    def forbidden(*args, **kwargs):
        raise AssertionError("Network must not be called")
    monkeypatch.setattr(httpx.Client, "post", forbidden)
    with pytest.raises(ValueError, match="5.000"):
        service.run(doc_id)
    assert service.get(doc_id)["state"] == "error"
