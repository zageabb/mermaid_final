# mermaid_final

A combined Flask app built from `mermaid_dashboard` and `mermaid-display-app`.

## Features

- Live Mermaid Editor canvas launcher and saved URL library.
- SQLite-backed saved diagrams with descriptions and notes.
- Local `.mmd` backup export from Mermaid Live Editor `pako:` URLs.
- `.mmd` file repository with master/sub-diagram grouping.
- Recursive `%% INCLUDE sub_diagrams/name.mmd` rendering.
- Browser-based source editing for repository files.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5013`.

Set `MERMAID_EDITOR_URL` if your Mermaid Live Editor is not running on `http://localhost:9000`.
