# SRE Triage Agent

An automated Site Reliability Engineering (SRE) Incident Triage Agent built with **Google Agent Development Kit (ADK)** and managed with **Google Agents CLI (`agents-cli`)**, powered by **`gemini-3.5-flash`**.

## Key Capabilities

- 🔍 **Server Log Parsing (`parse_server_logs`)**:
  - Ingests multiline raw server logs in diverse formats (JSON logs, Syslog, Apache/Nginx web server access logs, Kubernetes/Docker container logs).
  - Automatically isolates and extracts Python, Java, Go, and Node.js exception stack traces.
  - Aggregates telemetry: log volume, severity distribution, HTTP status codes, impacted microservices, and error frequency clustering.
- 🎯 **Log Filtering (`filter_logs`)**:
  - Quickly filters large log streams by severity level (`CRITICAL`, `ERROR`, `WARNING`, `INFO`), specific microservice, or error keywords (e.g., `timeout`, `503`, `OOMKilled`).
- ⚖️ **Incident Severity Classification (`classify_incident_severity`)**:
  - Evaluates operational metrics, blast radius, service criticality (Tier-1 vs Tier-2/3), error rates, and failure patterns.
  - Classifies incidents into standard severity tiers:
    - **`CRITICAL`** (P0/P1): Outages, core service failures, OOM kills, database connection pool exhaustion, error rate spikes (>5%), cascade risks. Immediate on-call escalation.
    - **`WARNING`** (P2/P3): Elevated latencies, resource saturation approaching thresholds (>80%), rate limiting (429), non-blocking errors with fallbacks.
    - **`INFO`**: Routine deployments, normal operations, expected low-frequency 4xx client errors, healthy status checks.
- 📋 **Incident Report Generation (`generate_incident_report`)**:
  - Generates standardized SRE Incident Triage Reports conforming to Google SRE post-mortem and incident response practices.
  - Includes executive summaries, severity badges, blast radius assessment, chronological timelines, root cause analysis (RCA), immediate mitigations, and preventative action items.

---

## Project Structure

```
SRETriageAgent/
├── app/
│   ├── __init__.py
│   ├── agent.py               # Main SRE Triage Agent definition and instructions
│   ├── fast_api_app.py        # FastAPI Backend server with A2A support
│   ├── app_utils/             # Session, telemetry, and A2A service helpers
│   └── tools/                 # Modular SRE Triage tools
│       ├── __init__.py
│       ├── log_parser.py      # Log ingestion, regex/JSON parser, stack trace extractor
│       ├── incident_classifier.py # SRE classification engine (CRITICAL / WARNING / INFO)
│       └── incident_reporter.py   # Markdown report & post-mortem generator
├── tests/                     # Unit, integration, and eval test suites
├── agents-cli-manifest.yaml   # Agents CLI project manifest
├── GEMINI.md                  # Development guidance and workflow rules
├── pyproject.toml             # Project dependencies (ADK, FastAPI, etc.)
└── README.md
```

---

## Model Configuration

- **Model**: `gemini-3.5-flash`
- **Framework**: `google-adk` (Agent Development Kit v2.8+)
- **Agent Name**: `sre_triage_agent`

---

## Quick Start

### 1. Install Dependencies
Dependencies are managed using `uv` via `agents-cli`:

```bash
agents-cli install
```

### 2. Configure Environment
Set your Google Cloud or Gemini API credentials in `.env`:

```bash
# Example for Vertex AI / Google Cloud
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1

# Or with AI Studio API Key:
# GEMINI_API_KEY=your_api_key_here
```

### 3. Launch Local Playground
Start the interactive local agent playground:

```bash
agents-cli playground
```

Or run the FastAPI server directly:

```bash
uv run python -m app.fast_api_app
```
