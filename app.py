import base64
import json
import os
import re
import urllib.error
import urllib.request
import zlib
from dataclasses import dataclass
from pathlib import Path

from flask import Flask, Response, abort, flash, jsonify, redirect, render_template, request, stream_with_context, url_for


BASE_DIR = Path(__file__).resolve().parent
DIAGRAM_DIR = BASE_DIR / "diagrams"
SUB_DIAGRAM_DIR = DIAGRAM_DIR / "sub_diagrams"
SAVED_DIAGRAM_DIR = BASE_DIR / "saved_diagrams"
SAVED_LIBRARY_FILE = SAVED_DIAGRAM_DIR / "saved_links.json"
FILE_REPOSITORY_DIR = BASE_DIR / "file_repository"
LLM_CONTEXT_DIR = BASE_DIR / "llm_context"
STANDARD_INSTRUCTIONS_FILE = LLM_CONTEXT_DIR / "standard_instructions.md"
MERMAID_DOCUMENTATION_FILE = LLM_CONTEXT_DIR / "mermaid_documentation.md"
EDITOR_URL = os.environ.get("MERMAID_EDITOR_URL", "http://localhost:9000")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://192.168.1.249:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e2b")
APP_PORT = int(os.environ.get("PORT", "5013"))
DEFAULT_NEW_DIAGRAM = """flowchart TD
    Start[New diagram] --> Next[Edit me in Mermaid]
"""

DIAGRAM_DIR.mkdir(exist_ok=True)
SUB_DIAGRAM_DIR.mkdir(exist_ok=True)
SAVED_DIAGRAM_DIR.mkdir(exist_ok=True)
FILE_REPOSITORY_DIR.mkdir(exist_ok=True)
LLM_CONTEXT_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "mermaid-final-dev-key")

# Database access is intentionally disabled. The app now stores the saved library
# in saved_diagrams/saved_links.json and the repository in file_repository/.
# from flask_sqlalchemy import SQLAlchemy
# from sqlalchemy import text
# app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DIR / 'instance' / 'database.db'}"
# app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# db = SQLAlchemy(app)


@dataclass
class SavedLink:
    id: int
    url: str
    description: str
    notes: str = ""


@dataclass
class RepositoryDiagram:
    id: str
    project_slug: str
    diagram_slug: str
    name: str
    diagram_type: str
    revision: int
    is_active: bool
    content: str


@dataclass
class ProjectFolder:
    slug: str
    name: str
    description: str
    active_diagrams: list
    inactive_diagrams: list


@app.context_processor
def inject_saved_links():
    return {"saved_links": load_saved_links(), "editor_url": EDITOR_URL, "ollama_model": OLLAMA_MODEL}


def slugify(text):
    return re.sub(r"[^a-zA-Z0-9_-]", "_", text.strip().replace(" ", "_")).strip("_") or "diagram"


def adaptive_decompress(compressed_bytes):
    for window_bits in (15, -15, 31):
        try:
            return zlib.decompress(compressed_bytes, window_bits)
        except zlib.error:
            continue
    raise ValueError("Unknown compressed Mermaid state format.")


def extract_code_from_mermaid_url(url_string):
    if "pako:" in url_string:
        encoded_state = url_string.split("pako:", 1)[1].split("?", 1)[0].split("#", 1)[0]
    elif "#/edit/" in url_string:
        encoded_state = url_string.split("#/edit/", 1)[1].split("?", 1)[0]
    else:
        raise ValueError("No Mermaid editor state found in the URL.")

    normalized = encoded_state.replace("-", "+").replace("_", "/")
    normalized += "=" * (-len(normalized) % 4)
    state_json = adaptive_decompress(base64.b64decode(normalized)).decode("utf-8")
    state = json.loads(state_json)
    return state.get("code", "") if isinstance(state, dict) else str(state)


