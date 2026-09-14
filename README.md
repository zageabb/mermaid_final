# mermaid_final

## Ubuntu server deployment

Verified on **14 September 2026** against the listeners, user systemd services,
Docker port mappings and deployment registry on `192.168.1.249`.

| Endpoint | Host TCP port | LAN URL |
|---|---:|---|
| Application | 5070 | http://192.168.1.249:5070/ |

Checkout: `/home/zageabb/mermaid/mermaid_final`.

These are **user** systemd units. Inspect them with:

```bash
systemctl --user status migrated-flask@mermaid-display-app.service
systemctl --user cat migrated-flask@mermaid-display-app.service
```

Local verification URL: `http://127.0.0.1:5070/`. HTTP 200 was observed during this audit.

Development defaults and container-internal ports elsewhere in this repository
may differ from this host deployment. Use the live ports above when accessing
this Ubuntu server; do not start a second copy on a port already occupied.

[Complete Ubuntu port inventory](https://github.com/zageabb/universal-deployment-agent/blob/main/UBUNTU_PORTS.md).

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

## Configuration

`config.json` is required at startup. Edit it to change app ports, paths, Mermaid rendering limits, Ollama URL/model, request timeout, keepalive duration, and assistant prompt text.

Environment variables still override common deployment settings:

- `PORT`
- `SECRET_KEY`
- `MERMAID_EDITOR_URL`
- `OLLAMA_URL`
- `OLLAMA_MODEL`
