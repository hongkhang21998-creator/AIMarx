import importlib.util
import json
from pathlib import Path
import httpx
import pytest
from tro_ly_van_ban import model
from tro_ly_van_ban.domain import validate_evidence
from tro_ly_van_ban.parser import parse
from tro_ly_van_ban.service import Service

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "UBND HUYỆN GIẢ LẬP A\nSố: 145/UBND-VP\nGiả Lập A, ngày 05 tháng 9 năm 2026\nĐề nghị các phòng gửi báo cáo trước ngày 20/09/2026."


def blocks():
    return parse(SOURCE.encode(), ".txt")[0]


class Reply:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        pass

    def json(self):
        return {"message": {"content": json.dumps(self.content, ensure_ascii=False)}}


@pytest.fixture
def ollama(monkeypatch):
    """Giả lập Ollama: ghi lại payload gửi đi, trả nội dung định sẵn."""
    sent = {}

    def post(self, url, json=None, **kwargs):
        sent.update(url=url, payload=json)
        return Reply(sent["reply"])

    monkeypatch.setattr(httpx.Client, "post", post)
    return sent


def vi_task(value, block="b4", deadline=None):
    return {"viec_can_lam": {"gia_tri": value, "ma_doan": block},
            "han_hoan_thanh": deadline and {"gia_tri": deadline, "ma_doan": block}}


def test_prompt_is_exactly_the_measured_v5():
    # Đổi prompt mà không đo lại thì mọi con số trong evals/ mất giá trị.
    spec = importlib.util.spec_from_file_location("run_eval", ROOT / "evals" / "extraction" / "run_eval.py")
    run_eval = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run_eval)
    assert model.SYSTEM_PROMPT == run_eval.VI_SYSTEM
    sample = blocks()
    assert model.build_messages(sample) == run_eval.vi_messages(sample, run_eval.VI_SYSTEM)


def test_request_uses_vietnamese_keys_no_quote_and_stays_local(ollama):
    ollama["reply"] = {"cac_viec": [], "thong_tin_thieu": []}
    model.extract(blocks(), "ollama", "qwen3:0.6b")
    assert ollama["url"] == "http://127.0.0.1:11434/api/chat"
    schema = json.dumps(ollama["payload"]["format"], ensure_ascii=False)
    assert "so_ky_hieu" in schema and "gia_tri" in schema
    assert '"number"' not in schema and "trich_nguyen_van" not in schema
    sent_blocks = json.loads(ollama["payload"]["messages"][1]["content"])
    assert set(sent_blocks[0]) == {"id", "text"}


def test_quote_comes_from_source_and_case_slip_is_snapped(ollama):
    ollama["reply"] = {"cac_viec": [vi_task("gửi báo cáo", deadline="20/09/2026")], "thong_tin_thieu": []}
    result = model.extract(blocks(), "ollama", "m")
    task = result.tasks[0]
    assert task.request.quote == "Đề nghị các phòng gửi báo cáo trước ngày 20/09/2026."
    assert task.request.value == "gửi báo cáo"
    validate_evidence(result, blocks())
    ollama["reply"] = {"cac_viec": [vi_task("ĐỀ NGHỊ CÁC PHÒNG")], "thong_tin_thieu": []}
    assert model.extract(blocks(), "ollama", "m").tasks[0].request.value == "Đề nghị các phòng"


def test_invented_value_is_still_rejected(ollama, tmp_path):
    # Ghép quote không được thành cửa hậu: giá trị không có trong nguồn vẫn bị chặn.
    ollama["reply"] = {"cac_viec": [vi_task("chuyển 50 triệu đồng")], "thong_tin_thieu": []}
    result = model.extract(blocks(), "ollama", "m")
    with pytest.raises(ValueError):
        validate_evidence(result, blocks())
    service = Service(tmp_path, mode="ollama")
    doc = service.ingest("a.txt", SOURCE.encode())
    with pytest.raises(ValueError):
        service.run(doc, expected_version=0)
    assert service.get(doc)["latest"] is None


def test_header_comes_from_rules_not_from_model(ollama):
    ollama["reply"] = {"so_ky_hieu": {"gia_tri": "1", "ma_doan": "b1"},
                       "co_quan_ban_hanh": {"gia_tri": "Bộ Công an", "ma_doan": "b1"},
                       "ngay_ban_hanh": None, "cac_viec": [], "thong_tin_thieu": []}
    result = model.extract(blocks(), "ollama", "m")
    assert (result.number.value, result.agency.value, result.document_date.value) == \
        ("145/UBND-VP", "UBND HUYỆN GIẢ LẬP A", "ngày 05 tháng 9 năm 2026")
    validate_evidence(result, blocks())


def test_no_rule_match_leaves_header_empty_even_if_model_answers(ollama):
    plain = parse("Kính gửi các phòng\nĐề nghị gửi báo cáo.".encode(), ".txt")[0]
    ollama["reply"] = {"co_quan_ban_hanh": {"gia_tri": "Kính gửi các phòng", "ma_doan": "b1"},
                       "cac_viec": [], "thong_tin_thieu": []}
    result = model.extract(plain, "ollama", "m")
    assert result.number is None and result.agency is None and result.document_date is None


def test_long_block_quote_is_windowed_around_value():
    source = "a " * 3000 + "gửi báo cáo" + " b" * 3000
    item = model.ground({"value": "gửi báo cáo", "block_id": "b1"}, {"b1": source})
    assert len(item["quote"]) <= model.QUOTE_MAX and "gửi báo cáo" in item["quote"] and item["quote"] in source
