import sqlite3
import pytest
import re
from fastapi.testclient import TestClient
from tro_ly_van_ban.service import Service
from tro_ly_van_ban.web import create_app


@pytest.mark.parametrize('label', ['unknown', 'internal', 'restricted', 'public', 'synthetic'])
def test_classification_survives_restart_and_duplicate(tmp_path, label):
    service = Service(tmp_path, 'demo')
    doc = service.ingest('a.txt', b'Example document', label)
    assert Service(tmp_path, 'demo').get(doc)['classification'] == label
    assert service.ingest('renamed.txt', b'Example document', 'public') == doc
    assert service.get(doc)['classification'] == label


@pytest.mark.parametrize('label', ['PUBLIC', '', None, True, ' public'])
def test_invalid_classification_creates_nothing(tmp_path, label):
    service = Service(tmp_path, 'demo')
    with pytest.raises(ValueError):
        service.ingest('a.txt', b'Example document', label)
    assert service.listing() == []


def test_old_database_defaults_unknown(tmp_path):
    service = Service(tmp_path, 'demo')
    doc = service.ingest('a.txt', b'Example document')
    with sqlite3.connect(tmp_path / 'state.sqlite3') as db:
        db.execute('ALTER TABLE documents DROP COLUMN classification')
    assert Service(tmp_path, 'demo').get(doc)['classification'] == 'unknown'


def test_upload_classification_requires_csrf_and_is_displayed(tmp_path):
    service = Service(tmp_path, 'demo')
    with TestClient(create_app(service), base_url='http://127.0.0.1') as client:
        token = re.search(r'name="csrf" value="([^"]+)"', client.get('/').text)[1]
        assert client.post('/upload', files={'file': ('a.txt', b'Example')}, data={'classification': 'public'}).status_code == 403
        response = client.post('/upload', files={'file': ('a.txt', b'Example')}, data={'csrf': token, 'classification': 'internal'})
        assert response.status_code == 200
        assert 'Nội bộ — chỉ local' in response.text
        assert service.get(service.listing()[0]['id'])['classification'] == 'internal'
