"""Bộ tái hiện QA ngày 08/09/2026 — bốn nhóm lỗi giao ở Issue #5.

Cả bảy ca ĐANG ĐỎ trên main tại `822ce30`, và đã được đánh `xfail(strict=True)`
để CI xanh mà lỗi vẫn nằm trong repo chứ không nằm trong trí nhớ ai đó.

`strict=True` làm đúng việc của nó: mỗi lần một nhóm được sửa, ca tương ứng
chuyển thành XPASS và làm đỏ CI, buộc người sửa quay lại gỡ marker. **Cả bảy
marker nay đã gỡ hết** — QA-01/02 ở PR #7, QA-03/04 ở PR này — nên từ đây bộ
này là test hồi quy bình thường, phải xanh.

Không xóa hay nới assertion để làm xanh. Nếu một assertion sai so với thiết kế
đã chốt thì sửa assertion kèm lý do trong PR, không phải xóa. Một thay đổi duy
nhất thuộc loại đó: ca QA-02 nay gửi kèm `version` khi POST /run, vì QA-03 chốt
chính sách /run bắt buộc có version. Đó là bước đặt, không phải assertion — sửa
để ca vẫn đo đúng thứ nó sinh ra là độ trễ event loop, chứ không dừng ở 400.
"""
import json
import re
import pytest
from fastapi.testclient import TestClient
from tro_ly_van_ban.service import Service
from tro_ly_van_ban.model import ModelUnavailable
import tro_ly_van_ban.service as mod
from tro_ly_van_ban.web import create_app

@pytest.fixture
def setup(tmp_path):
    s = Service(tmp_path, mode='demo')
    d = s.ingest('synthetic.txt', b'So: 12/ABC\nGui bao cao')
    s.save(d, {'tasks':[{'request':{'value':'Gui bao cao','quote':'Gui bao cao','block_id':'b2'}}]})
    return s,d

def client(s):
    c = TestClient(create_app(s), base_url='http://127.0.0.1', raise_server_exceptions=False)
    token = re.search('name="csrf" value="([^"]+)"', c.get('/').text).group(1)
    return c,token

# QA-01 đã sửa: run() ghi lỗi vào error/error_kind, không còn đụng documents.state.
# Độ phủ mở rộng (awaiting_review, rejected, sai schema, DB cũ) nằm ở tests/test_workflow.py.
def test_failed_rerun_preserves_approved_version(setup, monkeypatch):
    s,d=setup
    v=s.get(d)['latest']
    s.review(d,1,v['hash'],'approved','checked')
    def fail(*a,**k): raise ModelUnavailable('synthetic offline')
    monkeypatch.setattr(mod.graph,'invoke',fail)
    with pytest.raises(ModelUnavailable): s.run(d)
    doc=s.get(d)
    assert doc['latest']['version']==1
    assert len(doc['approvals'])==1
    assert doc['state']=='approved', f"unchanged v1 now {doc['state']}; tasks={s.tasks()}"

# QA-03 đã sửa: Service.run() nhận expected_version và chốt nó trước khi gọi model.
def test_stale_run_cannot_supersede_newer_version(setup):
    s,d=setup
    c,token=client(s)
    s.save(d, {}, expected_version=1)
    response=c.post(f'/documents/{d}/run',data={'csrf':token,'version':'1'},follow_redirects=False)
    assert s.get(d)['latest']['version']==2, f"stale run returned {response.status_code}, created v3"

# QA-04 đã sửa: field bắt buộc đọc qua required()/required_int(), thiếu thì 400.
@pytest.mark.parametrize('route,data',[('manual',{}),('save',{'version':'1'}),('review',{'version':'1'})])
def test_missing_form_fields_are_client_errors(setup,route,data):
    s,d=setup
    c,token=client(s)
    response=c.post(f'/documents/{d}/{route}',data={'csrf':token,**data},follow_redirects=False)
    assert 400<=response.status_code<500, (route,response.status_code,response.text[:100])

# QA-04 đã sửa: trang lỗi mang đúng mã trạng thái thay vì luôn 200.
def test_invalid_json_has_error_http_status(setup):
    s,d=setup
    c,token=client(s)
    response=c.post(f'/documents/{d}/save',data={'csrf':token,'version':'1','content':'{'},follow_redirects=False)
    assert 400<=response.status_code<500, (response.status_code,response.text[-200:])

# QA-02 đã sửa: cả năm route ghi đi qua run_in_threadpool.
# Độ phủ từng route (kể cả /upload và /edit) nằm ở tests/test_workflow.py.
def test_concurrent_save_does_not_block_event_loop(setup, monkeypatch):
    import asyncio
    import threading
    import time
    import httpx
    s,d=setup
    c,token=client(s)
    app=c.app
    entered=threading.Event()
    def slow(*args,**kwargs):
        entered.set()
        time.sleep(1.2)
        return {'result':{}}
    monkeypatch.setattr(mod.graph,'invoke',slow)
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://127.0.0.1') as ac:
            running=asyncio.create_task(ac.post(f'/documents/{d}/run',data={'csrf':token,'version':'1'}))
            assert await asyncio.to_thread(entered.wait,5)
            async def heartbeat():
                start=time.monotonic()
                await asyncio.sleep(.05)
                return time.monotonic()-start
            beat=asyncio.create_task(heartbeat())
            saving=asyncio.create_task(ac.post(f'/documents/{d}/manual',data={'csrf':token,'version':'1'}))
            lag=await beat
            await asyncio.gather(running,saving)
            return lag
    lag=asyncio.run(exercise())
    assert lag<.5, f'event-loop heartbeat delayed {lag:.2f}s during 1.2s synthetic inference'
