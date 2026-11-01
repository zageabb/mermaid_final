# Experimental diagram-core integration

This branch adds an optional endpoint alongside the existing /repository/export/... .mmd download. Existing exports are unchanged.

## Preconditions
- diagram-core PR in zageabb/shared-capabilities must be reviewed and merged with successful CI, and then released as a pinned version.
- Install the tagged package in a controlled environment with its optional pptx dependency. Do not install directly from a moving feature branch on the production server.
- Set MERMAID_PPTX_EXPERIMENTAL=1 only after confirming access controls, dependency provenance and file export test coverage. Default is disabled (404).
- URL: /repository/export-pptx/<project>/<diagram>/<revision> using the same existing repository identifier format as the .mmd export endpoint.

## Behaviour
- Export native editable flowchart nodes and connectors.
- Unsupported Mermaid constructs return 422, with no silent bitmap fallback.
- Missing optional package returns 503.
- The original Mermaid editor, AI panel, repository storage and .mmd route are unchanged.
- A visual export button has not yet been added.

## Acceptance gates
1. CI and integration regression tests, including default disabled mode and error handling.
2. Confirm the diagram-core export produces editable PowerPoint shapes with a representative diagram corpus.
3. Review the existing repository export permissions and UDA authentication boundaries.
4. Release/tag shared package and pin exact version here before enabling in deployment.
5. Update user manual when the UI entry point is added.

## Rollback
Unset MERMAID_PPTX_EXPERIMENTAL and restart the service; the additional endpoint becomes unavailable. No user data migrations are involved.
