# Deployment Guide for Civil AI Agent on Google Cloud

## Overview
This guide walks you through deploying the Civil AI Agent (Streamlit app) to **Google Cloud Run** with secure secret management via **Secret Manager**.

---

## Prerequisites

1. **Google Cloud Project**: Created and billing enabled
2. **gcloud CLI**: Installed and authenticated
   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```
3. **Docker**: Installed locally (for building images)
4. **Git**: Repository pushed to GitHub

---

## Step 1: Prepare Your Local Environment

### 1.1 Set environment variables (for convenience)
```bash
export GCP_PROJECT_ID=civil-ai-agent
export GCP_REGION=asia-south1
```

### 1.2 Ensure `.env` file is in repo root (local only, not committed)
```bash
cat .env  # Verify it has all required secrets
```

### 1.3 Make deployment scripts executable
```bash
chmod +x deploy.sh setup-secrets.sh
```

---

## Step 2: Set Up Google Cloud Project

### 2.1 Set default project
```bash
gcloud config set project $GCP_PROJECT_ID
```

### 2.2 Enable required APIs
```bash
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com
```

### 2.3 Create Artifact Registry (Docker image storage)
```bash
gcloud artifacts repositories create civil-ai-agent \
  --location=$GCP_REGION \
  --repository-format=docker
```

---

## Step 3: Configure Secret Manager

### 3.1 Enable Secret Manager API (if not already done)
```bash
gcloud services enable secretmanager.googleapis.com
```

### 3.2 Create secrets from `.env` file
```bash
# Example for one secret (repeat for each):
echo -n "your_openai_token_here" | \
  gcloud secrets create OPENAI_TOKEN \
    --data-file=- \
    --replication-policy="automatic"
```

**Easier way: Use the provided script**
```bash
./setup-secrets.sh
```

### 3.3 Grant Cloud Run service account access to secrets

Get your project number:
```bash
PROJECT_NUMBER=$(gcloud projects describe $GCP_PROJECT_ID --format='value(projectNumber)')
SA_EMAIL="${PROJECT_NUMBER}@cloudrun.gserviceaccount.com"
```

Grant Secret Manager access:
```bash
gcloud secrets add-iam-policy-binding OPENAI_TOKEN \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" \
  --quiet

# Repeat for all secrets:
# BREVO_API_KEY, HF_TOKEN, RESEND_API_KEY, EMAIL_FROM, ADMIN_SEED_EMAIL, etc.
```

**Or use a loop:**
```bash
for SECRET in OPENAI_TOKEN HF_TOKEN BREVO_API_KEY BREVO_FROM_EMAIL BREVO_FROM_NAME \
             RESEND_API_KEY EMAIL_FROM ADMIN_SEED_EMAIL; do
  gcloud secrets add-iam-policy-binding "$SECRET" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet
done
```

---

## Step 4: Build and Deploy

### 4.1 Automated deployment (recommended)
```bash
./deploy.sh
```

### 4.2 Manual deployment (if preferred)

**Step 4.2.1: Authenticate Docker**
```bash
gcloud auth configure-docker $GCP_REGION-docker.pkg.dev
```

**Step 4.2.2: Build Docker image**
```bash
IMAGE_TAG="$GCP_REGION-docker.pkg.dev/$GCP_PROJECT_ID/civil-ai-agent/civil-ai-agent:latest"
docker build -t $IMAGE_TAG .
```

**Step 4.2.3: Push to Artifact Registry**
```bash
docker push $IMAGE_TAG
```

**Step 4.2.4: Deploy to Cloud Run**
```bash
gcloud run deploy civil-ai-agent \
  --image=$IMAGE_TAG \
  --region=$GCP_REGION \
  --platform=managed \
  --min-instances=0 \
  --max-instances=1 \
  --concurrency=2 \
  --memory=1Gi \
  --cpu=0.5 \
  --timeout=900 \
  --cpu-throttling \
  --no-cpu-boost \
  --allow-unauthenticated \
  --port=8080 \
  --set-env-vars="STREAMLIT_SERVER_HEADLESS=true" \
  --set-env-vars="STREAMLIT_SERVER_ENABLEXSRFPROTECTION=false" \
  --set-env-vars="STREAMLIT_SERVER_ENABLECORS=false" \
  --set-secrets="OPENAI_TOKEN=OPENAI_TOKEN:latest" \
  --set-secrets="HF_TOKEN=HF_TOKEN:latest" \
  --set-secrets="BREVO_API_KEY=BREVO_API_KEY:latest" \
  --set-secrets="BREVO_FROM_EMAIL=BREVO_FROM_EMAIL:latest" \
  --set-secrets="BREVO_FROM_NAME=BREVO_FROM_NAME:latest" \
  --set-secrets="RESEND_API_KEY=RESEND_API_KEY:latest" \
  --set-secrets="EMAIL_FROM=EMAIL_FROM:latest" \
  --set-secrets="ADMIN_SEED_EMAIL=ADMIN_SEED_EMAIL:latest"
