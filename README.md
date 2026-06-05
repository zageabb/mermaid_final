# mermaid_final

A combined Flask app built from `mermaid_dashboard` and `mermaid-display-app`.

## Features

- Live Mermaid Editor canvas launcher and saved URL library.
- Built-in live Mermaid editor with source editing and rendered preview.
- Starter templates and contextual help for common Mermaid diagram types.
- Collapsible AI assistance panel backed by Ollama.
- File-backed saved diagram links with descriptions and notes.
- Local `.mmd` backup export from Mermaid Live Editor `pako:` URLs.
- File-backed project folders for repository flowcharts.
- Recursive `%% INCLUDE sub_diagrams/name.mmd` rendering within each project.
- Mermaid canvas editing for repository diagrams.
- Per-diagram `.mmd` export from repository files.
- Automatic repository revisions: saving from Canvas creates a new active revision file and leaves the old one inactive.

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

Set `OLLAMA_URL` if Ollama is not running on `http://127.0.0.1:11434`.
Set `OLLAMA_MODEL` to change the default assistant model. The UI also lets you override the model per request.
