# Repository Best Practices

This guidance is based on the current repository structure and recent commit history (deployment and setup changes are frequent).

## Documentation
- Keep operational and architecture docs under `docs/`.
- Keep root `README.md` as the primary entry point and link out to docs.
- Update script output and references whenever documentation paths change.

## Deployment Files
- Keep deployment-critical files in repository root:
  - `Dockerfile`
  - `cloudbuild.yaml`
  - `cloud-run-service.yaml`
  - `requirements.txt`
  - `packages.txt`
  - `runtime.txt`
- Treat Cloud Run and Cloud Build docs as living runbooks and keep them aligned with scripts.

## Python and App Structure
- Preserve module boundaries under `app/` (`config`, `data`, `services`, `ui`).
- Prefer targeted fixes over wide refactors unless explicitly requested.
- Add comments only when code intent is not obvious.

## Configuration and Secrets
- Never commit secrets (`.env`, keys, tokens).
- Keep sample values clearly marked as placeholders.
- Ensure deployment docs refer to secret managers or environment variables, not hardcoded credentials.

## Validation Workflow
- After documentation reorganization, verify all path references from root scripts and root docs.
- After Python changes, run lightweight checks first (syntax/lint) before broader tests.
