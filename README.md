# mermaid_final

A combined Flask app built from `mermaid_dashboard` and `mermaid-display-app`.

## Features

- Built-in live Mermaid editor with source editing and rendered preview.
- Starter templates and contextual help for common Mermaid diagram types.
- Canvas saves go directly into the File Repository, under `General` when no project is selected.
- Zoomable and pannable Mermaid preview.
- Draggable source, preview, and AI assistance panes.
- Repository master previews resolve active `%% INCLUDE` subdocuments.
- Collapsible AI assistance panel backed by Ollama.
- Local `.mmd` backup export from Mermaid Live Editor `pako:` URLs.
- File-backed project folders for repository flowcharts.
- Recursive `%% INCLUDE sub_diagrams/name.mmd` rendering within each project.
- Mermaid canvas editing for repository diagrams.
- Per-diagram `.mmd` export from repository files.
- Automatic repository revisions: saving from Canvas creates a new active revision file and leaves the old one inactive.
- LLM context files in `llm_context/standard_instructions.md` and `llm_context/mermaid_documentation.md`.
- Official Mermaid documentation snapshots stored in `llm_context/official_mermaid_docs/`.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5013`.

Set `MERMAID_EDITOR_URL` if your Mermaid Live Editor is not running on `http://localhost:9000`.
Set `PORT` if you want the Flask app on a different port.

Set `OLLAMA_URL` if Ollama is not running on `http://192.168.1.249:11434`.
Set `OLLAMA_MODEL` to change the default assistant model. The UI also lets you override the model per request.
