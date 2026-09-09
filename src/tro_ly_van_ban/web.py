import html
import json
import os
import secrets
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .service import Service
from .parser import MAX_BYTES


def create_app(service=None):
    service = service or Service(os.getenv("TLVB_DATA", "data"), os.getenv("TLVB_MODE", "ollama"), os.getenv("TLVB_MODEL", "qwen3:0.6b"))
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.service = service
    token = secrets.token_urlsafe(32)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    esc = lambda value: html.escape(str(value), quote=True)
    hidden = f'<input type="hidden" name="csrf" value="{token}">'

    @app.middleware("http")
    async def security(request, call_next):
        if request.method not in {"GET", "HEAD"}:
            origin = request.headers.get("origin")
            if origin and origin != f"{request.url.scheme}://{request.headers.get('host')}":
                return JSONResponse({"error": "Origin không hợp lệ"}, 403)
            if "content-length" not in request.headers or "transfer-encoding" in request.headers:
                return JSONResponse({"error": "Cần Content-Length; không nhận tải chunked"}, 411)
            try:
                if int(request.headers.get("content-length", "0")) > MAX_BYTES + 100000:
                    return JSONResponse({"error": "Yêu cầu quá lớn"}, 413)
            except ValueError:
                return JSONResponse({"error": "Content-Length không hợp lệ"}, 400)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'unsafe-inline'; frame-ancestors 'none'; form-action 'self'"
        return response

    async def checked_form(request):
        body = await request.body()
        if len(body) > MAX_BYTES + 100000:
            raise ValueError("Yêu cầu quá lớn")
        form = await request.form(max_part_size=MAX_BYTES)
        if not secrets.compare_digest(str(form.get("csrf", "")), token):
            from fastapi import HTTPException
            raise HTTPException(403, "CSRF không hợp lệ; tải lại trang")
        return form

    def warn_banner():
        return ''.join('<p class="warn"><b>Cảnh báo môi trường:</b> ' + esc(w) + '</p>' for w in getattr(service, "warnings", []))

    def page(body):
        return HTMLResponse('<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Trợ lý văn bản</title><style>body{font:17px system-ui;max-width:1100px;margin:30px auto;padding:20px;background:#f5f7fa;color:#182b3a}textarea{width:100%;min-height:320px}pre{white-space:pre-wrap}button,input{padding:9px;margin:5px}article{background:white;padding:20px;margin:15px 0;border:1px solid #ccd}a{color:#075e8f}.warn{background:#fff3cd;border:1px solid #e0b000;padding:12px;margin:12px 0}</style><a href="/">Kho tài liệu</a> · <a href="/tasks">Sổ công việc</a><h1>Trợ lý văn bản local</h1><p>Chế độ: <strong>' + esc(service.mode) + '</strong>. Phiếu thử nghiệm; chưa phải mẫu văn bản hành chính được xác nhận.</p>' + warn_banner() + body + '</html>')

    @app.exception_handler(ValueError)
    async def bad_value(request, exc):
        return page('<h2>Chưa thực hiện được</h2><p>' + esc(exc) + '</p>')

    @app.get("/", response_class=HTMLResponse)
    def home():
        body = '<form action="/upload" method="post" enctype="multipart/form-data">' + hidden + '<label>Nhập PDF, DOCX, TXT (tối đa 10 MB) <input type="file" name="file" required></label><button>Nhập tài liệu</button></form>'
        for doc in service.listing():
            body += f'<article><a href="/documents/{doc["id"]}">{esc(doc["name"])}</a> — {esc(doc["state"])}</article>'
        return page(body)

    @app.post("/upload")
    async def upload(request: Request):
        form = await checked_form(request)
        file = form.get("file")
        if file is None or not hasattr(file, "read"):
            raise ValueError("Chưa chọn file")
        data = await file.read(MAX_BYTES + 1)
        doc_id = service.ingest(file.filename or "file", data)
        return RedirectResponse(f"/documents/{doc_id}", 303)

    @app.get("/documents/{doc_id}")
    def document(doc_id: str):
        doc = service.get(doc_id)
        body = f'<h2>{esc(doc["name"])}</h2><p>Trạng thái: {esc(doc["state"])}</p>'
        # Trang thai duyet va ket qua lan chay la hai chuyen khac nhau; gop mot dong
        # thi loi trich xuat doc nhu thu da thay the trang thai duyet.
        if doc["error"]:
            nhan = "Model chưa sẵn sàng" if doc["error_kind"] == "model_unavailable" else "Lần xử lý gần nhất lỗi"
            body += f'<p class="warn"><b>{nhan}:</b> {esc(doc["error"])} — trạng thái duyệt ở trên giữ nguyên.</p>'
        body += f'<p>{esc("; ".join(doc["warnings"]))}</p>'
        body += f'<form action="/documents/{doc_id}/run" method="post">{hidden}<button>Trích xuất / thử lại (tạo phiên bản mới)</button></form>'
        if doc["state"] != "needs_ocr":
            current = doc["latest"]["version"] if doc["latest"] else 0
            body += f'<form action="/documents/{doc_id}/manual" method="post">{hidden}<input type="hidden" name="version" value="{current}"><button>Lập phiếu thủ công từ nguồn (bản mới)</button></form>'
        if doc["latest"]:
            latest = doc["latest"]
            disabled = " disabled" if doc["state"] != "awaiting_review" else ""
            body += "<p>Nguồn tạo phiên bản: " + esc(latest["mode"]) + "</p>"
            content = json.dumps(json.loads(latest["content"]), ensure_ascii=False, indent=2)
            data = json.loads(latest["content"])
            body += f'<h3>Phiếu xử lý</h3><form action="/documents/{doc_id}/edit" method="post">{hidden}<input type="hidden" name="version" value="{latest["version"]}">'
            def field(key, label, item):
                item = item or {}
                options = '<option value="">Chọn đoạn nguồn</option>'
                for block in doc["blocks"]:
                    selected = ' selected' if block["id"] == item.get("block_id") else ''
                    options += f'<option value="{esc(block["id"])}"{selected}>{esc(block["id"] + " · " + block["location"])}</option>'
                return f'<p><label>{label} <input name="{key}" value="{esc(item.get("value", ""))}" size="55"></label><label> Nguồn <select name="{key}_block">{options}</select></label></p>'
            for key, label in [("number", "Số ký hiệu"), ("agency", "Cơ quan"), ("document_date", "Ngày văn bản")]:
                body += field(key, label, data.get(key))
            body += '<h4>Công việc đề xuất</h4><p>Nhập nguyên văn từ nguồn. Để trống hạn khi chưa xác định. Xóa nội dung việc để bỏ việc đó.</p>'
            tasks = data["tasks"] + ([{}] if len(data["tasks"]) < 30 else [])
            for i, task in enumerate(tasks):
                body += field(f"request_{i}", f"Việc {i+1}", task.get("request"))
                body += field(f"deadline_{i}", "Hạn nguyên văn", task.get("deadline"))
            body += '<button>Lưu phiếu thành phiên bản mới</button></form>'
            if not latest["draft_hash"]:
                body += '<p class="warn">Phiên bản này chưa có <code>draft_hash</code> nên dự thảo DOCX <b>không xác minh được</b>. Không tải và không xác nhận được; hãy lưu lại thành phiên bản mới.</p>'
            body += '<p>' + esc('; '.join(data['missing'])) + '</p><details><summary>Dữ liệu JSON nâng cao</summary>'
            body += f'<h3>Phiên bản {latest["version"]}</h3><a href="/documents/{doc_id}/draft/{latest["version"]}">Tải DOCX dự thảo</a><form action="/documents/{doc_id}/save" method="post">{hidden}<input type="hidden" name="version" value="{latest["version"]}"><label>Sửa phiếu JSON (value phải nguyên văn trong quote; block_id xem nguồn)<textarea name="content">{esc(content)}</textarea></label><button>Lưu phiên bản mới</button></form></details>'
            body += f'<form action="/documents/{doc_id}/review" method="post">{hidden}<input type="hidden" name="version" value="{latest["version"]}"><input type="hidden" name="hash" value="{latest["hash"]}"><label>Lý do / ghi chú <input name="reason"></label><button name="action" value="approved"{disabled}>Tôi xác nhận phiên bản này</button><button name="action" value="rejected"{disabled}>Từ chối</button></form>'
        body += '<h3>Nguồn đối chiếu</h3>'
        for block in doc["blocks"]:
            body += f'<article><b>{esc(block["id"])} · {esc(block["location"])}</b><pre>{esc(block["text"])}</pre></article>'
        body += '<h3>Lịch sử duyệt</h3><pre>' + esc(json.dumps(doc["approvals"], ensure_ascii=False, indent=2)) + '</pre>'
        return page(body)

    @app.post("/documents/{doc_id}/run")
    async def run(doc_id: str, request: Request):
        await checked_form(request)
        try:
            from starlette.concurrency import run_in_threadpool
            await run_in_threadpool(service.run, doc_id)
        except Exception:
            pass  # service persists a bounded error message displayed on the document page
        return RedirectResponse(f"/documents/{doc_id}", 303)

    @app.post("/documents/{doc_id}/manual")
    async def manual(doc_id: str, request: Request):
        form = await checked_form(request)
        service.save(doc_id, {}, int(str(form["version"])), provenance="manual")
        return RedirectResponse(f"/documents/{doc_id}", 303)

    @app.post("/documents/{doc_id}/save")
    async def save(doc_id: str, request: Request):
        form = await checked_form(request)
        service.save(doc_id, json.loads(str(form["content"])), int(str(form["version"])))
        return RedirectResponse(f"/documents/{doc_id}", 303)

    @app.post("/documents/{doc_id}/edit")
    async def edit(doc_id: str, request: Request):
        form = await checked_form(request)
        doc = service.get(doc_id)
        sources = {b["id"]: b["text"] for b in doc["blocks"]}
        def value(key):
            text = str(form.get(key, "")).strip()
            if not text:
                return None
            block_id = str(form.get(key + "_block", ""))
            if block_id not in sources:
                raise ValueError("Chọn đoạn nguồn cho mỗi dữ kiện đã nhập")
            return {"value": text, "block_id": block_id, "quote": text}
        content = {key: value(key) for key in ("number", "agency", "document_date")}
        # Tai lieu chua co phien ban nao thi latest la None. Khong duoc de vo thanh
        # TypeError 500: cu di tiep de Service.save la cua chan duy nhat.
        content["missing"] = json.loads(doc["latest"]["content"])["missing"] if doc["latest"] else []
        content["tasks"] = []
        for i in range(30):
            task = value(f"request_{i}")
            if task:
                content["tasks"].append({"request": task, "deadline": value(f"deadline_{i}")})
        service.save(doc_id, content, int(str(form["version"])))
        return RedirectResponse(f"/documents/{doc_id}", 303)

    @app.post("/documents/{doc_id}/review")
    async def review(doc_id: str, request: Request):
        form = await checked_form(request)
        service.review(doc_id, int(str(form["version"])), str(form["hash"]), str(form["action"]), str(form.get("reason", "")))
        return RedirectResponse(f"/documents/{doc_id}", 303)

    @app.get("/documents/{doc_id}/draft/{version}")
    def draft(doc_id: str, version: int):
        doc = service.get(doc_id)
        if not doc["latest"] or version != doc["latest"]["version"]:
            raise ValueError("Chỉ tải bản hiện tại qua giao diện")
        path = service.verify_draft(doc_id, version, doc["latest"]["draft_hash"])
        return FileResponse(path, filename=f"du-thao-v{version}.docx")

    @app.get("/tasks")
    def tasks():
        body = '<h2>Sổ công việc</h2><p>Chỉ trạng thái approved là đã xác nhận. Hạn giữ nguyên văn, không tính lịch.</p>'
        for task in service.tasks():
            deadline = task['deadline']['value'] if task['deadline'] else 'Chưa xác định'
            body += f'<article><b>{esc(task["request"]["value"])}</b><p>Hạn: {esc(deadline)} · {esc(task["state"])}</p><a href="/documents/{task["document_id"]}">Xem nguồn và phiếu</a></article>'
        return page(body)

    return app


def main():
    import uvicorn
    uvicorn.run(create_app(), host="127.0.0.1", port=int(os.getenv("TLVB_PORT", "8765")), workers=1)


if __name__ == "__main__":
    main()
