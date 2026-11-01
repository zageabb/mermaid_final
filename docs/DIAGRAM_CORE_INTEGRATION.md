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
- A gated Export PPTX button is now present in active and revision-history repository rows; it appears only when MERMAID_PPTX_EXPERIMENTAL=1. Existing Export .mmd remains available.

## Acceptance gates
1. CI and integration regression tests, including default disabled mode and error handling.
2. Confirm the diagram-core export produces editable PowerPoint shapes with a representative diagram corpus.
3. Review the existing repository export permissions and UDA authentication boundaries.
4. Release/tag shared package and pin exact version here before enabling in deployment.
5. Confirm UI tests, update user manual and include clear limitations about supported flowcharts before enabling the flag.

## Rollback
Unset MERMAID_PPTX_EXPERIMENTAL and restart the service; the additional endpoint becomes unavailable. No user data migrations are involved.

## Real-library CI gate

The separate `Real diagram-core compatibility` workflow installs shared-capabilities at the immutable commit `434a6759d0c8e71d169d05948a0367707e53ba00`, then runs `tests/test_real_diagram_core.py` with actual PowerPoint shape assertions.

For a private repository, configure `SHARED_CAPABILITIES_READ_TOKEN` as a GitHub Actions repository secret. Use a fine-grained token with **read-only Contents** access to `zageabb/shared-capabilities`; never add the token to source or workflow logs. If the secret is not present, the workflow fails explicitly rather than reporting a misleading compatibility success. Replace the pinned commit with a released semver tag or immutable released SHA after the package release is approved.

The older isolated integration workflow uses stubs and is not a substitute for this real-library compatibility gate. Do not merge, deploy or enable the experimental endpoint until both workflows pass and release/access control review is completed.
