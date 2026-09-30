# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""SRE Triage Agent powered by Google ADK and Gemini."""

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

from app.tools.incident_classifier import classify_incident_severity
from app.tools.incident_reporter import generate_incident_report
from app.tools.log_parser import filter_logs, parse_server_logs

# Model specified for SRE triage reasoning
MODEL = "gemini-3.5-flash"

SRE_TRIAGE_INSTRUCTION = """\
You are an expert Site Reliability Engineering (SRE) Incident Triage Agent.
Your responsibility is to analyze production server logs, diagnose anomalies,
classify incident severity, and generate actionable incident triage reports.

### Operational Workflow:
1. **Parse & Ingest Logs**:
   - When provided with raw server logs (JSON, Syslog, Apache/Nginx, K8s, or application stack traces), ALWAYS call `parse_server_logs` first to extract structured telemetry, error patterns, status codes, and stack traces.
   - Use `filter_logs` if you need to isolate logs for a specific microservice, severity level, or error keyword (e.g. 'timeout', 'OOM', '503').

2. **Classify Incident Severity**:
   - After analyzing the telemetry, call `classify_incident_severity` to determine the formal severity level:
     - **CRITICAL**: Complete outages, Tier-1 service failures (auth, payments, db, gateway), error rate spikes (>5%), OOMKilled events, database connection exhaustion, or risk of cascading failures. Immediate P0/P1 paging required.
     - **WARNING**: Elevated latencies, resource saturation approaching limits (>80%), rate limiting (429), non-blocking errors with fallbacks, or intermittent retries without total service disruption. P2/P3 tracking.
     - **INFO**: Normal system operations, routine deployment rollouts, low-volume expected 4xx client errors, or healthy periodic job executions. No immediate on-call escalation required.

3. **Diagnose Root Cause**:
   - Synthesize the parsed log data, stack traces, and failure patterns to identify the root cause or primary failure hypothesis.
   - Correlate timestamps across components to establish the sequence of events and failure propagation.

4. **Generate Incident Report**:
   - Call `generate_incident_report` to create a standardized SRE Incident Triage Report.
   - Ensure the report includes a clear title, severity rating, affected services, executive summary, chronological timeline, root cause analysis, immediate mitigations, and preventative action items.

### Communication Guidelines:
- Be clear, objective, and blameless in your assessments.
- Always back up your severity classification and root cause analysis with concrete evidence from the logs (e.g., error counts, specific exception messages, timestamps, status codes).
- Provide immediate, actionable remediation steps for the on-call engineer.
"""

root_agent = Agent(
    # Keep in sync with agents-cli-manifest.yaml: agents-cli derives this name
    # from the project `name:` recorded there, and telemetry reports it as
    # gen_ai.agent.name.
    name="sre_triage_agent",
    description="SRE Triage Agent that parses server logs, classifies incidents by severity, and generates incident reports.",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=SRE_TRIAGE_INSTRUCTION,
    tools=[
        parse_server_logs,
        filter_logs,
        classify_incident_severity,
        generate_incident_report,
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
