"""End-to-end route checks with the actual editable PowerPoint package installed.

Only the real-package workflow executes this file; no stub implementation is used.
"""
import os
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from pptx import Presentation
import app as mermaid_app
from shared_diagram_core.pptx_export import export_flowchart_pptx


def test_actual_exporter_creates_editable_shapes(tmp_path: Path):
    output = tmp_path / "actual.pptx"
    export_flowchart_pptx("flowchart LR\nA[Start] --> B[End]", output)
    slide = Presentation(output).slides[0]
    assert len([shape for shape in slide.shapes if shape.has_text_frame and shape.text in ("Start", "End")]) == 2
    assert len([shape for shape in slide.shapes if shape.shape_type == 9]) == 1


def test_mermaid_final_route_with_actual_library(monkeypatch):
    monkeypatch.setenv("MERMAID_PPTX_EXPERIMENTAL", "1")
    mermaid_app.app.config["TESTING"] = True
    diagram = SimpleNamespace(
        diagram_type="standard", content="flowchart LR\nA[Start] --> B[End]",
        name="Integration", project_slug="demo", revision=1,
    )
    with patch.object(mermaid_app, "load_repository_diagram", return_value=diagram):
        response = mermaid_app.app.test_client().get("/repository/export-pptx/demo/diagram/1")
    assert response.status_code == 200
    assert response.data.startswith(b"PK")
    from io import BytesIO
    slides = Presentation(BytesIO(response.data)).slides
    assert len(slides) == 1
    assert sum(shape.shape_type == 9 for shape in slides[0].shapes) == 1


def test_real_package_rejects_unsupported_syntax(monkeypatch):
    monkeypatch.setenv("MERMAID_PPTX_EXPERIMENTAL", "1")
    diagram = SimpleNamespace(
        diagram_type="standard", content="sequenceDiagram\nA->>B: Hello",
        name="Unsupported", project_slug="demo", revision=1,
    )
    with patch.object(mermaid_app, "load_repository_diagram", return_value=diagram):
        response = mermaid_app.app.test_client().get("/repository/export-pptx/demo/diagram/1")
    assert response.status_code == 422
