# Google Cloud Platform Setup for AI Librarian CI/CD

This guide details the steps to configure Google Cloud resources required for the GitHub Actions CI/CD pipeline.

## Prerequisites

- Google Cloud Project: `angelic-edition-325910` (Target Project)
- `gcloud` CLI installed and authenticated
- Owner permissions on the project

## 1. Enable APIs

```bash
gcloud services enable \
    iamcredentials.googleapis.com \
    containerregistry.googleapis.com \
    run.googleapis.com \
    secretmanager.googleapis.com
```

## 2. Container Registry (gcr.io)

We are using the legacy Container Registry (`gcr.io`) to match the existing deployment structure. Ensure it is enabled for your project.

## 3. Workload Identity Federation (WIF)

Allow GitHub Actions to impersonate a Service Account without using long-lived keys.

### Create Identity Pool & Provider

(If not already created)

```bash
gcloud iam workload-identity-pools create "github-pool" \
  --project="angelic-edition-325910" \
  --location="global" \
  --display-name="GitHub Actions Pool"
```

```bash
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --project="angelic-edition-325910" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub Actions Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --attribute-condition="assertion.repository_owner == 'donggyun112' && assertion.repository == 'donggyun112/ai-librarian'" \
  --issuer-uri="https://token.actions.githubusercontent.com"
  --issuer-uri="https://token.actions.githubusercontent.com"
```

### Troubleshooting: `INVALID_ARGUMENT` Error

If you see `The attribute condition must reference one of the provider's claims`, it is because Google now enforces security conditions for GitHub. The command above **includes the fix** (`--attribute-condition` and `attribute.repository_owner` mapping). Ensure you use the exact command above.

```bash
ERROR: (gcloud.iam.workload-identity-pools.providers.create-oidc) INVALID_ARGUMENT: The attribute condition must reference one of the provider's claims. For more information, see https://cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines#conditions
```

### Verify Provider

Run the following command to verify the provider:

> ```bash
> gcloud iam workload-identity-pools providers describe "github-provider" \
>   --project="angelic-edition-325910" \
>   --location="global" \
>   --workload-identity-pool="github-pool"
> ```

## 4. Create Service Account

```bash
gcloud iam service-accounts create "github-ci-sa" \
  --display-name="GitHub Actions Service Account"
```

### Grant Permissions

Grant necessary roles to the Service Account.

```bash
SA_EMAIL="github-ci-sa@angelic-edition-325910.iam.gserviceaccount.com"

# Allow SA to push to Container Registry (Storage Admin)
gcloud projects add-iam-policy-binding "angelic-edition-325910" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.admin"

# Allow SA to deploy to Cloud Run
gcloud projects add-iam-policy-binding "angelic-edition-325910" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.admin"

# Allow SA to act as itself
gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/iam.serviceAccountUser"
# Allow SA to access Secret Manager
gcloud projects add-iam-policy-binding "angelic-edition-325910" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor"
```

## 5. Secret Manager

Create the following secrets in Google Cloud Secret Manager if they don't exist:

- `openai-api-key`
- `supabase-url`
- `supabase-service-role-key`
- `postgres-password`

## 6. GitHub Secrets

Add the following secrets to your GitHub Repository:

| Secret Name        | Value                                                         |
| ------------------ | ------------------------------------------------------------- |
| `GCP_PROJECT_ID`   | `angelic-edition-325910`                                      |
| `GCP_SA_EMAIL`     | `github-ci-sa@angelic-edition-325910.iam.gserviceaccount.com` |
| `GCP_WIF_PROVIDER` | Full provider name from Step 3                                |

### 7. How to Retrieve these Values

Run these commands to get the exact values for GitHub Secrets:

**Get GCP_WIF_PROVIDER:**

```bash
gcloud iam workload-identity-pools providers describe "github-provider" \
  --project="angelic-edition-325910" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --format="value(name)"
```

**Get GCP_SA_EMAIL:**

```bash
echo "github-ci-sa@angelic-edition-325910.iam.gserviceaccount.com"
```
