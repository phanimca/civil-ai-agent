#!/bin/bash
set -e

# Google Cloud deployment script for Civil AI Agent
# Usage: ./deploy.sh

PROJECT_ID="${GCP_PROJECT_ID:-civil-ai-agent}"
REGION="${GCP_REGION:-asia-south1}"
SERVICE_NAME="civil-ai-agent"
IMAGE_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/${SERVICE_NAME}/${SERVICE_NAME}:latest"

echo "🚀 Starting deployment for ${SERVICE_NAME}"
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Image: ${IMAGE_TAG}"
echo ""

# Step 1: Ensure gcloud is authenticated
echo "1️⃣  Checking gcloud authentication..."
gcloud auth list --filter=status:ACTIVE --format="value(account)" || {
  echo "❌ Not authenticated. Run: gcloud auth login"
  exit 1
}

# Step 2: Set project
echo "2️⃣  Setting project to ${PROJECT_ID}..."
gcloud config set project "${PROJECT_ID}"

# Step 3: Enable required APIs
echo "3️⃣  Enabling required Google Cloud APIs..."
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  --quiet

# Step 4: Create Artifact Registry repository if needed
echo "4️⃣  Setting up Artifact Registry..."
gcloud artifacts repositories describe "${SERVICE_NAME}" \
  --location="${REGION}" \
  --repository-format=docker >/dev/null 2>&1 || {
  echo "   Creating repository ${SERVICE_NAME} in ${REGION}..."
  gcloud artifacts repositories create "${SERVICE_NAME}" \
    --location="${REGION}" \
    --repository-format=docker
}

# Step 5: Configure Docker authentication for Artifact Registry
echo "5️⃣  Configuring Docker authentication..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# Step 6: Build image
echo "6️⃣  Building Docker image..."
docker build -t "${IMAGE_TAG}" .

# Step 7: Push image
echo "7️⃣  Pushing image to Artifact Registry..."
docker push "${IMAGE_TAG}"

# Step 8: Deploy to Cloud Run
echo "8️⃣  Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image="${IMAGE_TAG}" \
  --region="${REGION}" \
  --platform=managed \
  --memory=1Gi \
  --cpu=0.5 \
  --timeout=3600 \
  --max-instances=10 \
  --allow-unauthenticated \
  --port=8080 \
  --set-env-vars="STREAMLIT_SERVER_HEADLESS=true" \
  --set-env-vars="STREAMLIT_SERVER_ENABLEXSRFPROTECTION=false" \
  --set-secrets="OPENAI_TOKEN=OPENAI_TOKEN:latest" \
  --set-secrets="HF_TOKEN=HF_TOKEN:latest" \
  --set-secrets="BREVO_API_KEY=BREVO_API_KEY:latest" \
  --set-secrets="BREVO_FROM_EMAIL=BREVO_FROM_EMAIL:latest" \
  --set-secrets="BREVO_FROM_NAME=BREVO_FROM_NAME:latest" \
  --set-secrets="RESEND_API_KEY=RESEND_API_KEY:latest" \
  --set-secrets="EMAIL_FROM=EMAIL_FROM:latest" \
  --set-secrets="ADMIN_SEED_EMAIL=ADMIN_SEED_EMAIL:latest"

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 Next steps:"
echo "1. Get the service URL:"
echo "   gcloud run services describe ${SERVICE_NAME} --region=${REGION} --format='value(status.url)'"
echo ""
echo "2. View logs:"
echo "   gcloud run logs read ${SERVICE_NAME} --region=${REGION} --limit=50"
echo ""
echo "3. Update secrets (if needed):"
echo "   gcloud secrets versions add OPENAI_TOKEN --data-file=-"
