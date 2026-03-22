#!/bin/bash
# Setup Google Cloud Secret Manager for Civil AI Agent secrets
# Usage: ./setup-secrets.sh

PROJECT_ID="${GCP_PROJECT_ID:-civil-ai-agent}"

echo "🔐 Setting up Secret Manager for ${PROJECT_ID}"
echo ""

# List of secrets to setup
SECRETS=(
  "OPENAI_TOKEN"
  "HF_TOKEN"
  "BREVO_API_KEY"
  "BREVO_FROM_EMAIL"
  "BREVO_FROM_NAME"
  "RESEND_API_KEY"
  "EMAIL_FROM"
  "ADMIN_SEED_EMAIL"
)

# Enable Secret Manager API
echo "Enabling Secret Manager API..."
gcloud services enable secretmanager.googleapis.com --project="${PROJECT_ID}" --quiet

echo ""
echo "Creating/updating secrets..."
echo ""

for SECRET in "${SECRETS[@]}"; do
  VALUE=$(grep "^${SECRET}=" ../.env | cut -d= -f2-)
  
  if [ -z "$VALUE" ]; then
    echo "⚠️  ${SECRET}: Not found in .env (skipping)"
    continue
  fi
  
  # Check if secret exists
  if gcloud secrets describe "${SECRET}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    echo "✏️  Updating ${SECRET}..."
    echo -n "$VALUE" | gcloud secrets versions add "${SECRET}" \
      --data-file=- \
      --project="${PROJECT_ID}" \
      --quiet
  else
    echo "➕ Creating ${SECRET}..."
    echo -n "$VALUE" | gcloud secrets create "${SECRET}" \
      --data-file=- \
      --replication-policy="automatic" \
      --project="${PROJECT_ID}" \
      --quiet
  fi
done

echo ""
echo "✅ Secrets configured!"
echo ""
echo "⚠️  Important: Add IAM binding so Cloud Run can access secrets:"
echo ""
echo "PROJECT_ID=\$(gcloud config get-value project)"
echo "SA_EMAIL=\"\${PROJECT_ID}@appspot.gserviceaccount.com\""
echo ""
for SECRET in "${SECRETS[@]}"; do
  echo "gcloud secrets add-iam-policy-binding ${SECRET} \\"
  echo "  --member=\"serviceAccount:\${SA_EMAIL}\" \\"
  echo "  --role=\"roles/secretmanager.secretAccessor\" \\"
  echo "  --quiet"
done
