
import os
import subprocess
import sys

try:
    from dotenv import load_dotenv
except ImportError:
    print("❌ Error: 'python-dotenv' is not installed.")
    print("👉 Please run: pip install python-dotenv")
    print("   Or run inside your environment: poetry run python setup_secrets.py")
    sys.exit(1)


def run_command(command, input_text=None):
    """Run a shell command and return output."""
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE if input_text else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True
        )
        stdout, stderr = process.communicate(input=input_text)
        return process.returncode, stdout, stderr
    except Exception as e:
        return 1, "", str(e)

def setup_secrets():
    """
    Read .env and upload secrets to Google Cloud Secret Manager.
    
    This script:
    1. Parses the local .env file (using python-dotenv for robustness).
    2. Uploads secrets (OPENAI_API_KEY, ZILLIZ_HOST, ZILLIZ_TOKEN) to Google Secret Manager.
    3. Grants 'Secret Accessor' permissions to the Compute Engine default service account
       so that Cloud Run can access these secrets during runtime.
    """
    print("🚀 Starting Secret Setup (Python Version)...")
    
    # Load environment variables from .env file
    if not os.path.exists(".env"):
        print("❌ .env file not found! Please create one from env_example.txt first.")
        return
    
    load_dotenv(override=True)
    
    project_id = os.getenv("GCP_PROJECT_ID", "angelic-edition-325910")
    print(f"📋 Project ID: {project_id}")
    
    # Mapping of Google Secret Name -> Env Var Name
    secrets = {
        "openai-api-key": "OPENAI_API_KEY",
        "zilliz-host": "ZILLIZ_HOST",
        "zilliz-token": "ZILLIZ_TOKEN"
    }
    
    for secret_name, env_var in secrets.items():
        value = os.getenv(env_var)
        if not value:
            print(f"⚠️  Value for {env_var} is empty or missing in .env")
            continue
            
        print(f"Processing {secret_name}...")
        
        # Check if secret exists
        check_cmd = f"gcloud secrets describe {secret_name} --project={project_id}"
        code, _, _ = run_command(check_cmd)
        
        if code != 0:
            # Create new secret
            print(f"   Creating new secret: {secret_name}")
            create_cmd = f"gcloud secrets create {secret_name} --data-file=- --project={project_id}"
            code, out, err = run_command(create_cmd, input_text=value)
        else:
            # Add new version
            print(f"   Updating existing secret: {secret_name}")
            update_cmd = f"gcloud secrets versions add {secret_name} --data-file=- --project={project_id}"
            code, out, err = run_command(update_cmd, input_text=value)
            
        if code == 0:
            print(f"   ✅ Success: {secret_name}")
        else:
            print(f"   ❌ Failed to set {secret_name}: {err.strip()}")

    # Grant permissions
    print("\n🔐 Granting IAM permissions...")
    
    # Get project number
    code, project_num, err = run_command(f"gcloud projects describe {project_id} --format='value(projectNumber)'")
    if code != 0:
        print(f"❌ Failed to get project number: {err}")
        return
        
    project_num = project_num.strip()
    service_account = f"{project_num}-compute@developer.gserviceaccount.com"
    print(f"   Service Account: {service_account}")
    
    for secret_name in secrets.keys():
        cmd = (
            f"gcloud secrets add-iam-policy-binding {secret_name} "
            f"--member='serviceAccount:{service_account}' "
            f"--role='roles/secretmanager.secretAccessor' "
            f"--project={project_id}"
        )
        code, out, err = run_command(cmd)
        if code == 0:
            print(f"   ✅ Granted access: {secret_name}")
        else:
            print(f"   ⚠️  Failed to grant access (might already exist or secret missing): {secret_name}")

    print("\n✅ Done!")

if __name__ == "__main__":
    setup_secrets()
