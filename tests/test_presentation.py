"""Serving/packaging contracts for the readable presentation layer."""
from fastapi.testclient import TestClient
from frameport.app import create_app
from frameport.config import Settings, ROOT


def test_presentation_served_and_loaded_after_structure(tmp_path):
    client = TestClient(create_app(Settings(data=tmp_path, allowed_hosts=('testserver',))))
    document = client.get('/').text
    assert document.index('/static/style.css') < document.index('/static/presentation.css')
    response = client.get('/static/presentation.css')
    assert response.status_code == 200
    assert 'text/css' in response.headers['content-type']
    assert '--weight-heading: 600' in response.text
    assert '--weight-body: 500' in response.text


def test_presentation_remains_monochrome_and_local():
    css = (ROOT / 'web/presentation.css').read_text()
    assert '@import' not in css and 'url(' not in css
    assert 'text-shadow' not in css and 'text-stroke' not in css
    assert 'font-weight: var(--weight-heading)' in css


def test_portable_packager_includes_presentation_layer():
    source = (ROOT / 'scripts/make_preview.py').read_text()
    assert "for stylesheet in ('style.css', 'presentation.css')" in source