```

---

## Step 5: Verify Deployment

### 5.1 Get service URL
```bash
gcloud run services describe civil-ai-agent \
  --region=$GCP_REGION \
  --format='value(status.url)'
```

### 5.2 Test the app
```bash
# Open the URL in your browser
# Or test with curl:
curl https://civil-ai-agent-{random-id}.$GCP_REGION.run.app
```

### 5.3 View real-time logs
```bash
gcloud run logs read civil-ai-agent \
  --region=$GCP_REGION \
  --limit=50 \
  --follow
```

---

## Step 6: Post-Deployment Configuration

### 6.1 Set up automatic deployments (optional)

**Connect GitHub to Cloud Build:**
```bash
gcloud builds connect --repository-name=civil-ai-agent \
  --repository-owner=phanimca \
  --region=$GCP_REGION
```

**Create Cloud Build trigger** (UI or gcloud):
```bash
gcloud builds triggers create github \
  --name=civil-ai-agent-deploy \
  --repo-name=civil-ai-agent \
  --repo-owner=phanimca \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml \
  --region=$GCP_REGION
```

### 6.2 Set up custom domain (optional)
```bash
gcloud run domain-mappings create \
  --service=civil-ai-agent \
  --domain=your-domain.com \
  --region=$GCP_REGION
```

Then add the CNAME record to your DNS provider.

### 6.3 Enable Cloud Monitoring/Logging
Automatically available in Cloud Console under **Cloud Run** → **Logs**.

---

## Step 7: Update Secrets

To update a secret (e.g., after rotating API keys):

```bash
echo -n "new_secret_value" | gcloud secrets versions add OPENAI_TOKEN --data-file=-
```

Then redeploy Cloud Run to pick up the new version:
```bash
gcloud run deploy civil-ai-agent \
  --image=$IMAGE_TAG \
  --region=$GCP_REGION \
  --update-secrets=OPENAI_TOKEN=latest:latest
```

---

## Step 8: Cost Optimization

### 8.1 Monitor costs
```bash
gcloud billing accounts list
```

### 8.2 Set up budget alerts
Use Cloud Console: **Billing** → **Budgets and alerts**

### 8.3 Optimize Cloud Run
- **CPU allocation**: Use `--cpu-throttling` (request-only CPU) for lower idle compute charges
- **Startup CPU boost**: Disable with `--no-cpu-boost` for strict cost control
- **Memory**: Start at `1Gi`; drop to `512Mi` only if your app remains stable
- **Min instances**: Keep at `0` to avoid always-on charges
- **Max instances**: Set `1` to cap burst spend and stay Free Tier friendly
- **Concurrency**: Set `2` to reduce memory pressure for Streamlit sessions

---

## Troubleshooting

### Issue: "Permission denied" when accessing secrets
**Solution**: Verify IAM binding:
```bash
gcloud secrets get-iam-policy OPENAI_TOKEN
# Should show cloudrun.gserviceaccount.com in the bindings
```

### Issue: Container won't start / logs show import errors
**Solution**: Check logs and verify all dependencies in `requirements.txt`:
```bash
gcloud run logs read civil-ai-agent --region=$GCP_REGION --limit=100
```

### Issue: Streamlit won't load / "Something went wrong"
**Solution**: Add these env vars to Cloud Run:
```
STREAMLIT_SERVER_HEADLESS=true
STREAMLIT_SERVER_ENABLEXSRFPROTECTION=false
```

### Issue: Cold start time is slow
**Solution**: Set min-instances to 1 (costs extra):
```bash
gcloud run deploy civil-ai-agent \
  --min-instances=1 \
  --region=$GCP_REGION
```

---

## Cleanup (if needed)

### Delete Cloud Run service
```bash
gcloud run services delete civil-ai-agent --region=$GCP_REGION
```

### Delete secrets
```bash
gcloud secrets delete OPENAI_TOKEN
# Repeat for all secrets
```

### Delete Artifact Registry repository
```bash
gcloud artifacts repositories delete civil-ai-agent --location=$GCP_REGION
```

---

## Additional Resources

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Secret Manager Documentation](https://cloud.google.com/secret-manager/docs)
- [Streamlit on Cloud Run](https://discuss.streamlit.io/t/deploying-streamlit-apps-on-google-cloud/10717)
- [gcloud CLI Reference](https://cloud.google.com/sdk/gcloud/reference)
