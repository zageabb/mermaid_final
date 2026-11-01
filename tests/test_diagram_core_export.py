"""Opt-in export endpoint regression tests: no dependency required on default install."""
import sys
import types
from unittest.mock import patch

import pytest
import app as mermaid_app


@pytest.fixture
def client():
    mermaid_app.app.config["TESTING"] = True
    return mermaid_app.app.test_client()


def test_disabled_by_default(client, monkeypatch):
    monkeypatch.delenv("MERMAID_PPTX_EXPERIMENTAL", raising=False)
    assert client.get("/repository/export-pptx/demo/diagram/1").status_code == 404


def test_invalid_id_rejected_without_loading_repository(client, monkeypatch):
    monkeypatch.setenv("MERMAID_PPTX_EXPERIMENTAL", "1")
    fake_package = types.ModuleType("shared_diagram_core")
    fake_package.DiagramError = ValueError
    fake_export = types.ModuleType("shared_diagram_core.pptx_export")
    fake_export.export_flowchart_pptx = lambda *args, **kwargs: None
    with patch.dict(sys.modules, {"shared_diagram_core": fake_package, "shared_diagram_core.pptx_export": fake_export}):
        assert client.get("/repository/export-pptx/invalid").status_code == 404


def test_unsupported_diagram_returns_422(client, monkeypatch):
    monkeypatch.setenv("MERMAID_PPTX_EXPERIMENTAL", "1")
    fake_package = types.ModuleType("shared_diagram_core")
    class DiagramError(ValueError):
        pass
    fake_package.DiagramError = DiagramError
    fake_export = types.ModuleType("shared_diagram_core.pptx_export")
    def reject(*args, **kwargs):
        raise DiagramError("Unsupported diagram")
    fake_export.export_flowchart_pptx = reject
    diagram = types.SimpleNamespace(diagram_type="standard", content="sequenceDiagram", name="Test", project_slug="demo", revision=1)
    with patch.dict(sys.modules, {"shared_diagram_core": fake_package, "shared_diagram_core.pptx_export": fake_export}):
        with patch.object(mermaid_app, "load_repository_diagram", return_value=diagram):
            response = client.get("/repository/export-pptx/demo/diagram/1")
    assert response.status_code == 422
    assert response.is_json


def test_valid_export_sends_pptx_attachment(client, monkeypatch):
    monkeypatch.setenv("MERMAID_PPTX_EXPERIMENTAL", "1")
    fake_package = types.ModuleType("shared_diagram_core")
    fake_package.DiagramError = ValueError
    fake_export = types.ModuleType("shared_diagram_core.pptx_export")
    def emit(source, destination, **kwargs):
        assert source == "flowchart LR\\nA-->B"
        destination.write_bytes(b"pptx-test-payload")
    fake_export.export_flowchart_pptx = emit
    diagram = types.SimpleNamespace(diagram_type="standard", content="flowchart LR\\nA-->B", name="Test", project_slug="demo", revision=1)
    with patch.dict(sys.modules, {"shared_diagram_core": fake_package, "shared_diagram_core.pptx_export": fake_export}):
        with patch.object(mermaid_app, "load_repository_diagram", return_value=diagram):
            response = client.get("/repository/export-pptx/demo/diagram/1")
    assert response.status_code == 200
    assert response.data == b"pptx-test-payload"
    assert "attachment" in response.headers["Content-Disposition"]
    assert "presentationml.presentation" in response.mimetype

def test_original_mmd_export_remains_available(client, monkeypatch):
    monkeypatch.delenv("MERMAID_PPTX_EXPERIMENTAL", raising=False)
    diagram = types.SimpleNamespace(
        diagram_type="standard", content="flowchart TD\nA --> B\n",
        name="Original", project_slug="demo", revision=1,
    )
    with patch.object(mermaid_app, "load_repository_diagram", return_value=diagram):
        response = client.get("/repository/export/demo/original/1")
    assert response.status_code == 200
    assert response.mimetype == "text/plain"
    assert response.data.decode("utf-8") == diagram.content
    assert response.headers["Content-Disposition"].endswith(".mmd")
