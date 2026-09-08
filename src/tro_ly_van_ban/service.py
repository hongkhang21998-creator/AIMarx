import asyncio
import hashlib
import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import TypedDict
from docx import Document
from langgraph.graph import StateGraph, START, END
from .domain import Extraction, validate_evidence
from .model import extract, ModelUnavailable
from .parser import parse, MAX_BYTES


class Flow(TypedDict):
    blocks: list[dict]
    mode: str
    model: str
    result: dict


def infer(state: Flow):
    return {"result": extract(state["blocks"], state["mode"], state["model"]).model_dump()}


def validate(state: Flow):
    validate_evidence(Extraction.model_validate(state["result"]), state["blocks"])
    return {}


builder = StateGraph(Flow)
builder.add_node("extract", infer)
builder.add_node("validate", validate)
builder.add_edge(START, "extract")
builder.add_edge("extract", "validate")
builder.add_edge("validate", END)
graph = builder.compile()


class Service:
    def __init__(self, root: str | Path, mode="ollama", model="qwen3:0.6b"):
        if mode not in {"ollama", "demo"}:
            raise ValueError("TLVB_MODE must be ollama or demo")
        self.root = Path(root).absolute()
        if self.root.is_symlink():
            raise ValueError("Data directory cannot be a symlink")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root = self.root.resolve()
        for folder in ("originals", "drafts"):
            path = self.root / folder
            if path.is_symlink():
                raise ValueError("Storage directory cannot be a symlink")
            path.mkdir(exist_ok=True, mode=0o700)
        if (self.root / "state.sqlite3").is_symlink():
            raise ValueError("Database cannot be a symlink")
        self.mode, self.model = mode, model
        self.lock = threading.RLock()
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY, name TEXT, suffix TEXT, blocks TEXT, warnings TEXT, state TEXT, error TEXT);
            CREATE TABLE IF NOT EXISTS versions(document_id TEXT, version INTEGER, content TEXT, hash TEXT, mode TEXT, model TEXT, PRIMARY KEY(document_id,version));
            CREATE TABLE IF NOT EXISTS approvals(document_id TEXT, version INTEGER, hash TEXT, action TEXT, reason TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
            ''')

            if "draft_hash" not in {row[1] for row in db.execute("PRAGMA table_info(versions)")}:
                db.execute("ALTER TABLE versions ADD COLUMN draft_hash TEXT NOT NULL DEFAULT ''")

    def db(self):
        conn = sqlite3.connect(self.root / "state.sqlite3", timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def path(self, folder, name):
        path = self.root / folder / name
        if path.is_symlink() or path.resolve().parent != (self.root / folder).resolve():
            raise ValueError("Đường dẫn kho không hợp lệ")
        return path

    def listing(self):
        with self.db() as db:
            return [dict(x) for x in db.execute("SELECT id,name,state,error FROM documents ORDER BY rowid DESC")]

    def get(self, document_id):
        with self.db() as db:
            row = db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
            if row is None:
                raise ValueError("Không tìm thấy tài liệu")
            result = dict(row)
            result["blocks"] = json.loads(result["blocks"])
            result["warnings"] = json.loads(result["warnings"])
            latest = db.execute("SELECT * FROM versions WHERE document_id=? ORDER BY version DESC LIMIT 1", (document_id,)).fetchone()
            result["latest"] = dict(latest) if latest else None
            result["approvals"] = [dict(x) for x in db.execute("SELECT * FROM approvals WHERE document_id=?", (document_id,))]
            return result

    def ingest(self, name, data):
        if not data or len(data) > MAX_BYTES:
            raise ValueError("File rỗng hoặc vượt 10 MB")
        suffix = Path(name).suffix.lower()
        if suffix not in {".txt", ".pdf", ".docx"}:
            raise ValueError("Chỉ nhận PDF, DOCX, TXT")
        digest = hashlib.sha256(data).hexdigest()
        with self.lock:
            with self.db() as db:
                if db.execute("SELECT 1 FROM documents WHERE id=?", (digest,)).fetchone():
                    return digest
            try:
                blocks, warnings = parse(data, suffix)
            except Exception as exc:
                raise ValueError("Không đọc được file: " + str(exc)[:200]) from exc
            target = self.path("originals", digest + suffix)
            if target.exists():
                if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                    raise ValueError("Bản gốc không khớp hash")
            else:
                with target.open("xb") as out:
                    out.write(data)
                target.chmod(0o400)
            state = "needs_ocr" if not blocks or any("cần OCR" in w for w in warnings) else "ready"
            with self.db() as db:
                db.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?)", (digest, Path(name).name[:200], suffix, json.dumps(blocks, ensure_ascii=False), json.dumps(warnings, ensure_ascii=False), state, ""))
        return digest

    def run(self, document_id):
        with self.lock:
            doc = self.get(document_id)
            if doc["state"] == "needs_ocr":
                raise ValueError("Cần OCR đầy đủ trước khi xử lý")
            try:
                from fastmcp import Client
                from .mcp_server import create_mcp
                async def read_source():
                    async with Client(create_mcp(self)) as client:
                        response = await client.call_tool("read_document", {"document_id": document_id})
                        return response.data
                source = asyncio.run(read_source())
                result = graph.invoke({"blocks": source["blocks"], "mode": self.mode, "model": self.model})
                return self.save(document_id, result["result"], provenance=self.mode)
            except Exception as exc:
                with self.db() as db:
                    db.execute("UPDATE documents SET state=?,error=? WHERE id=?", ("model_unavailable" if isinstance(exc, ModelUnavailable) else "error", str(exc)[:500], document_id))
                raise

    def save(self, document_id, content, expected_version=None, provenance="manual"):
        with self.lock:
            doc = self.get(document_id)
            current = doc["latest"]["version"] if doc["latest"] else 0
            if expected_version is not None and expected_version != current:
                raise ValueError("Phiên bản đã thay đổi; tải lại trang")
            value = Extraction.model_validate(content)
            validate_evidence(value, doc["blocks"])
            encoded = json.dumps(value.model_dump(), ensure_ascii=False, sort_keys=True)
            digest = hashlib.sha256(encoded.encode()).hexdigest()
            version = current + 1
            draft = Document()
            draft.add_heading("DỰ THẢO PHIẾU XỬ LÝ — CHỜ KIỂM TRA", 0)
            draft.add_paragraph(f"Nguồn: {doc['name']} | phiên bản {version} | chế độ {provenance}")
            for label, field in [("Số ký hiệu", value.number), ("Cơ quan", value.agency), ("Ngày văn bản", value.document_date)]:
                draft.add_paragraph(f"{label}: {field.value if field else '[CẦN BỔ SUNG]'}")
            for task in value.tasks:
                draft.add_paragraph(f"Việc đề xuất: {task.request.value}\nHạn nguyên văn: {task.deadline.value if task.deadline else '[CHƯA XÁC ĐỊNH]'}")
            for item in value.missing:
                draft.add_paragraph("[CẦN BỔ SUNG] " + item)
            draft.add_heading("Trích nguồn để kiểm tra", 1)
            draft.add_paragraph(encoded)
            target = self.path("drafts", f"{document_id}-{version}.docx")
            temp = self.path("drafts", f"{document_id}-{version}.tmp")
            draft.save(temp)
            os.replace(temp, target)
            target.chmod(0o400)
            draft_hash = hashlib.sha256(target.read_bytes()).hexdigest()
            with self.db() as db:
                db.execute("INSERT INTO versions(document_id,version,content,hash,mode,model,draft_hash) VALUES(?,?,?,?,?,?,?)", (document_id, version, encoded, digest, provenance, self.model if provenance == "ollama" else "", draft_hash))
                db.execute("UPDATE documents SET state='awaiting_review',error='' WHERE id=?", (document_id,))
            return version

    def review(self, document_id, version, digest, action, reason):
        if action not in {"approved", "rejected"}:
            raise ValueError("Hành động không hợp lệ")
        with self.lock, self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            latest = db.execute("SELECT * FROM versions WHERE document_id=? ORDER BY version DESC LIMIT 1", (document_id,)).fetchone()
            state = db.execute("SELECT state FROM documents WHERE id=?", (document_id,)).fetchone()
            if not latest or latest["version"] != version or latest["hash"] != digest or state["state"] != "awaiting_review":
                raise ValueError("Phiên bản cũ hoặc đã duyệt; tải lại trang")
            db.execute("INSERT INTO approvals(document_id,version,hash,action,reason) VALUES(?,?,?,?,?)", (document_id, version, digest, action, reason[:2000]))
            db.execute("UPDATE documents SET state=? WHERE id=?", (action, document_id))

    def tasks(self):
        result = []
        for doc in self.listing():
            full = self.get(doc["id"])
            if full["latest"]:
                for task in json.loads(full["latest"]["content"])["tasks"]:
                    result.append({"document_id": doc["id"], "version": full["latest"]["version"], "state": doc["state"], **task})
        return result
