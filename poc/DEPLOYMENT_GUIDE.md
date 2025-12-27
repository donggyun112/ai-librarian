# 🚀 GCP Cloud Run Deployment Guide

Complete guide for deploying the AI Librarian RAG system to Google Cloud Run.

---

## 📋 Table of Contents

1. [Current Status](#current-status)
2. [Prerequisites](#prerequisites)
3. [What's Already Done](#whats-already-done)
4. [Quick Deployment (3 Steps)](#quick-deployment-3-steps)
5. [Detailed Deployment Steps](#detailed-deployment-steps)
6. [Testing Your Deployment](#testing-your-deployment)
7. [Configuration Options](#configuration-options)
8. [Troubleshooting](#troubleshooting)
9. [Cost Management](#cost-management)

---

## 🎯 Current Status

```
[████████████████████░] 90% Complete

✅ GCP Project configured (angelic-edition-325910)
✅ Billing enabled
✅ APIs enabled (Cloud Build, Cloud Run, Container Registry, Secret Manager)
✅ Docker configured & tested
✅ Deployment scripts ready
⏳ Waiting for API keys
☐ Create secrets
☐ Deploy to Cloud Run
☐ Test deployment
```

### What's Configured

- **Project ID**: angelic-edition-325910
- **Project Number**: 1045672892426
- **Billing**: Enabled
- **Authentication**: leeyj0304@gmail.com
- **Docker Image**: Built and tested locally
- **Deployment Script**: Ready (`deploy.sh`)

### What's Missing

You need these **three API keys** from your team members:

1. **OpenAI API Key** (format: `sk-...`)

   - Get from: https://platform.openai.com/api-keys
   - Used for: GPT-4o-mini model and text embeddings

2. **Zilliz Host URL** (format: `https://xxx.zillizcloud.com`)

   - Get from: Zilliz Cloud dashboard
   - Used for: Vector database connection

3. **Zilliz Token** (API key)
   - Get from: Zilliz Cloud dashboard → API Keys
   - Used for: Vector database authentication

---

## ✅ Prerequisites

### Already Installed & Configured

- ✅ **gcloud CLI**: Version 548.0.0
- ✅ **Docker**: Version 27.4.0
- ✅ **GCP Authentication**: Configured
- ✅ **Required APIs**: All enabled
- ✅ **Docker GCR Auth**: Configured

### Tools Reference

If you ever need to reinstall:

```bash
# macOS
brew install google-cloud-sdk
brew install --cask docker

# Verify installations
gcloud --version
docker --version
```

---

## 🎉 What's Already Done

Your project is **90% ready**! Here's everything that's been set up:

### Infrastructure Setup

1. **GCP Project**: angelic-edition-325910
2. **Billing**: Enabled (Account: 0137B9-57D2B5-B78C59)
3. **Authentication**: Configured
4. **Required APIs**: All enabled
   - Cloud Build API
   - Cloud Run API
   - Container Registry API
   - Secret Manager API

### Docker Setup

1. **Docker**: Installed and configured
2. **GCR Authentication**: Configured for pushing images
3. **Docker Image**: Built and tested successfully
   - Image: `gcr.io/angelic-edition-325910/ai-librarian`

### Deployment Files

1. **Dockerfile**: Container definition
2. **uv.lock / pyproject.toml**: Python dependencies (uv)
3. **.dockerignore**: Optimized build context
4. **deploy.sh**: Automated deployment script with secret validation

---

## 🚀 Quick Deployment (3 Steps)

Once you receive the API keys from your team, follow these steps:

### Step 1: Set Environment Variables (Temporary)

```bash
# Save keys as environment variables temporarily
export OPENAI_API_KEY="sk-your-actual-key"
export ZILLIZ_HOST="https://your-host.zillizcloud.com"
export ZILLIZ_TOKEN="your-actual-token"
```

### Step 2: Create Secrets & Grant Permissions

```bash
# Navigate to project directory
cd poc

# Get project number for IAM bindings
PROJECT_NUM=$(gcloud projects describe angelic-edition-325910 --format="value(projectNumber)")

# Create secrets in Secret Manager
echo -n "$OPENAI_KEY" | gcloud secrets create openai-api-key --data-file=-
echo -n "$ZILLIZ_HOST" | gcloud secrets create zilliz-host --data-file=-
echo -n "$ZILLIZ_TOKEN" | gcloud secrets create zilliz-token --data-file=-

# Grant Cloud Run service account access to secrets
for secret in openai-api-key zilliz-host zilliz-token; do
    gcloud secrets add-iam-policy-binding $secret \
        --member="serviceAccount:${PROJECT_NUM}-compute@developer.gserviceaccount.com" \
        --role="roles/secretmanager.secretAccessor"
done
```

### Step 3: Deploy to Cloud Run

```bash
# Optional: Choose your region
export GCP_REGION="us-central1"  # Default (cheapest)
# OR
export GCP_REGION="asia-northeast3"  # Seoul (faster for South Korea)

# Run deployment script
./deploy.sh
```

**That's it!** The script will:

- Build your Docker image
- Push it to Google Container Registry
- Deploy to Cloud Run
- Provide you with a public URL

### Get Your Service URL

```bash
gcloud run services describe ai-librarian \
    --region us-central1 \
    --format 'value(status.url)'
```

---

## 📖 Detailed Deployment Steps

### Understanding the Process

The deployment consists of these phases:

1. **Secret Creation**: Store API keys securely in Secret Manager
2. **IAM Configuration**: Grant Cloud Run access to secrets
3. **Image Build**: Package your application into a Docker container
4. **Image Push**: Upload to Google Container Registry
5. **Service Deploy**: Create Cloud Run service with secrets

### Manual Step-by-Step (Alternative to Quick Deployment)

If you prefer manual control:

#### 1. Create Secrets

```bash
# Set project
gcloud config set project angelic-edition-325910

# Get project number
PROJECT_NUM=$(gcloud projects describe angelic-edition-325910 --format="value(projectNumber)")
echo "Project Number: $PROJECT_NUM"

# Create each secret
echo -n "sk-your-openai-key" | gcloud secrets create openai-api-key --data-file=- --project=angelic-edition-325910
echo -n "https://xxx.zillizcloud.com" | gcloud secrets create zilliz-host --data-file=- --project=angelic-edition-325910
echo -n "your-zilliz-token" | gcloud secrets create zilliz-token --data-file=- --project=angelic-edition-325910
```

#### 2. Grant IAM Permissions

```bash
# Grant access for each secret
gcloud secrets add-iam-policy-binding openai-api-key \
    --member="serviceAccount:${PROJECT_NUM}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" \
    --project=angelic-edition-325910

gcloud secrets add-iam-policy-binding zilliz-host \
    --member="serviceAccount:${PROJECT_NUM}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" \
    --project=angelic-edition-325910

gcloud secrets add-iam-policy-binding zilliz-token \
    --member="serviceAccount:${PROJECT_NUM}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" \
    --project=angelic-edition-325910
```

#### 3. Build Docker Image

```bash
cd /Users/iyeonjae/.cursor/worktrees/ai-librarian/CZgjF/poc

# Build image
docker build -t gcr.io/angelic-edition-325910/ai-librarian .
```

#### 4. Push to Container Registry

```bash
# Push image
docker push gcr.io/angelic-edition-325910/ai-librarian
```

#### 5. Deploy to Cloud Run

```bash
gcloud run deploy ai-librarian \
    --image gcr.io/angelic-edition-325910/ai-librarian \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --port 8080 \
    --memory 2Gi \
    --cpu 2 \
    --timeout 300 \
    --max-instances 10 \
    --set-env-vars "ENVIRONMENT=production" \
    --update-secrets "OPENAI_API_KEY=openai-api-key:latest,ZILLIZ_HOST=zilliz-host:latest,ZILLIZ_TOKEN=zilliz-token:latest"
```

---

## 📋 Testing Your Deployment

After deployment completes:

### 1. Get Your Service URL

```bash
gcloud run services describe ai-librarian \
    --region us-central1 \
    --format 'value(status.url)'
```

Output example: `https://ai-librarian-xxxxx-uc.a.run.app`

### 2. Open in Browser

Navigate to the URL in your web browser.

### 3. Add Sample Data

1. Go to "📚 데이터 관리" (Data Management) tab
2. Click "🔄 샘플 문서 추가" (Add Sample Documents)
3. Wait for confirmation

### 4. Ask a Question

1. Go to "🚀 질의응답" (Q&A) tab
2. Try asking: "What is LangChain?"
3. You should get a comprehensive answer

### 5. Verify System Health

Check the system is working properly:

- View answer sources (Vector DB, Web Search, LLM Direct)
- Check confidence scores
- View processing times

---

## ⚙️ Configuration Options

### Regional Selection

Choose based on your priorities:

| Region            | Location     | Latency from Korea | Cost            | Best For    |
| ----------------- | ------------ | ------------------ | --------------- | ----------- |
| `us-central1`     | Iowa, USA    | ~200ms             | Lowest (Tier 1) | **Budget**  |
| `asia-northeast3` | Seoul, Korea | ~10ms              | Higher (Tier 2) | **Speed**   |
| `asia-northeast1` | Tokyo, Japan | ~50ms              | Medium          | **Balance** |

#### To Change Region

Set before deploying:

```bash
export GCP_REGION="asia-northeast3"  # For Seoul
```

For study group projects, `us-central1` is recommended unless low latency is critical.

### Resource Configuration

Default configuration (suitable for most cases):

- **Memory**: 2Gi
- **CPU**: 2 vCPUs
- **Timeout**: 300s (5 minutes)
- **Max Instances**: 10

#### To Adjust Resources

Update service after deployment:

```bash
# Increase memory
gcloud run services update ai-librarian \
    --region us-central1 \
    --memory 4Gi

# Increase CPU
gcloud run services update ai-librarian \
    --region us-central1 \
    --cpu 4

# Increase timeout
gcloud run services update ai-librarian \
    --region us-central1 \
    --timeout 600
```

### Environment Variables

You can set additional environment variables:

```bash
gcloud run services update ai-librarian \
    --region us-central1 \
    --set-env-vars "LOG_LEVEL=DEBUG,MAX_RETRIES=5"
```

---

## 🐛 Troubleshooting

### Common Issues

#### Issue 1: "Secrets not found" error

**Symptoms**: deploy.sh exits with message about missing secrets

**Solution**: Create secrets first (see Step 2 in Quick Deployment)

**Verify secrets exist**:

```bash
gcloud secrets list --project=angelic-edition-325910
```

#### Issue 2: "Permission denied" errors

**Symptoms**: IAM policy binding fails

**Solution**: Ensure you have necessary roles:

```bash
gcloud projects add-iam-policy-binding angelic-edition-325910 \
    --member="user:leeyj0304@gmail.com" \
    --role="roles/secretmanager.admin"
```

#### Issue 3: Service crashes on startup

**Symptoms**: Service deploys but shows errors in logs

**Solution**: Check logs for specific error:

```bash
gcloud run services logs read ai-librarian --region us-central1 --limit 50
```

Common causes:

- Invalid API keys (check secret values)
- Zilliz connection issues (verify host and token)
- Missing environment variables

#### Issue 4: "Out of memory" errors

**Symptoms**: Service times out or crashes under load

**Solution**: Increase memory allocation:

```bash
gcloud run services update ai-librarian \
    --region us-central1 \
    --memory 4Gi
```

#### Issue 5: Slow response times

**Possible causes**:

- High latency to vector DB (consider region change)
- OpenAI API rate limits (check usage)
- Insufficient resources (increase CPU/memory)

**Solutions**:

```bash
# Deploy closer to your location
export GCP_REGION="asia-northeast3"
./deploy.sh

# Increase resources
gcloud run services update ai-librarian \
    --region asia-northeast3 \
    --memory 4Gi \
    --cpu 4
```

### Useful Debugging Commands

```bash
# View real-time logs
gcloud run services logs read ai-librarian --region us-central1 --follow

# Check service status
gcloud run services describe ai-librarian --region us-central1

# Check environment variables
gcloud run services describe ai-librarian \
    --region us-central1 \
    --format="value(spec.template.spec.containers[0].env)"

# List all Cloud Run services
gcloud run services list

# Check Docker images
docker images | grep ai-librarian

# Verify authentication
gcloud auth list
```

---

## 💰 Cost Management

### Estimated Monthly Costs

For moderate usage (study group with ~1000 requests/day):

| Component          | Cost (us-central1) | Cost (asia-northeast3) |
| ------------------ | ------------------ | ---------------------- |
| Cloud Run          | $10-20/month       | $12-25/month           |
| OpenAI API         | $5-20/month        | $5-20/month            |
| Container Registry | <$1/month          | <$1/month              |
| **Total**          | **$15-40/month**   | **$17-45/month**       |

_Note: Zilliz Cloud is billed separately - check with your team._

### Cost Optimization Tips

#### 1. Set Resource Limits

```bash
# Limit max instances to control costs
gcloud run services update ai-librarian \
    --region us-central1 \
    --max-instances 5

# Use minimum resources that work
gcloud run services update ai-librarian \
    --region us-central1 \
    --memory 1Gi \
    --cpu 1
```

#### 2. Monitor Usage

```bash
# Check Cloud Run metrics in console
open "https://console.cloud.google.com/run/detail/us-central1/ai-librarian/metrics?project=angelic-edition-325910"
```

#### 3. Set Billing Alerts

1. Go to: https://console.cloud.google.com/billing
2. Select your billing account
3. Click "Budgets & alerts"
4. Create a budget (e.g., $50/month)
5. Set alert threshold (e.g., 80%)

#### 4. Use Cheaper Region

`us-central1` is ~10-15% cheaper than Seoul region for similar performance.

#### 5. Optimize OpenAI Usage

- Use caching for repeated queries
- Set lower max_tokens if possible
- Monitor usage: https://platform.openai.com/usage

### Cost Monitoring Commands

```bash
# View Cloud Run billing
gcloud billing accounts list

# Check project billing info
gcloud billing projects describe angelic-edition-325910
```

---

## 💡 Useful Commands Reference

### Service Management

```bash
# Get service URL
gcloud run services describe ai-librarian --region us-central1 --format 'value(status.url)'

# View service details
gcloud run services describe ai-librarian --region us-central1

# List all services
gcloud run services list

# Delete service
gcloud run services delete ai-librarian --region us-central1
```

### Logs & Monitoring

```bash
# Real-time logs
gcloud run services logs read ai-librarian --region us-central1 --follow

# Recent logs (last 50 lines)
gcloud run services logs read ai-librarian --region us-central1 --limit 50

# Filter logs by severity
gcloud run services logs read ai-librarian --region us-central1 --log-filter="severity>=ERROR"
```

### Secrets Management

```bash
# List secrets
gcloud secrets list --project=angelic-edition-325910

# View secret metadata
gcloud secrets describe openai-api-key --project=angelic-edition-325910

# Update secret value
echo -n "new-value" | gcloud secrets versions add openai-api-key --data-file=-

# Delete secret
gcloud secrets delete openai-api-key --project=angelic-edition-325910
```

### Docker Operations

```bash
# List local images
docker images | grep ai-librarian

# Remove local image
docker rmi gcr.io/angelic-edition-325910/ai-librarian

# Rebuild image
docker build -t gcr.io/angelic-edition-325910/ai-librarian .

# Test image locally
docker run -p 8080:8080 \
    -e OPENAI_API_KEY="sk-test" \
    -e ZILLIZ_HOST="https://test.com" \
    -e ZILLIZ_TOKEN="test" \
    gcr.io/angelic-edition-325910/ai-librarian
```

---

## 🔐 Security Best Practices

### Current Security Configuration

✅ **API keys stored in Secret Manager** (not in code or environment)
✅ **Secrets only accessible to Cloud Run service account**
✅ **HTTPS enabled by default**
✅ **Service currently public** (can add authentication later)

### Adding Authentication (Optional)

To require authentication:

```bash
gcloud run services update ai-librarian \
    --region us-central1 \
    --no-allow-unauthenticated
```

Then users must authenticate:

```bash
# Generate auth token
gcloud auth print-identity-token

# Access service with token
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
    https://ai-librarian-xxxxx-uc.a.run.app
```

### Rotating Secrets

Update secrets regularly:

```bash
# Create new version
echo -n "new-api-key" | gcloud secrets versions add openai-api-key --data-file=-

# Redeploy to use new version (happens automatically)
```

---

## 📞 What to Tell Your Team

Message template for your study group:

> Hey team! 👋
>
> I've set up the deployment infrastructure for our AI Librarian project. We're 90% ready to deploy!
>
> **I need three things to complete the deployment:**
>
> 1. **OpenAI API key** (starts with `sk-`)
> 2. **Zilliz host URL** (format: `https://xxx.zillizcloud.com`)
> 3. **Zilliz token** (API key from dashboard)
>
> Once I have these, I can deploy in about 5 minutes and share the live URL!
>
> Our app will be hosted on Google Cloud Run with:
>
> - ✅ Auto-scaling
> - ✅ HTTPS by default
> - ✅ Estimated cost: $15-40/month
>
> Let me know when you have the keys! 🚀

---

## 📚 Additional Resources

### Official Documentation

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Secret Manager Documentation](https://cloud.google.com/secret-manager/docs)
- [Container Registry Documentation](https://cloud.google.com/container-registry/docs)

### Project Documentation

- `README.md` - Project overview and architecture
- `PROJECT_CONTEXT.md` - Development context and history
- `deploy.sh` - Automated deployment script
- `Dockerfile` - Container definition

### Helpful Links

- [Cloud Run Pricing Calculator](https://cloud.google.com/products/calculator)
- [OpenAI API Pricing](https://openai.com/pricing)
- [GCP Console](https://console.cloud.google.com)

---

## ✅ Deployment Checklist

Use this checklist when you're ready to deploy:

### Pre-Deployment

- [ ] Received OpenAI API key from team
- [ ] Received Zilliz host URL from team
- [ ] Received Zilliz token from team
- [ ] Verified gcloud authentication
- [ ] Verified billing is enabled

### Deployment Steps

- [ ] Set environment variables with API keys
- [ ] Created secrets in Secret Manager
- [ ] Granted IAM permissions to secrets
- [ ] Ran deploy.sh script successfully
- [ ] Retrieved service URL
- [ ] Tested service in browser

### Post-Deployment

- [ ] Added sample data in web interface
- [ ] Asked test question and verified response
- [ ] Shared URL with team
- [ ] Set up billing alerts
- [ ] Documented service URL for team

---

**You're ready to deploy as soon as you get those API keys! 🎉**

For questions or issues, check the [Troubleshooting](#troubleshooting) section or review the logs.
