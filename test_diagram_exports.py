"""Regression checks for SVG/PNG export in the active Mermaid app."""
from app import app


def test_canvas_export_buttons_and_asset():
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="download-svg"' in html
    assert 'id="download-png"' in html
    assert '/static/diagram_export.js' in html
    asset = client.get("/static/diagram_export.js")
    assert asset.status_code == 200
    assert b"prepareSvg" in asset.data


def test_canvas_asset_url_with_uda_prefix():
    client = app.test_client()
    response = client.get("/", headers={
        "X-Forwarded-Prefix": "/apps/mermaid-display-app",
        "X-Forwarded-Host": "example.test",
        "X-Forwarded-Proto": "https",
    })
    assert response.status_code == 200
    assert '/apps/mermaid-display-app/static/diagram_export.js' in response.get_data(as_text=True)
