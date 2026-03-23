---
name: google-cloud-deployment
description: "Use when user selects Google Cloud deployment for this project (Cloud Run/Cloud Build), including secrets, IAM checks, and deploy verification."
---

# Google Cloud Deployment Skill

## Use When
- User chooses Google Cloud as deployment server.
- User asks for Cloud Run or Cloud Build deployment steps.

## Preconditions
- `gcloud` CLI installed and authenticated.
- Correct GCP project and region selected.
- Required root deployment files present: `Dockerfile`, `cloudbuild.yaml`, `cloud-run-service.yaml`.

## Required Checks
1. Confirm APIs enabled: Cloud Run, Cloud Build, Secret Manager, Artifact Registry.
2. Confirm required secrets exist (names only, no values).
3. Confirm service account permissions for deployment flow.
4. Confirm runtime configuration for Streamlit server flags.

## Execution Pattern
1. Validate configuration and prerequisites.
2. Build and deploy via repository scripts/config first (`deploy.sh`, `setup-cloud-build.sh`, `cloudbuild.yaml`).
3. Apply minimal overrides only when requested.
4. Return service URL and health-check steps.

## Verification Checklist
- [ ] Build completed successfully
- [ ] Cloud Run revision is healthy
- [ ] App URL returns expected response
- [ ] Logs show no startup import/secrets errors

## Failure Handling
- Classify failures as IAM, secret, build, runtime, or networking.
- Provide exact command to diagnose each class.
- Suggest the smallest fix and re-verify.
