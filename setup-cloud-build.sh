#!/bin/bash
# Cloud Build CI/CD setup automation script
# This script sets up automated builds and deployments on every GitHub push

set -e

PROJECT_ID="${GCP_PROJECT_ID:-civil-ai-agent}"
REGION="${GCP_REGION:-asia-south1}"
SERVICE_NAME="civil-ai-agent"
GITHUB_OWNER="${GITHUB_OWNER:-phanimca}"
GITHUB_REPO="${GITHUB_REPO:-civil-ai-agent}"

echo "🚀 Setting up Cloud Build CI/CD for ${SERVICE_NAME}"
echo "   Project: ${PROJECT_ID}"
echo "   Region: ${REGION}"
echo "   GitHub: ${GITHUB_OWNER}/${GITHUB_REPO}"
echo ""

# Step 1: Verify gcloud auth
echo "1️⃣  Verifying gcloud authentication..."
gcloud auth list --filter=status:ACTIVE --format="value(account)" >/dev/null || {
  echo "❌ Not authenticated. Run: gcloud auth login"
  exit 1
}

# Step 2: Set project
echo "2️⃣  Setting GCP project to ${PROJECT_ID}..."
gcloud config set project "${PROJECT_ID}"

# Step 3: Enable required APIs
echo "3️⃣  Enabling required APIs..."
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  --quiet

# Step 4: Get project number
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')
echo "   Project Number: ${PROJECT_NUMBER}"

# Step 5: Create Artifact Registry repo (if not exists)
echo "4️⃣  Setting up Artifact Registry repository..."
gcloud artifacts repositories describe "${SERVICE_NAME}" \
  --location="${REGION}" \
  --repository-format=docker >/dev/null 2>&1 || {
  echo "   Creating repository ${SERVICE_NAME}..."
  gcloud artifacts repositories create "${SERVICE_NAME}" \
    --location="${REGION}" \
    --repository-format=docker \
    --quiet
}

# Step 6: Grant Cloud Build service account permissions
echo "5️⃣  Granting Cloud Build service account permissions..."

echo "   • Cloud Run Admin..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/run.admin" \
  --quiet

echo "   • Secret Manager Secret Accessor..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --quiet

echo "   • Service Account User (for Cloud Run SA)..."
gcloud iam service-accounts add-iam-policy-binding \
  "${PROJECT_NUMBER}@cloudrun.gserviceaccount.com" \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser" \
  --quiet

echo "   • Artifact Registry Writer..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/artifactregistry.writer" \
  --quiet

# Step 7: Connect GitHub repository
echo "6️⃣  Connecting GitHub repository..."
echo "   ℹ️  This will open a browser window to authorize GitHub access."
echo ""
gcloud builds connect \
  --repository-name="${GITHUB_REPO}" \
  --repository-owner="${GITHUB_OWNER}" \
  --region="${REGION}" || {
  echo "   ⚠️  GitHub connection skipped (may already be connected)."
}

# Step 8: Create Build Trigger
echo "7️⃣  Creating Cloud Build trigger..."
TRIGGER_EXISTS=$(gcloud builds triggers list --region="${REGION}" \
  --filter="name:${SERVICE_NAME}-deploy" \
  --format='value(name)' 2>/dev/null || echo "")

if [ -n "$TRIGGER_EXISTS" ]; then
  echo "   ℹ️  Trigger already exists: ${TRIGGER_EXISTS}"
else
  echo "   Creating trigger: ${SERVICE_NAME}-deploy..."
  gcloud builds triggers create github \
    --name="${SERVICE_NAME}-deploy" \
    --repo-name="${GITHUB_REPO}" \
    --repo-owner="${GITHUB_OWNER}" \
    --branch-pattern="^main$" \
    --build-config="cloudbuild.yaml" \
    --region="${REGION}" \
    --quiet
fi

# Step 9: Verify trigger
echo "8️⃣  Verifying Cloud Build trigger..."
TRIGGER_ID=$(gcloud builds triggers list --region="${REGION}" \
  --filter="name:${SERVICE_NAME}-deploy" \
  --format='value(name)')
echo "   ✅ Trigger ID: ${TRIGGER_ID}"

# Step 10: Test trigger (optional)
echo ""
echo "9️⃣  Ready to test!"
echo "   Run this to manually trigger a build:"
echo "   gcloud builds submit --config=cloudbuild.yaml --region=${REGION} --async"
echo ""

# Step 11: Provide summary
echo ""
echo "================================"
echo "✅ Cloud Build CI/CD Setup Complete!"
echo "================================"
echo ""
echo "📋 Summary:"
echo "   • Project: ${PROJECT_ID}"
echo "   • Region: ${REGION}"
echo "   • Service: ${SERVICE_NAME}"
echo "   • GitHub: ${GITHUB_OWNER}/${GITHUB_REPO}"
echo "   • Build Trigger: ${TRIGGER_ID}"
echo ""
echo "🚀 Next Steps:"
echo "   1. Commit and push to main branch:"
echo "      git add cloudbuild.yaml CLOUD_BUILD_CI_CD.md"
echo "      git commit -m 'Add Cloud Build CI/CD configuration'"
echo "      git push origin main"
echo ""
echo "   2. Monitor builds:"
echo "      gcloud builds list --region=${REGION} --limit=10"
echo ""
echo "   3. View build logs:"
echo "      gcloud builds log LATEST --region=${REGION} --stream"
echo ""
echo "   4. Get deployment URL:"
echo "      gcloud run services describe ${SERVICE_NAME} --region=${REGION} --format='value(status.url)'"
echo ""
echo "📚 Documentation:"
echo "   • Cloud Build: https://docs.cloud.google.com/build/docs/overview"
echo "   • Setup Guide: ./CLOUD_BUILD_CI_CD.md"
echo ""
