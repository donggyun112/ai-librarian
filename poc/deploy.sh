#!/bin/bash

# GCP Cloud Run Deployment Script
# This script deploys the AI Librarian Streamlit app to Google Cloud Run

set -e          # Exit on error
set -o pipefail # Exit if any command in a pipe fails


# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-angelic-edition-325910}"
SERVICE_NAME="${SERVICE_NAME:-ai-librarian}"
REGION="${GCP_REGION:-us-central1}"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo -e "${GREEN}🚀 Starting Cloud Run Deployment${NC}"
echo "Project ID: ${PROJECT_ID}"
echo "Service Name: ${SERVICE_NAME}"
echo "Region: ${REGION}"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI is not installed${NC}"
    echo "Install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Docker check removed - using Cloud Build

# Check if secrets exist
echo -e "${YELLOW}📋 Checking if secrets exist...${NC}"
SECRETS_MISSING=false

for secret in openai-api-key zilliz-host zilliz-token; do
    if ! gcloud secrets describe $secret --project=$PROJECT_ID &> /dev/null; then
        echo -e "${RED}❌ Secret '$secret' not found${NC}"
        SECRETS_MISSING=true
    else
        echo -e "${GREEN}✅ Secret '$secret' exists${NC}"
    fi
done

if [ "$SECRETS_MISSING" = true ]; then
    echo -e "${RED}❌ Some secrets are missing. Run ./setup_secrets.py first.${NC}"
    exit 1
fi

# Check if user is authenticated
echo -e "${YELLOW}📋 Checking GCP authentication...${NC}"
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo -e "${YELLOW}⚠️  Not authenticated. Running gcloud auth login...${NC}"
    gcloud auth login
fi

# Set the project
echo -e "${YELLOW}📋 Setting GCP project...${NC}"
gcloud config set project ${PROJECT_ID}

# Build the Docker image
echo -e "${YELLOW}📦 Exporting requirements...${NC}"
# Try to export, but proceed if it fails (fallback to existing requirements.txt)
if poetry export -f requirements.txt --output requirements.txt --without-hashes 2>/dev/null; then
    echo -e "${GREEN}✅ Requirements exported successfully${NC}"
else
    echo -e "${YELLOW}⚠️  Poetry export failed or plugin missing. Using existing requirements.txt${NC}"
fi

# Build and Push image using Google Cloud Build
echo -e "${YELLOW}☁️  Building and Pushing image via Cloud Build...${NC}"
echo "Submitting build to Cloud Build..."
gcloud builds submit --tag ${IMAGE_NAME} .

# Deploy to Cloud Run
echo -e "${YELLOW}🚀 Deploying to Cloud Run...${NC}"
echo "Deploying service..."

# Flattened command to avoid line continuation errors
gcloud run deploy ${SERVICE_NAME} --image ${IMAGE_NAME} --platform managed --region ${REGION} --allow-unauthenticated --port 8080 --memory 2Gi --cpu 2 --timeout 300 --max-instances 10 --set-env-vars "ENVIRONMENT=production" --update-secrets "OPENAI_API_KEY=openai-api-key:latest,ZILLIZ_HOST=zilliz-host:latest,ZILLIZ_TOKEN=zilliz-token:latest"

echo ""
echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""
echo "To get the service URL, run:"
echo "  gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)'"