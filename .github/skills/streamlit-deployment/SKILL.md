---
name: streamlit-deployment
description: "Use when user selects Streamlit deployment server (including 'Stemlit' typo), covering dependency files, secrets setup, and smoke-test verification."
---

# Streamlit Deployment Skill

## Use When
- User chooses Streamlit as deployment server.
- User asks to deploy to Streamlit Community Cloud.

## Preconditions
- Repository contains root deployment files used by Streamlit Cloud: `requirements.txt`, `packages.txt`, `runtime.txt`.
- Main entrypoint is confirmed (`app/main.py`).

## Required Checks
1. Validate `requirements.txt` and `packages.txt` are deployment-ready.
2. Confirm expected secrets are configured in Streamlit settings (names only).
3. Confirm Python version pin in `runtime.txt`.
4. Confirm no local-only assumptions (`.env` only) for cloud runtime.

## Execution Pattern
1. Verify deployment files and entrypoint.
2. Provide Streamlit app creation steps and secrets mapping.
3. Guide first deploy and monitor startup logs.
4. Provide functional smoke test list (auth, upload, AI report, PDF).

## Verification Checklist
- [ ] App booted without import/runtime errors
- [ ] Secrets are available at runtime
- [ ] Model/report generation path works
- [ ] PDF download path works

## Failure Handling
- Separate dependency errors from secrets/config errors.
- Recommend minimal file or settings fix.
- Re-run smoke tests after each fix.
