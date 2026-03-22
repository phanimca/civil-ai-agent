# Cloud Build CI/CD Setup for Civil AI Agent

## Overview

This guide helps you set up automated CI/CD pipelines using **Google Cloud Build** to automatically test, build, and deploy your Streamlit app whenever you push code to GitHub.

**Reference**: [Cloud Build Documentation](https://docs.cloud.google.com/build/docs/overview)

---

## Prerequisites

1. Google Cloud Project with billing enabled
2. `gcloud` CLI installed and authenticated
3. GitHub repository (public or private)
4. Cloud Build, Artifact Registry, Cloud Run APIs enabled

### Enable Required APIs

```bash
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  container.googleapis.com
```

---

## Step 1: Connect GitHub Repository to Cloud Build

### Option A: Using Google Cloud Console (Recommended for first-time setup)

1. Go to [Cloud Build → Repositories](https://console.cloud.google.com/cloud-build/repositories)
2. Click **Connect Repository**
3. Select **GitHub** as source
4. Authorize Google Cloud Build to access your GitHub account
5. Select your `phanimca/civil-ai-agent` repository
6. Click **Connect**

### Option B: Using gcloud CLI

```bash
gcloud builds connect \
  --repository-name=civil-ai-agent \
  --repository-owner=phanimca \
  --region=asia-south1
```

---

## Step 2: Create Build Trigger

### Manual Trigger Setup (via Console)

1. Go to [Cloud Build → Triggers](https://console.cloud.google.com/cloud-build/triggers)
2. Click **Create Trigger**
3. Configure:
   - **Name**: `civil-ai-agent-deploy`
   - **Event**: `Push to branch`
   - **Repository**: `civil-ai-agent`
   - **Branch**: `^main$` (regex for main branch)
   - **Build configuration**: `Cloud Build configuration file`
   - **Configuration file location**: `cloudbuild.yaml`
4. Click **Create**

### Automated Trigger Setup (via CLI)

```bash
gcloud builds triggers create github \
  --name=civil-ai-agent-deploy \
  --repo-name=civil-ai-agent \
  --repo-owner=phanimca \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml \
  --region=asia-south1
```

---

## Step 3: Configure Cloud Build Service Account Permissions

Cloud Build needs permissions to deploy to Cloud Run and access Secret Manager.

### Get your project number

```bash
PROJECT_NUMBER=$(gcloud projects list \
  --filter="projectId=civil-ai-agent" \
  --format='value(projectNumber)')
echo $PROJECT_NUMBER
```

### Grant Cloud Build service account Cloud Run Admin role

```bash
gcloud projects add-iam-policy-binding civil-ai-agent \
  --member=serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com \
  --role=roles/run.admin \
  --quiet
```

### Grant Cloud Build service account access to Secret Manager

```bash
gcloud projects add-iam-policy-binding civil-ai-agent \
  --member=serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor \
  --quiet
```

### Grant Cloud Build service account pass-through to Cloud Run service account

```bash
gcloud iam service-accounts add-iam-policy-binding \
  ${PROJECT_NUMBER}@cloudrun.gserviceaccount.com \
  --member=serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com \
  --role=roles/iam.serviceAccountUser \
  --quiet
```

### Grant Artifact Registry permissions

```bash
gcloud projects add-iam-policy-binding civil-ai-agent \
  --member=serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com \
  --role=roles/artifactregistry.writer \
  --quiet
```

---

## Step 4: Verify Cloud Build Trigger

### Manually trigger a build (for testing)

```bash
gcloud builds submit \
  --config=cloudbuild.yaml \
  --region=asia-south1 \
  --async
```

### Monitor build progress

```bash
gcloud builds log $(gcloud builds list --limit=1 --format='value(ID)') \
  --region=asia-south1 \
  --stream
```

### View all builds

```bash
gcloud builds list --region=asia-south1 --limit=10
```

---

## Step 5: Update Your GitHub Repository

### 1. Commit Cloud Build files

```bash
git add Dockerfile .dockerignore cloudbuild.yaml
git commit -m "Add Cloud Build CI/CD configuration"
git push origin main
```

### 2. This automatically triggers a build!

Once you push, Cloud Build will:
- ✅ Build Docker image
- ✅ Push to Artifact Registry
- ✅ Deploy to Cloud Run
- ✅ Show deployment URL

---

## Step 6: Monitor Builds and Deployments

### View build history in console

```bash
gcloud builds list \
  --region=asia-south1 \
  --limit=20 \
  --format='table(ID,CREATE_TIME,SUBSTITUTIONS._SERVICE,BUILD_STATUS)'
```

### Get detailed build logs

```bash
BUILD_ID=$(gcloud builds list --limit=1 --region=asia-south1 --format='value(ID)')
gcloud builds log $BUILD_ID --region=asia-south1 --stream
```

### Get Cloud Run service URL after deployment

```bash
gcloud run services describe civil-ai-agent \
  --region=asia-south1 \
  --format='value(status.url)'
```

---

## Step 7: Set Up Build Notifications (Optional)

### Configure Slack Notifications

1. Create a Pub/Sub topic:
```bash
gcloud pubsub topics create cloud-builds
```

2. Create a Slack notifier:
```bash
gcloud builds notifiers create slack \
  --display-name=civil-ai-slack \
  --channel=#deployments \
  --slack-channel-override=#deployments
```

3. Subscribe to build events:
```bash
gcloud builds notifiers update slack \
  --build-filter='status == "SUCCESS" OR status == "FAILURE"'
```

### View available notifiers

```bash
gcloud builds notifiers list
```

---

## Step 8: View Build Security Insights (Optional)

Cloud Build provides **SLSA level 3** security compliance and build provenance tracking.

### View security insights in Cloud Console

1. Go to [Cloud Build → Security Insights](https://console.cloud.google.com/cloud-build/security-insights)
2. Review:
   - SLSA Level maturity
   - Detected vulnerabilities
   - Build provenance details

### Export build provenance (for audit)

```bash
gcloud builds describe $BUILD_ID \
  --region=asia-south1 \
  --format='value(build_provenance)' | jq .
```

---

## Advanced: Build Triggers for Multiple Branches

### Deploy `develop` to staging Cloud Run service

```bash
gcloud builds triggers create github \
  --name=civil-ai-deploy-staging \
  --repo-name=civil-ai-agent \
  --repo-owner=phanimca \
  --branch-pattern="^develop$" \
  --build-config=cloudbuild.yaml \
  --substitutions=_SERVICE=civil-ai-agent-staging,_REGION=asia-south1 \
  --region=asia-south1
```

### Deploy `main` to production (with approval)

```bash
gcloud builds triggers create github \
  --name=civil-ai-deploy-prod \
  --repo-name=civil-ai-agent \
  --repo-owner=phanimca \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml \
  --require-approval \
  --region=asia-south1
```

---

## Troubleshooting

### "Permission denied" errors

**Problem**: Build fails with permission issues.

**Solution**: Re-grant IAM permissions (see Step 3):
```bash
PROJECT_NUMBER=$(gcloud projects describe civil-ai-agent --format='value(projectNumber)')
gcloud projects add-iam-policy-binding civil-ai-agent \
  --member=serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com \
  --role=roles/run.admin
```

### "Secret not found" errors

**Problem**: Cloud Run deployment fails accessing secrets.

**Solution**: Ensure secrets exist in Secret Manager:
```bash
gcloud secrets list
# Should show: OPENAI_TOKEN, HF_TOKEN, BREVO_API_KEY, etc.
```

If missing, add them:
```bash
echo -n "your_token_value" | gcloud secrets create OPENAI_TOKEN --data-file=-
```

### Build timeout

**Problem**: Build exceeds timeout (default 10 mins).

**Solution**: Increase timeout in `cloudbuild.yaml`:
```yaml
timeout: 3600s  # 1 hour
```

Or via CLI:
```bash
gcloud builds submit \
  --config=cloudbuild.yaml \
  --timeout=3600s
```

### Docker image push fails

**Problem**: "Access denied" when pushing to Artifact Registry.

**Solution**: Authenticate Docker and ensure Cloud Build SA has permissions:
```bash
gcloud auth configure-docker asia-south1-docker.pkg.dev
gcloud projects add-iam-policy-binding civil-ai-agent \
  --member=serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com \
  --role=roles/artifactregistry.writer
```

---

## Monitoring and Alerting

### Set up build failure alerts

```bash
gcloud alpha monitoring alerting policies create \
  --notification-channels=CHANNEL_ID \
  --condition "cloudbuild.googleapis.com/build_failure_rate > 0"
```

### Export metrics to BigQuery (for analysis)

```bash
gcloud builds log $(BUILD_ID) --stream=false | bq load --source_format=NEWLINE_DELIMITED_JSON \
  civil_ai.build_logs - build_logs_schema.json
```

---

## Cost Optimization

### Reduce build costs

1. **Use faster machine types** (already set to `N1_HIGHCPU_8`):
   ```yaml
   machineType: N1_HIGHCPU_8
   ```

2. **Cache Docker layers** (enable BuildKit):
   ```yaml
   env:
     - DOCKER_BUILDKIT=1
   ```

3. **Only build on main branch** (avoid building for every commit):
   ```bash
   --branch-pattern="^main$"
   ```

### Free tier limits

- **Cloud Build**: 120 build-minutes/day free
- **Cloud Run**: 2M requests/month, 360K GB-seconds/month free
- **Artifact Registry**: 0.5 GiB/month free

---

## What's Next

- ✅ Set up Slack notifications for build status
- ✅ Add custom domain mapping to Cloud Run
- ✅ Set up scheduled builds for regular deployments
- ✅ Configure Binary Authorization for signed image deployments
- ✅ Add security scanning (Artifact Analysis)

---

## Useful Commands Cheat Sheet

```bash
# List all builds
gcloud builds list --region=asia-south1 --limit=10

# View specific build logs
gcloud builds log BUILD_ID --region=asia-south1

# Manually trigger build
gcloud builds submit --config=cloudbuild.yaml --region=asia-south1

# List triggers
gcloud builds triggers list --region=asia-south1

# Delete a trigger
gcloud builds triggers delete TRIGGER_ID --region=asia-south1

# Update Cloud Run deployment manually
gcloud run deploy civil-ai-agent --image=IMAGE_URL --region=asia-south1

# Get Cloud Run service URL
gcloud run services describe civil-ai-agent --region=asia-south1 --format='value(status.url)'

# View Cloud Run logs
gcloud run logs read civil-ai-agent --region=asia-south1 --limit=50
```

---

## References

- [Cloud Build Overview](https://docs.cloud.google.com/build/docs/overview)
- [Cloud Build Quickstart](https://docs.cloud.google.com/build/docs/quickstart-docker)
- [Cloud Build Triggers](https://docs.cloud.google.com/build/docs/triggers)
- [Deploy to Cloud Run](https://docs.cloud.google.com/build/docs/deploying-builds/deploy-cloud-run)
- [Cloud Build Security](https://docs.cloud.google.com/build/docs/securing-builds/overview)
- [SLSA Framework](https://slsa.dev/)