def convert_mmd_text_to_mermaid_url(mmd_text):
    state = {
        "code": mmd_text.strip(),
        "mermaid": '{"theme":"default"}',
        "autoSync": True,
        "updateDiagram": True,
        "updateEditor": True,
    }
    json_bytes = json.dumps(state, ensure_ascii=False).encode("utf-8")
    compressed = zlib.compress(json_bytes, level=9)
    encoded = base64.b64encode(compressed).decode("utf-8")
    url_safe = encoded.replace("+", "-").replace("/", "_").replace("=", "")
    return f"{EDITOR_URL}/#/edit/pako:{url_safe}"


def default_canvas_url():
    return convert_mmd_text_to_mermaid_url(DEFAULT_NEW_DIAGRAM)


def load_saved_links():
    if not SAVED_LIBRARY_FILE.exists():
        return []
    try:
        rows = json.loads(SAVED_LIBRARY_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [SavedLink(**row) for row in rows]


def write_saved_links(links):
    SAVED_LIBRARY_FILE.write_text(
        json.dumps([link.__dict__ for link in links], indent=2),
        encoding="utf-8",
    )


def next_saved_link_id():
    links = load_saved_links()
    return max([link.id for link in links], default=0) + 1


def export_url_to_mmd_file(diagram_id, description, url_string):
    try:
        mermaid_code = extract_code_from_mermaid_url(url_string)
    except Exception as exc:
        app.logger.warning("Could not extract Mermaid source from URL: %s", exc)
        return False

    filename = f"{diagram_id}_{slugify(description)}.mmd"
    (SAVED_DIAGRAM_DIR / filename).write_text(mermaid_code, encoding="utf-8")
    return True


def project_dir(project_slug):
    path = (FILE_REPOSITORY_DIR / project_slug).resolve()
    if FILE_REPOSITORY_DIR.resolve() not in path.parents and path != FILE_REPOSITORY_DIR.resolve():
        abort(400)
    return path


def diagram_dir(project_slug, diagram_slug):
    path = (project_dir(project_slug) / diagram_slug).resolve()
    if project_dir(project_slug).resolve() not in path.parents and path != project_dir(project_slug).resolve():
        abort(400)
    return path


def revision_filename(revision):
    return f"r{revision:03d}.mmd"


def read_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_context_file(path, limit=24000):
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")[:limit]


def normalize_mermaid_source(source):
    normalized = (source or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in normalized.split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def has_mermaid_declaration(source):
    return bool(
        re.match(
            r"^\s*(flowchart|graph|sequenceDiagram|classDiagram|stateDiagram(?:-v2)?|erDiagram|journey|gantt|pie|quadrantChart|mindmap|timeline|gitGraph|requirementDiagram|C4)",
            source or "",
        )
    )


def preview_prefix_for_diagram(diagram):
    if diagram.diagram_type == "sub" and not has_mermaid_declaration(diagram.content):
        return "flowchart TB\n"
    return ""


def renderable_repository_content(diagram):
    return preview_prefix_for_diagram(diagram) + assemble_repository_diagram(diagram)


def create_project_folder(name, description=""):
    slug = slugify(name)
    path = project_dir(slug)
    path.mkdir(parents=True, exist_ok=True)
    metadata_path = path / ".project.json"
    if not metadata_path.exists():
        write_json(metadata_path, {"name": name, "description": description})
    return slug


def ensure_general_project():
    return create_project_folder("General", "Default project for diagrams saved from Canvas.")


def create_repository_revision(project_slug, name, diagram_type, content, source_revision=None):
    content = normalize_mermaid_source(content)
    diagram_slug = slugify(Path(name).stem)
    path = diagram_dir(project_slug, diagram_slug)
    path.mkdir(parents=True, exist_ok=True)

    metadata_path = path / "metadata.json"
    metadata = read_json(
        metadata_path,
        {
            "name": slugify(Path(name).stem) + ".mmd",
            "diagram_type": diagram_type,
            "active_revision": 0,
        },
    )
    existing_revisions = [
        int(match.group(1))
        for file_path in path.glob("r*.mmd")
        if (match := re.match(r"r(\d+)\.mmd$", file_path.name))
    ]
    next_revision = max(existing_revisions + [metadata.get("active_revision", 0)]) + 1
    (path / revision_filename(next_revision)).write_text(content, encoding="utf-8")
    metadata.update(
        {
            "name": metadata.get("name") or slugify(Path(name).stem) + ".mmd",
            "diagram_type": diagram_type or metadata.get("diagram_type"),
            "active_revision": next_revision,
            "source_revision": source_revision,
        }
    )
    write_json(metadata_path, metadata)
    return next_revision


def load_repository_diagram(project_slug, diagram_slug, revision=None):
    path = diagram_dir(project_slug, diagram_slug)
    metadata = read_json(path / "metadata.json", None)
    if not metadata:
        abort(404)
    active_revision = int(metadata.get("active_revision", 1))
    selected_revision = int(revision or active_revision)
    content_path = path / revision_filename(selected_revision)
    if not content_path.exists():
        abort(404)
    return RepositoryDiagram(
        id=f"{project_slug}/{diagram_slug}/{selected_revision}",
        project_slug=project_slug,
        diagram_slug=diagram_slug,
        name=metadata["name"],
        diagram_type=metadata.get("diagram_type", "master"),
        revision=selected_revision,
        is_active=selected_revision == active_revision,
        content=content_path.read_text(encoding="utf-8"),
    )


def load_projects():
    seed_file_repository_from_legacy_files()
    projects = []
    for path in sorted(FILE_REPOSITORY_DIR.iterdir()):
        if not path.is_dir():
            continue
        metadata = read_json(path / ".project.json", {"name": path.name, "description": ""})
        active_diagrams = []
        inactive_diagrams = []
        for diagram_path in sorted([item for item in path.iterdir() if item.is_dir()]):
            diagram_metadata = read_json(diagram_path / "metadata.json", None)
            if not diagram_metadata:
                continue
            active_revision = int(diagram_metadata.get("active_revision", 1))
            for revision_path in sorted(diagram_path.glob("r*.mmd")):
                match = re.match(r"r(\d+)\.mmd$", revision_path.name)
                if not match:
                    continue
                revision = int(match.group(1))
                diagram = RepositoryDiagram(
                    id=f"{path.name}/{diagram_path.name}/{revision}",
                    project_slug=path.name,
                    diagram_slug=diagram_path.name,
                    name=diagram_metadata["name"],
                    diagram_type=diagram_metadata.get("diagram_type", "master"),
                    revision=revision,
                    is_active=revision == active_revision,
                    content=revision_path.read_text(encoding="utf-8"),
                )
                if diagram.is_active:
                    active_diagrams.append(diagram)
                else:
                    inactive_diagrams.append(diagram)
        projects.append(
            ProjectFolder(
                slug=path.name,
                name=metadata.get("name", path.name),
                description=metadata.get("description", ""),
                active_diagrams=sorted(active_diagrams, key=lambda item: (item.name, item.revision)),
                inactive_diagrams=sorted(inactive_diagrams, key=lambda item: (item.name, item.revision), reverse=True),
            )
        )
    return projects


def seed_file_repository_from_legacy_files():
    if any(FILE_REPOSITORY_DIR.iterdir()):
        return
    project_slug = create_project_folder("Sample Flowcharts", "Imported from the original file repository.")
    for path in sorted(DIAGRAM_DIR.glob("*.mmd")):
        create_repository_revision(project_slug, path.name, "master", path.read_text(encoding="utf-8"))
    for path in sorted(SUB_DIAGRAM_DIR.glob("*.mmd")):
        create_repository_revision(project_slug, path.name, "sub", path.read_text(encoding="utf-8"))


def find_active_include(project_slug, include_name):
    for project in load_projects():
        if project.slug != project_slug:
            continue
        for diagram in project.active_diagrams:
            if diagram.name == include_name:
                return load_repository_diagram(project_slug, diagram.diagram_slug)
    return None


def active_include_sources(project_slug):
    sources = {}
    for project in load_projects():
        if project.slug != project_slug:
            continue
        for diagram in project.active_diagrams:
            sources[diagram.name] = diagram.content
    return sources


def assemble_repository_diagram(diagram, seen=None, is_sub_include=False):
    if seen is None:
        seen = set()
    key = (diagram.project_slug, diagram.diagram_slug, diagram.revision)
    if key in seen:
        return f"%% ERROR: Circular include skipped for {diagram.name}\n"

    seen.add(key)
    include_pattern = re.compile(r"^\s*%%\s*INCLUDE\s+(.+)$")
    assembled = []

    for line in diagram.content.splitlines(keepends=True):
        if is_sub_include and re.match(r"^\s*(erDiagram|flowchart|graph)\b", line):
            continue

        match = include_pattern.match(line)
        if not match:
            assembled.append(line)
            continue

        include_name = Path(match.group(1).strip()).name
        included = find_active_include(diagram.project_slug, include_name)
        sub_content = assemble_repository_diagram(included, seen=seen, is_sub_include=True) if included else None
        assembled.append(f"\n{sub_content}\n" if sub_content else f"%% ERROR: Missing include '{include_name}'\n")

    seen.remove(key)
    return "".join(assembled)


@app.route("/")
def canvas():
    current_name = request.args.get("name", "New Diagram Canvas")
    save_mode = request.args.get("save_mode", "library")
    repository_diagram_id = request.args.get("repository_diagram_id")
    source = request.args.get("source", "")
    include_sources = {}
    preview_prefix = ""
    if save_mode == "repository" and repository_diagram_id:
        try:
            diagram = load_repository_diagram(*repository_diagram_id.split("/", 2))
            source = diagram.content
            preview_prefix = preview_prefix_for_diagram(diagram)
            include_sources = active_include_sources(diagram.project_slug)
        except Exception:
            source = ""
    elif not source and request.args.get("url"):
        try:
            source = extract_code_from_mermaid_url(request.args["url"])
        except Exception:
            source = DEFAULT_NEW_DIAGRAM
    elif not source:
        source = DEFAULT_NEW_DIAGRAM

    return render_template(
        "canvas.html",
        current_name=current_name,
        save_mode=save_mode,
        repository_diagram_id=repository_diagram_id,
        source=source,
        include_sources=include_sources,
        preview_prefix=preview_prefix,
    )


@app.route("/new")
def new_canvas():
    return redirect(url_for("canvas", name="Untitled Diagram", source=DEFAULT_NEW_DIAGRAM))


@app.route("/save", methods=["POST"])
def save_diagram():
    source = normalize_mermaid_source(request.form.get("source", ""))
    description = request.form.get("description", "").strip()
    notes = request.form.get("notes", "").strip()
    diagram_type = request.form.get("diagram_type", "master").strip() or "master"

    if not source or not description:
        flash("Diagram source and description are required.")
        return redirect(request.referrer or url_for("canvas"))

    project_slug = ensure_general_project()
    revision = create_repository_revision(project_slug, description, diagram_type, source)
    flash(f"{description} saved to File Repository / General as revision {revision}.")
    return redirect(url_for("repository"))


@app.route("/library")
def library():
    return render_template("library.html", diagrams=sorted(load_saved_links(), key=lambda item: item.id, reverse=True))


@app.route("/library/upload", methods=["POST"])
def upload_mmd_to_library():
    description = request.form.get("description", "").strip()
    notes = request.form.get("notes", "").strip()
    uploaded_file = request.files.get("file")

    if not uploaded_file or not description:
        flash("Choose a .mmd file and provide a title.")
        return redirect(url_for("library"))

    mmd_text = uploaded_file.read().decode("utf-8")
    links = load_saved_links()
    diagram = SavedLink(
        id=next_saved_link_id(),
        url=convert_mmd_text_to_mermaid_url(mmd_text),
        description=description,
        notes=notes,
    )
    links.append(diagram)
    write_saved_links(links)
    export_url_to_mmd_file(diagram.id, diagram.description, diagram.url)
    flash("File imported into the saved diagram library.")
    return redirect(url_for("library"))


@app.route("/library/edit/<int:diagram_id>", methods=["POST"])
def edit_saved_diagram(diagram_id):
    links = load_saved_links()
    for diagram in links:
        if diagram.id == diagram_id:
            diagram.description = request.form.get("description", "").strip()
            diagram.url = request.form.get("url", "").strip()
            diagram.notes = request.form.get("notes", "").strip()
            export_url_to_mmd_file(diagram.id, diagram.description, diagram.url)
            break
    write_saved_links(links)
    flash("Saved diagram updated.")
    return redirect(url_for("library"))


@app.route("/library/delete/<int:diagram_id>", methods=["POST"])
def delete_saved_diagram(diagram_id):
    links = [diagram for diagram in load_saved_links() if diagram.id != diagram_id]
    write_saved_links(links)
    flash("Saved diagram deleted.")
    return redirect(url_for("library"))


@app.route("/repository")
def repository():
    return render_template("repository.html", projects=load_projects())


@app.route("/repository/project", methods=["POST"])
def create_project():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    if not name:
        flash("Project name is required.")
        return redirect(url_for("repository"))

    create_project_folder(name, description)
    flash("Project folder created.")
    return redirect(url_for("repository"))


@app.route("/repository/diagram", methods=["POST"])
def create_repository_diagram():
    project_slug = request.form.get("project_slug", "").strip()
    name = request.form.get("name", "").strip()
    diagram_type = request.form.get("diagram_type", "master")
    content = normalize_mermaid_source(request.form.get("content", "")) or DEFAULT_NEW_DIAGRAM

    if not project_slug or not name:
        flash("Project and flowchart name are required.")
        return redirect(url_for("repository"))

    revision = create_repository_revision(project_slug, name, diagram_type, content)
    flash(f"{name} created as revision {revision}.")
    return redirect(url_for("repository"))


@app.route("/repository/upload", methods=["POST"])
def upload_repository_file():
    uploaded_file = request.files.get("file")
    project_slug = request.form.get("project_slug", "").strip()
    diagram_type = request.form.get("diagram_type", "master")

    if not uploaded_file or not uploaded_file.filename.endswith(".mmd"):
        flash("Upload a .mmd file.")
        return redirect(url_for("repository"))
    if not project_slug:
        flash("Choose a project.")
        return redirect(url_for("repository"))

    filename = slugify(Path(uploaded_file.filename).stem) + ".mmd"
    content = normalize_mermaid_source(uploaded_file.read().decode("utf-8"))
    revision = create_repository_revision(project_slug, filename, diagram_type, content)
    flash(f"{filename} imported as revision {revision}.")
    return redirect(url_for("repository"))


@app.route("/repository/view/<path:diagram_id>")
def view_file(diagram_id):
    diagram = load_repository_diagram(*diagram_id.split("/", 2))
    content = renderable_repository_content(diagram)
    return render_template(
        "view.html",
        filename=f"{diagram.project_slug}/{diagram.name}",
        content=content,
        diagram_id=diagram.id,
    )


@app.route("/repository/editor/<path:diagram_id>")
def edit_file(diagram_id):
    diagram = load_repository_diagram(*diagram_id.split("/", 2))
    return redirect(
        url_for(
            "canvas",
            name=f"{diagram.project_slug} / {diagram.name} r{diagram.revision}",
            save_mode="repository",
            repository_diagram_id=diagram.id,
        )
    )


@app.route("/repository/update/<path:diagram_id>", methods=["POST"])
def update_repository_diagram(diagram_id):
    diagram = load_repository_diagram(*diagram_id.split("/", 2))
    source = normalize_mermaid_source(request.form.get("source", ""))
    url = request.form.get("url", "").strip()

    if not source and url:
        try:
            source = normalize_mermaid_source(extract_code_from_mermaid_url(url))
        except Exception as exc:
            flash(f"Could not read Mermaid source from that URL: {exc}")
            return redirect(url_for("repository"))
    if not source:
        flash("Paste Mermaid source before saving the revision.")
        return redirect(url_for("repository"))

    revision = create_repository_revision(
        diagram.project_slug,
        diagram.name,
        diagram.diagram_type,
        source,
        source_revision=diagram.revision,
    )
    flash(f"{diagram.name} saved as revision {revision}. Revision {diagram.revision} remains inactive history.")
    return redirect(url_for("repository"))


@app.route("/assistant/chat", methods=["POST"])
def assistant_chat():
    payload = request.get_json(silent=True) or {}
    prompt = (payload.get("prompt") or "").strip()
    diagram = payload.get("diagram") or ""
    model = (payload.get("model") or OLLAMA_MODEL).strip()

    if not prompt:
        return jsonify({"error": "Prompt is required."}), 400

    full_prompt = f"""You are helping edit a Mermaid diagram.

Standard instructions:
{read_context_file(STANDARD_INSTRUCTIONS_FILE)}

Local Mermaid documentation summary:
{read_context_file(MERMAID_DOCUMENTATION_FILE)}

Current Mermaid diagram:
```mermaid
{diagram}
```

User request:
{prompt}

Give a concise answer. If you suggest code, provide a complete Mermaid snippet or a clear patch-style replacement.
Do not reveal private chain-of-thought or output <think> blocks. If reasoning is useful, provide a brief visible summary only."""
    request_payload = json.dumps(
        {
            "model": model,
            "prompt": full_prompt,
            "stream": True,
        }
    ).encode("utf-8")
    request_obj = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=request_payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    def stream_response():
        def event(payload):
            return json.dumps(payload) + "\n"

        yield event({"type": "status", "message": f"Contacting Ollama at {OLLAMA_URL}"})
        try:
            with urllib.request.urlopen(request_obj, timeout=120) as response:
                yield event({"type": "status", "message": f"Streaming response from {model}"})
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        yield event({"type": "error", "message": "Ollama returned an unreadable stream chunk."})
                        return
                    if chunk.get("response"):
                        yield event({"type": "token", "text": chunk["response"]})
                    if chunk.get("done"):
                        yield event({"type": "done", "model": model})
                        return
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")[:500]
            yield event({"type": "error", "message": f"Ollama returned HTTP {exc.code}: {error_body or exc.reason}"})
        except urllib.error.URLError as exc:
            yield event({"type": "error", "message": f"Could not reach Ollama at {OLLAMA_URL}: {exc.reason}"})
        except TimeoutError:
            yield event({"type": "error", "message": f"Ollama timed out at {OLLAMA_URL}."})
        except Exception as exc:
            app.logger.exception("Assistant request failed")
            yield event({"type": "error", "message": f"Assistant request failed: {exc}"})

    return Response(
        stream_with_context(stream_response()),
        mimetype="application/x-ndjson",
        headers={"Cache-Control": "no-cache"},
    )


@app.route("/assistant/keepalive", methods=["POST"])
def assistant_keepalive():
    payload = request.get_json(silent=True) or {}
    model = (payload.get("model") or OLLAMA_MODEL).strip()
    request_payload = json.dumps(
        {
            "model": model,
            "prompt": "",
            "stream": False,
            "keep_alive": "1h",
        }
    ).encode("utf-8")
    request_obj = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=request_payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request_obj, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")[:500]
        return jsonify({"error": f"Ollama returned HTTP {exc.code}: {error_body or exc.reason}"}), 502
    except urllib.error.URLError as exc:
        return jsonify({"error": f"Could not reach Ollama at {OLLAMA_URL}: {exc.reason}"}), 502
    except TimeoutError:
        return jsonify({"error": f"Ollama timed out at {OLLAMA_URL}."}), 504
    except json.JSONDecodeError:
        return jsonify({"error": "Ollama returned an unreadable keepalive response."}), 502
    except Exception as exc:
        app.logger.exception("Assistant keepalive failed")
        return jsonify({"error": f"Assistant keepalive failed: {exc}"}), 500

    return jsonify(
        {
            "ok": True,
            "model": model,
            "keep_alive": "1h",
            "done": result.get("done", False),
        }
    )


@app.route("/repository/export/<path:diagram_id>")
def export_repository_diagram(diagram_id):
    diagram = load_repository_diagram(*diagram_id.split("/", 2))
    content = assemble_repository_diagram(diagram) if diagram.diagram_type == "master" else diagram.content
    filename = slugify(f"{diagram.project_slug}_{diagram.name}_r{diagram.revision}") + ".mmd"
    return Response(
        content,
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


if __name__ == "__main__":
    seed_file_repository_from_legacy_files()
    app.run(host="0.0.0.0", port=APP_PORT, debug=True)
