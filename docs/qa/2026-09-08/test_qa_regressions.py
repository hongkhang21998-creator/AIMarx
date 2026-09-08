"""Bộ tái hiện QA ngày 08/09/2026 — bốn nhóm lỗi giao ở Issue #5.

Cả bảy ca ĐANG ĐỎ trên main tại `822ce30`. Chúng được đánh `xfail(strict=True)`
để CI xanh mà lỗi vẫn nằm trong repo chứ không nằm trong trí nhớ ai đó.

`strict=True` là chủ ý: khi lỗi được sửa, ca tương ứng chuyển thành XPASS và
**làm đỏ CI**. Người sửa buộc phải quay lại gỡ marker, nên không có đường nào
để một bản sửa lặng lẽ trôi qua mà không ai cập nhật trạng thái ở đây.

Không xóa hay nới assertion để làm xanh. Nếu một assertion sai so với thiết kế
đã chốt thì sửa assertion kèm lý do trong PR, không phải xóa.
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

@pytest.mark.xfail(strict=True, reason="QA-01: run() lỗi ghi đè documents.state, xóa mất trạng thái đã duyệt")
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

@pytest.mark.xfail(strict=True, reason="QA-03: /run bỏ qua version nên tab cũ vẫn thay được phiên bản hiện hành")
def test_stale_run_cannot_supersede_newer_version(setup):
    s,d=setup
    c,token=client(s)
    s.save(d, {}, expected_version=1)
    response=c.post(f'/documents/{d}/run',data={'csrf':token,'version':'1'},follow_redirects=False)
    assert s.get(d)['latest']['version']==2, f"stale run returned {response.status_code}, created v3"

@pytest.mark.xfail(strict=True, reason="QA-04: thiếu field biểu mẫu ném KeyError thành HTTP 500")
@pytest.mark.parametrize('route,data',[('manual',{}),('save',{'version':'1'}),('review',{'version':'1'})])
def test_missing_form_fields_are_client_errors(setup,route,data):
    s,d=setup
    c,token=client(s)
    response=c.post(f'/documents/{d}/{route}',data={'csrf':token,**data},follow_redirects=False)
    assert 400<=response.status_code<500, (route,response.status_code,response.text[:100])

@pytest.mark.xfail(strict=True, reason="QA-04: JSON hỏng trả trang lỗi nhưng HTTP vẫn 200")
def test_invalid_json_has_error_http_status(setup):
    s,d=setup
    c,token=client(s)
    response=c.post(f'/documents/{d}/save',data={'csrf':token,'version':'1','content':'{'},follow_redirects=False)
    assert 400<=response.status_code<500, (response.status_code,response.text[-200:])

@pytest.mark.xfail(strict=True, reason="QA-02: route ghi async gọi thẳng service nên chặn event loop suốt lúc inference")
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
            running=asyncio.create_task(ac.post(f'/documents/{d}/run',data={'csrf':token}))
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
