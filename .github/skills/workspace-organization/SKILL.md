---
name: workspace-organization
description: "Use when the user asks to organize repository files, centralize documentation, or update repo-level best practices and navigation."
---

# Workspace Organization Skill

## Use When
- The user asks to tidy folder structure.
- The user asks to move documents into a dedicated location.
- The user asks to refresh project best-practices documentation.

## Steps
1. Identify documentation files and classify by audience (operators, developers, admins).
2. Move docs into `.github/docs/` with minimal renaming.
3. Update all references in scripts and root docs.
4. Add `.github/docs/README.md` with a quick index.
5. Update `.github/docs/BEST_PRACTICES.md` with repository-specific guidance.

## Quality Checklist
- No broken local relative references from root scripts and README.
- Root `README.md` points to doc index.
- Deployment-critical files remain in root.
- Documentation changes do not alter application code paths.
