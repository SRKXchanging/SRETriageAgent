# SRE Triage Agent - Commands Reference Guide

This document records the exact commands executed across the end-to-end lifecycle of the SRE Triage Agent: initial scaffolding, dependency installation, local testing, enhancing for Vertex AI Agent Runtime, project binding, cloud deployment, and operations.

---

## 1. Environment & CLI Verification

Verify that `agents-cli`, `uv`, and Python are properly installed in the environment:

```bash
# Check agents-cli version
agents-cli --version

# Check uv package manager version
uv --version

# Check Python version
python3 --version
```

---

## 2. Initial Project Scaffolding

Scaffold the base Google ADK agent project structure using `agents-cli create` in prototype mode:

```bash
# Scaffold the project template
agents-cli create sre-triage-agent --prototype -y -s -o /tmp/sre_init

# Move scaffolded files to workspace root
cp -R /tmp/sre_init/sre-triage-agent/. /Users/user/Documents/Suraj/antigravityide/SRETriageAgent/
rm -rf /tmp/sre_init

# Initialize git repository
git init
git config user.name "SRE Bot"
git config user.email "sre-bot@example.com"
```

*What was generated:*
- `agents-cli-manifest.yaml`: Core project manifest
- `pyproject.toml`: Dependency definitions with `google-adk`
- `app/agent.py`: Agent definition & system instruction
- `app/fast_api_app.py`: FastAPI backend server with A2A protocol support
- `app/app_utils/`: Session and telemetry helper services

---

## 3. Install Initial Dependencies

Install all project dependencies into a local virtual environment (`.venv`) using `uv` via `agents-cli`:

```bash
agents-cli install
```

---

## 4. Local Development Server & Interactive Testing

Launch the local interactive ADK Playground UI to test the agent locally before deployment:

```bash
# Start playground on port 8080
agents-cli playground --port 8080

# Verify the local server is running
curl -s -L http://127.0.0.1:8080/ | head -n 20
```

*Access URL:* `http://127.0.0.1:8080`

---

## 5. Google Cloud Project Binding & Prerequisites

Configure the active Google Cloud project and verify required Vertex AI APIs are enabled:

```bash
# Set active GCP project to projectone-509923
gcloud config set project projectone-509923

# Confirm active account and project
gcloud config get-value project
gcloud auth list

# Verify Agent Platform / Vertex AI API is enabled
gcloud services list --enabled --filter="name:aiplatform.googleapis.com" --project=projectone-509923
```

---

## 6. Enhance Scaffold for Vertex AI Agent Runtime (`agent_runtime`)

Upgrade the project from prototype mode to support **Vertex AI Agent Runtime (Reasoning Engine)** without overwriting custom agent code:

```bash
# Enhance project configuration for agent_runtime target
agents-cli scaffold enhance --deployment-target agent_runtime --region asia-southeast1 -y -s
```

*What this command added:*
- `app/app_utils/reasoning_engine_adapter.py`: Adapter enabling Vertex AI Console Playground and Gemini Enterprise integration
- `deployment/terraform/single-project/`: Terraform infrastructure templates
- `deployment_metadata.json`: Deployment state tracking
- Added `google-cloud-aiplatform[agent-engines]` to `pyproject.toml`
- Updated `agents-cli-manifest.yaml` to `deployment_target: agent_runtime`

---

## 7. Sync Updated Dependencies for Agent Engine

Install the newly added Agent Engine packages (`google-cloud-aiplatform[agent-engines]`, `protobuf`, etc.):

```bash
agents-cli install
```

---

## 8. Deploy to Vertex AI Agent Runtime

Deploy the containerized agent to **Vertex AI Agent Engine** in Google Cloud:

```bash
agents-cli deploy --project projectone-509923 --region asia-southeast1
```

*Deployment Specifications:*
- **Project:** `projectone-509923` (Number: `736321734520`)
- **Region:** `asia-southeast1` (Singapore)
- **Runtime ID:** `projects/736321734520/locations/asia-southeast1/reasoningEngines/8504951139265937408`
- **Service Account:** `service-736321734520@gcp-sa-aiplatform-re.iam.gserviceaccount.com`
- **Min Instances:** `0` (Serverless scale-to-zero enabled)
- **Max Instances:** `10`
- **Resources:** `1 vCPU`, `4GiB RAM`
- **Model:** `gemini-3.5-flash`

---

## 9. Deployment Verification & Inspection

Inspect project metadata and verify the deployed remote runtime:

```bash
# View current project configuration and deployment target
agents-cli info

# Check deployment status
agents-cli deploy --status

# Inspect deployed Reasoning Engine using Python SDK
python3 -c "
import vertexai
from vertexai.preview import reasoning_engines
vertexai.init(project='projectone-509923', location='asia-southeast1')
engine = reasoning_engines.ReasoningEngine('projects/736321734520/locations/asia-southeast1/reasoningEngines/8504951139265937408')
print('Engine resource:', engine.resource_name)
print('Display name:', engine.display_name)
"
```

---

## 10. Operational & Maintenance Commands

### Redeploy After Code Changes
When modifying `app/agent.py` or `app/tools/`:
```bash
# Redeploys directly using settings saved in agents-cli-manifest.yaml
agents-cli deploy
```

### Deploy with Explicit Min Instances
```bash
# Scale to zero when idle (default, $0 idle cost):
agents-cli deploy --min-instances 0

# Keep 1 warm instance (avoids cold start latency):
agents-cli deploy --min-instances 1
```

### Delete / Tear Down the Deployed Agent
If you want to permanently delete the deployed Reasoning Engine instance:
```bash
gcloud ai reasoning-engines delete 8504951139265937408 \
  --region=asia-southeast1 \
  --project=projectone-509923 \
  --quiet
```
