# Local Mermaid Documentation Summary

Official Mermaid HTML documentation is stored under `llm_context/official_mermaid_docs/`.

Downloaded source pages include:

- Syntax reference: `syntax-reference.html`
- Flowcharts: `flowchart.html`
- Sequence diagrams: `sequenceDiagram.html`
- Class diagrams: `classDiagram.html`
- State diagrams: `stateDiagram.html`
- Entity relationship diagrams: `entityRelationshipDiagram.html`
- Gantt charts: `gantt.html`
- Pie charts: `pie.html`
- User journey diagrams: `userJourney.html`
- Mindmaps: `mindmap.html`
- Timelines: `timeline.html`
- Git graphs: `gitgraph.html`

Core syntax reminders:

- Flowcharts begin with `flowchart TD`, `flowchart LR`, `graph TD`, etc. Common nodes: `A[Rectangle]`, `B(Rounded)`, `C{Decision}`, `D((Circle))`, `E[(Database)]`, `F[[Subroutine]]`. Common links: `-->`, `---`, `-.->`, `==>`, `-->|label|`, `<-->`. Use `subgraph Name ... end` for grouping. Comments use `%%`.
- Sequence diagrams begin with `sequenceDiagram`. Use `participant`, messages such as `A->>B: text`, replies `B-->>A: text`, activations `activate A`, `deactivate A`, blocks `alt/else/end`, `loop/end`, `opt/end`, `par/and/end`, and notes such as `Note over A,B: text`.
- Class diagrams begin with `classDiagram`. Define classes with `class Name { +field type +method() }`. Relationships include `<|--`, `*--`, `o--`, `-->`, `..>`, `--`, and labels after `:`.
- State diagrams begin with `stateDiagram-v2`. Use `[*]` for start/end, transitions `A --> B`, composite states with `state Name { ... }`, choices with `<<choice>>`, and notes with `note right of State`.
- ER diagrams begin with `erDiagram`. Relationships use cardinality markers such as `||--o{`, `}|..|{`, and labels after `:`. Entity fields are placed inside `{}` blocks.
- Gantt charts begin with `gantt`, commonly include `title`, `dateFormat`, `section`, tasks, durations, dependencies with `after`, and markers such as `milestone`, `crit`, `active`, `done`.
- Pie charts begin with `pie title ...`, followed by quoted labels and numeric values.
- Mindmaps begin with `mindmap`; indentation creates hierarchy.
- Timelines begin with `timeline`; add `title` and grouped entries by date or period.
- Git graphs begin with `gitGraph`; use `commit`, `branch`, `checkout`, `merge`, and related git-like operations.
- Requirement diagrams begin with `requirementDiagram`; define `requirement`, `element`, and relationship statements for traceability.
- C4 diagrams use `C4Context`, `C4Container`, etc. Common objects include `Person`, `System`, `Container`, `Rel`.

Common gotchas:

- Avoid lowercase `end` as a flowchart node label; capitalize it or quote/escape it.
- Quote labels that contain punctuation likely to confuse the parser.
- Keep diagram declarations at the top of included subdocuments, but remove duplicate declarations when assembling a master preview.
- If a diagram fails, simplify to the smallest valid block, then add elements back.

