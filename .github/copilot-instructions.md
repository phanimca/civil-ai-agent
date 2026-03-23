# Copilot Workspace Instructions

## Scope
- This repository is a Python Streamlit application for civil inspection workflows.
- Prefer minimal, targeted changes over broad refactors.
- Keep deployment-critical files in repository root: `Dockerfile`, `cloudbuild.yaml`, `cloud-run-service.yaml`, `requirements.txt`, `packages.txt`, `runtime.txt`.

## Coding Conventions
- Preserve existing module layout under `app/`.
- Add concise comments only where logic is non-obvious.
- Avoid introducing new dependencies unless needed.
- Keep secrets out of source control and examples.

## Docs Conventions
- Put operational and project documentation in `.github/docs/`.
- Keep root `README.md` as the main project entry point.
- When moving docs, update references in scripts and top-level docs.

## Validation
- After edits, run focused checks relevant to changed files.
- For Python code changes, prefer lightweight syntax/lint checks before full test runs.
