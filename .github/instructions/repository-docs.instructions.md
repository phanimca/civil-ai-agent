applyTo: ".github/docs/**/*.md,README.md,*.sh,*.ps1"
description: "Use when reorganizing docs, updating references, and maintaining documentation best practices in this repository."
---

# Documentation Maintenance Rules

- Keep project docs centralized in the `.github/docs/` folder.
- Keep file names stable when possible to reduce broken links.
- Prefer relative links from `README.md` and scripts to docs using `.github/docs/<FILE>.md`.
- If a script echoes or references documentation paths, update those paths when docs move.
- Avoid mixing deployment runbooks with application architecture details in the same file.
- Record process-level guidance in `.github/docs/BEST_PRACTICES.md`.
