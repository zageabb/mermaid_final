import base64
import json
import os
import re
import zlib
from pathlib import Path

from flask import Flask, Response, abort, flash, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text


BASE_DIR = Path(__file__).resolve().parent
DIAGRAM_DIR = BASE_DIR / "diagrams"
SUB_DIAGRAM_DIR = DIAGRAM_DIR / "sub_diagrams"
SAVED_DIAGRAM_DIR = BASE_DIR / "saved_diagrams"
EDITOR_URL = os.environ.get("MERMAID_EDITOR_URL", "http://localhost:9000")
APP_PORT = int(os.environ.get("PORT", "5013"))
DEFAULT_NEW_DIAGRAM = """flowchart TD
    Start[New diagram] --> Next[Edit me in Mermaid]
"""

DIAGRAM_DIR.mkdir(exist_ok=True)
SUB_DIAGRAM_DIR.mkdir(exist_ok=True)
SAVED_DIAGRAM_DIR.mkdir(exist_ok=True)
(BASE_DIR / "instance").mkdir(exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "mermaid-final-dev-key")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DIR / 'instance' / 'database.db'}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class SavedDiagram(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    notes = db.Column(db.Text, nullable=True)


class ProjectFolder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    diagrams = db.relationship("RepositoryDiagram", backref="project", cascade="all, delete-orphan", lazy=True)


class RepositoryDiagram(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project_folder.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    diagram_type = db.Column(db.String(32), nullable=False, default="master")
    content = db.Column(db.Text, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    revision = db.Column(db.Integer, nullable=False, default=1)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


@app.context_processor
def inject_saved_links():
    try:
        links = SavedDiagram.query.order_by(SavedDiagram.id.desc()).all()
    except Exception:
        links = []
    return {"saved_links": links, "editor_url": EDITOR_URL}


def ensure_database_schema():
    columns = {
        row[1]
        for row in db.session.execute(text("PRAGMA table_info(repository_diagram)")).fetchall()
    }
    if "revision" not in columns:
        db.session.execute(text("ALTER TABLE repository_diagram ADD COLUMN revision INTEGER NOT NULL DEFAULT 1"))
    if "is_active" not in columns:
        db.session.execute(text("ALTER TABLE repository_diagram ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"))
    db.session.commit()


def slugify(text):
    return re.sub(r"[^a-zA-Z0-9_-]", "_", text.strip().replace(" ", "_")).strip("_") or "diagram"


def safe_diagram_path(rel_path):
    path = (DIAGRAM_DIR / rel_path).resolve()
    if DIAGRAM_DIR.resolve() not in path.parents and path != DIAGRAM_DIR.resolve():
        abort(400)
    if path.suffix != ".mmd":
        abort(400)
    return path


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


def export_url_to_mmd_file(diagram_id, description, url_string):
    try:
        mermaid_code = extract_code_from_mermaid_url(url_string)
    except Exception as exc:
        app.logger.warning("Could not extract Mermaid source from URL: %s", exc)
        return False

    filename = f"{diagram_id}_{slugify(description)}.mmd"
    (SAVED_DIAGRAM_DIR / filename).write_text(mermaid_code, encoding="utf-8")
    return True


def assemble_diagram(path, is_sub_include=False, seen=None):
    if seen is None:
        seen = set()

    resolved = path.resolve()
    if resolved in seen:
        return f"%% ERROR: Circular include skipped for {path.name}\n"
    if not resolved.exists():
        return None

    seen.add(resolved)
    include_pattern = re.compile(r"^\s*%%\s*INCLUDE\s+(.+)$")
    assembled = []

    for line in resolved.read_text(encoding="utf-8").splitlines(keepends=True):
        if is_sub_include and re.match(r"^\s*(erDiagram|flowchart|graph)\b", line):
            continue

        match = include_pattern.match(line)
        if not match:
            assembled.append(line)
            continue

        include_name = match.group(1).strip()
        include_path = safe_diagram_path(include_name)
        sub_content = assemble_diagram(include_path, is_sub_include=True, seen=seen)
        assembled.append(f"\n{sub_content}\n" if sub_content else f"%% ERROR: Missing include '{include_name}'\n")

    seen.remove(resolved)
    return "".join(assembled)


def assemble_repository_diagram(diagram, seen=None, is_sub_include=False):
    if seen is None:
        seen = set()
    if diagram.id in seen:
        return f"%% ERROR: Circular include skipped for {diagram.name}\n"

    seen.add(diagram.id)
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
        included = RepositoryDiagram.query.filter_by(
            project_id=diagram.project_id,
            name=include_name,
            is_active=True,
        ).first()
        sub_content = assemble_repository_diagram(included, seen=seen, is_sub_include=True) if included else None
        assembled.append(f"\n{sub_content}\n" if sub_content else f"%% ERROR: Missing include '{include_name}'\n")

    seen.remove(diagram.id)
    return "".join(assembled)


def seed_repository_from_files():
    if ProjectFolder.query.first():
        return

    project = ProjectFolder(name="Sample Flowcharts", description="Imported from the original file repository.")
    db.session.add(project)
    db.session.flush()

    for path in sorted(DIAGRAM_DIR.glob("*.mmd")):
        db.session.add(
            RepositoryDiagram(
                project_id=project.id,
                name=path.name,
                diagram_type="master",
                content=path.read_text(encoding="utf-8"),
                revision=1,
                is_active=True,
            )
        )

    for path in sorted(SUB_DIAGRAM_DIR.glob("*.mmd")):
        db.session.add(
            RepositoryDiagram(
                project_id=project.id,
                name=path.name,
                diagram_type="sub",
                content=path.read_text(encoding="utf-8"),
                revision=1,
                is_active=True,
            )
        )

    db.session.commit()


def repository_rows():
    master_files = sorted(path.name for path in DIAGRAM_DIR.glob("*.mmd"))
    sub_files = sorted(path.name for path in SUB_DIAGRAM_DIR.glob("*.mmd"))
    assigned_subs = set()
    rows = []
    include_pattern = re.compile(r"^\s*%%\s*INCLUDE\s+sub_diagrams/(.+)$")

    for master in master_files:
        rows.append({"name": master, "type": "Master", "rel_path": master, "is_child": False})
        for line in (DIAGRAM_DIR / master).read_text(encoding="utf-8").splitlines():
            match = include_pattern.match(line)
            if match and match.group(1).strip() in sub_files:
                sub_name = match.group(1).strip()
                rows.append(
                    {
                        "name": sub_name,
                        "type": "Included Sub-Doc",
                        "rel_path": f"sub_diagrams/{sub_name}",
                        "is_child": True,
                    }
                )
                assigned_subs.add(sub_name)

    for orphan in [name for name in sub_files if name not in assigned_subs]:
        rows.append(
            {
                "name": orphan,
                "type": "Standalone Sub-Doc",
                "rel_path": f"sub_diagrams/{orphan}",
                "is_child": False,
            }
        )
    return rows


@app.route("/")
def canvas():
    current_url = request.args.get("url", default_canvas_url())
    current_name = request.args.get("name", "New Diagram Canvas")
    save_mode = request.args.get("save_mode", "library")
    repository_diagram_id = request.args.get("repository_diagram_id")
    return render_template(
        "canvas.html",
        current_url=current_url,
        current_name=current_name,
        save_mode=save_mode,
        repository_diagram_id=repository_diagram_id,
    )


@app.route("/new")
def new_canvas():
    return redirect(url_for("canvas", url=default_canvas_url(), name="Untitled Diagram"))


@app.route("/save", methods=["POST"])
def save_diagram():
    url = request.form.get("url", "").strip()
    description = request.form.get("description", "").strip()
    notes = request.form.get("notes", "").strip()

    if not url or not description:
        flash("A diagram URL and description are required.")
        return redirect(request.referrer or url_for("library"))

    diagram = SavedDiagram(url=url, description=description, notes=notes)
    db.session.add(diagram)
    db.session.commit()
    exported = export_url_to_mmd_file(diagram.id, diagram.description, diagram.url)
    flash("Diagram saved. A local .mmd backup was written." if exported else "Diagram saved. No .mmd backup could be extracted from that URL.")
    return redirect(request.referrer or url_for("library"))


@app.route("/library")
def library():
    diagrams = SavedDiagram.query.order_by(SavedDiagram.id.desc()).all()
    return render_template("library.html", diagrams=diagrams)


@app.route("/library/upload", methods=["POST"])
def upload_mmd_to_library():
    description = request.form.get("description", "").strip()
    notes = request.form.get("notes", "").strip()
    uploaded_file = request.files.get("file")

    if not uploaded_file or not description:
        flash("Choose a .mmd file and provide a title.")
        return redirect(url_for("library"))

    mmd_text = uploaded_file.read().decode("utf-8")
    diagram = SavedDiagram(
        url=convert_mmd_text_to_mermaid_url(mmd_text),
        description=description,
        notes=notes,
    )
    db.session.add(diagram)
    db.session.commit()
    export_url_to_mmd_file(diagram.id, diagram.description, diagram.url)
    flash("File imported into the saved diagram library.")
    return redirect(url_for("library"))


@app.route("/library/edit/<int:diagram_id>", methods=["POST"])
def edit_saved_diagram(diagram_id):
    diagram = SavedDiagram.query.get_or_404(diagram_id)
    diagram.description = request.form.get("description", "").strip()
    diagram.url = request.form.get("url", "").strip()
    diagram.notes = request.form.get("notes", "").strip()
    db.session.commit()
    export_url_to_mmd_file(diagram.id, diagram.description, diagram.url)
    flash("Saved diagram updated.")
    return redirect(url_for("library"))


@app.route("/library/delete/<int:diagram_id>", methods=["POST"])
def delete_saved_diagram(diagram_id):
    diagram = SavedDiagram.query.get_or_404(diagram_id)
    backup = SAVED_DIAGRAM_DIR / f"{diagram.id}_{slugify(diagram.description)}.mmd"
    if backup.exists():
        backup.unlink()
    db.session.delete(diagram)
    db.session.commit()
    flash("Saved diagram deleted.")
    return redirect(url_for("library"))


@app.route("/repository")
def repository():
    projects = ProjectFolder.query.order_by(ProjectFolder.name.asc()).all()
    for project in projects:
        project.active_diagrams = sorted(
            [diagram for diagram in project.diagrams if diagram.is_active],
            key=lambda diagram: (diagram.name, diagram.revision),
        )
        project.inactive_diagrams = sorted(
            [diagram for diagram in project.diagrams if not diagram.is_active],
            key=lambda diagram: (diagram.name, diagram.revision),
            reverse=True,
        )
    return render_template("repository.html", projects=projects)


@app.route("/repository/project", methods=["POST"])
def create_project():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    if not name:
        flash("Project name is required.")
        return redirect(url_for("repository"))

    existing = ProjectFolder.query.filter_by(name=name).first()
    if existing:
        flash("A project with that name already exists.")
        return redirect(url_for("repository"))

    db.session.add(ProjectFolder(name=name, description=description))
    db.session.commit()
    flash("Project folder created.")
    return redirect(url_for("repository"))


@app.route("/repository/diagram", methods=["POST"])
def create_repository_diagram():
    project_id = request.form.get("project_id", type=int)
    name = request.form.get("name", "").strip()
    diagram_type = request.form.get("diagram_type", "master")
    content = request.form.get("content", "").strip() or DEFAULT_NEW_DIAGRAM

    project = ProjectFolder.query.get_or_404(project_id)
    if not name:
        flash("Flowchart name is required.")
        return redirect(url_for("repository"))

    filename = slugify(Path(name).stem) + ".mmd"
    db.session.add(
        RepositoryDiagram(
            project_id=project.id,
            name=filename,
            diagram_type=diagram_type if diagram_type in {"master", "sub"} else "master",
            content=content,
            revision=1,
            is_active=True,
        )
    )
    db.session.commit()
    flash(f"Flowchart created in {project.name}.")
    return redirect(url_for("repository"))


@app.route("/repository/upload", methods=["POST"])
def upload_repository_file():
    uploaded_file = request.files.get("file")
    project_id = request.form.get("project_id", type=int)
    diagram_type = request.form.get("diagram_type", "master")

    if not uploaded_file or not uploaded_file.filename.endswith(".mmd"):
        flash("Upload a .mmd file.")
        return redirect(url_for("repository"))

    project = ProjectFolder.query.get_or_404(project_id)
    filename = slugify(Path(uploaded_file.filename).stem) + ".mmd"
    content = uploaded_file.read().decode("utf-8")
    db.session.add(
        RepositoryDiagram(
            project_id=project.id,
            name=filename,
            diagram_type=diagram_type if diagram_type in {"master", "sub"} else "master",
            content=content,
            revision=1,
            is_active=True,
        )
    )
    db.session.commit()
    flash(f"{filename} imported into {project.name}.")
    return redirect(url_for("repository"))


@app.route("/repository/view/<int:diagram_id>")
def view_file(diagram_id):
    diagram = RepositoryDiagram.query.get_or_404(diagram_id)
    content = assemble_repository_diagram(diagram)
    return render_template(
        "view.html",
        filename=f"{diagram.project.name}/{diagram.name}",
        content=content,
        diagram_id=diagram.id,
    )


@app.route("/repository/editor/<int:diagram_id>")
def edit_file(diagram_id):
    diagram = RepositoryDiagram.query.get_or_404(diagram_id)
    return redirect(
        url_for(
            "canvas",
            url=convert_mmd_text_to_mermaid_url(diagram.content),
            name=f"{diagram.project.name} / {diagram.name}",
            save_mode="repository",
            repository_diagram_id=diagram.id,
        )
    )


@app.route("/repository/update/<int:diagram_id>", methods=["POST"])
def update_repository_diagram(diagram_id):
    diagram = RepositoryDiagram.query.get_or_404(diagram_id)
    url = request.form.get("url", "").strip()
    if not url:
        flash("Paste or capture a Mermaid editor URL before saving.")
        return redirect(url_for("repository"))

    try:
        new_content = extract_code_from_mermaid_url(url)
    except Exception as exc:
        flash(f"Could not read Mermaid source from that URL: {exc}")
        return redirect(url_for("repository"))

    current_max_revision = (
        db.session.query(db.func.max(RepositoryDiagram.revision))
        .filter_by(project_id=diagram.project_id, name=diagram.name)
        .scalar()
        or diagram.revision
        or 1
    )
    RepositoryDiagram.query.filter_by(
        project_id=diagram.project_id,
        name=diagram.name,
        is_active=True,
    ).update({"is_active": False})
    new_diagram = RepositoryDiagram(
        project_id=diagram.project_id,
        name=diagram.name,
        diagram_type=diagram.diagram_type,
        content=new_content,
        notes=diagram.notes,
        revision=current_max_revision + 1,
        is_active=True,
    )
    db.session.add(new_diagram)
    db.session.commit()
    flash(f"{diagram.name} saved as revision {new_diagram.revision}. Revision {diagram.revision} was deactivated.")
    return redirect(url_for("repository"))


@app.route("/repository/export/<int:diagram_id>")
def export_repository_diagram(diagram_id):
    diagram = RepositoryDiagram.query.get_or_404(diagram_id)
    content = assemble_repository_diagram(diagram) if diagram.diagram_type == "master" else diagram.content
    filename = slugify(f"{diagram.project.name}_{diagram.name}_r{diagram.revision}") + ".mmd"
    return Response(
        content,
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        ensure_database_schema()
        seed_repository_from_files()
    app.run(host="0.0.0.0", port=APP_PORT, debug=True)
