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

"""Incident severity classification tool for SRE triage.

Classifies incidents into CRITICAL, WARNING, or INFO tiers based on error rates,
blast radius, service tier, cascade risk, and failure signals.
"""

import json
from typing import Any

# Keywords that indicate critical failure modes
CRITICAL_FAILURE_KEYWORDS = {
    "oomkilled",
    "out of memory",
    "deadlock",
    "connection refused",
    "connection pool exhausted",
    "database unavailable",
    "data loss",
    "circuit breaker open",
    "segmentation fault",
    "panic:",
    "fatal",
    "cascading failure",
    "503 service unavailable",
    "504 gateway timeout",
    "unauthorized access breach",
}

# Core/Tier-1 service indicators
TIER_1_SERVICES = {
    "auth",
    "authentication",
    "authorization",
    "payment",
    "payments",
    "checkout",
    "database",
    "db",
    "postgres",
    "mysql",
    "redis",
    "api-gateway",
    "ingress",
    "orders",
    "billing",
}


def classify_incident_severity(
    service_name: str,
    error_summary: str,
    error_count: int,
    total_requests: int = 0,
    is_service_down: bool = False,
    cascade_risk: bool = False,
    is_tier_1_service: bool | None = None,
    detected_error_types: list[str] | None = None,
) -> str:
    """Classifies an incident into CRITICAL, WARNING, or INFO severity with SRE triage guidance.

    Evaluates production operational metrics, service criticality, blast radius,
    and failure signatures to determine severity, escalation urgency, and response SLA.

    Args:
        service_name: Name of the impacted microservice or component (e.g., 'payment-service').
        error_summary: Summary of the error condition or symptoms observed in logs.
        error_count: Total number of error occurrences observed.
        total_requests: Total request volume during the observed period (0 if unknown).
        is_service_down: Whether the service is completely unreachable or dead.
        cascade_risk: Whether upstream/downstream services are also failing as a result.
        is_tier_1_service: Whether this is a Tier-0/1 mission-critical service (optional, inferred if None).
        detected_error_types: List of specific error classes or codes (e.g., ['500', 'ConnectionRefusedError']).

    Returns:
        A JSON string containing:
            - severity: 'CRITICAL', 'WARNING', or 'INFO'
            - escalation_tier: 'P0', 'P1', 'P2', 'P3', or 'None'
            - sla_target: Recommended initial response SLA
            - blast_radius: 'EXTENSIVE', 'MODERATE', 'CONTAINED', or 'MINIMAL'
            - justification: Detailed technical explanation for this severity classification
            - recommended_immediate_actions: Actionable next steps for SRE on-call engineers
    """
    error_summary_lower = error_summary.lower()
    service_lower = service_name.lower()
    error_types = [t.lower() for t in (detected_error_types or [])]

    # Infer Tier-1 criticality if not explicitly provided
    if is_tier_1_service is None:
        is_tier_1_service = any(t1 in service_lower for t1 in TIER_1_SERVICES)

    # Calculate error rate if request volume is provided
    error_rate_pct = 0.0
    if total_requests > 0:
        error_rate_pct = round((error_count / total_requests) * 100, 2)

    has_critical_signature = any(
        kw in error_summary_lower for kw in CRITICAL_FAILURE_KEYWORDS
    ) or any(
        any(kw in err for kw in CRITICAL_FAILURE_KEYWORDS) for err in error_types
    )

    # --- Classification Logic ---
    severity: str
    escalation_tier: str
    sla_target: str
    blast_radius: str
    reasons: list[str] = []
    actions: list[str] = []

    # 1. CRITICAL Criteria
    if (
        is_service_down
        or cascade_risk
        or (is_tier_1_service and (error_rate_pct >= 5.0 or error_count >= 50 or has_critical_signature))
        or error_rate_pct >= 10.0
        or (has_critical_signature and error_count >= 10)
    ):
        severity = "CRITICAL"
        blast_radius = "EXTENSIVE" if (cascade_risk or is_tier_1_service) else "MODERATE"

        if is_service_down or (is_tier_1_service and cascade_risk):
            escalation_tier = "P0"
            sla_target = "Immediate (< 15 minutes), Page On-Call Lead & Incident Commander"
        else:
            escalation_tier = "P1"
            sla_target = "< 30 minutes, Page Service On-Call Engineer"

        if is_service_down:
            reasons.append(f"Service '{service_name}' is reported down/unreachable.")
        if cascade_risk:
            reasons.append("High probability of cascading failure impacting dependent microservices.")
        if is_tier_1_service:
            reasons.append(f"Impacts Tier-1 core system component '{service_name}'.")
        if has_critical_signature:
            reasons.append("Fatal failure signature detected (e.g. OOM, deadlock, connection pool depletion, or 503).")
        if error_rate_pct >= 5.0:
            reasons.append(f"Elevated error rate of {error_rate_pct}% exceeds critical threshold (5%).")
        elif error_count >= 50:
            reasons.append(f"High error volume ({error_count} events) detected.")

        actions = [
            f"Acknowledge {escalation_tier} incident and spin up dedicated incident bridge.",
            f"Inspect recent canary/production deployments or config updates for '{service_name}'.",
            "Consider traffic shedding, circuit breaking, or rolling back recent release.",
            "Verify health of downstream databases, connection pools, and caching layers.",
            "Post public/internal status update to stakeholders.",
        ]

    # 2. WARNING Criteria
    elif (
        error_count > 0
        or has_critical_signature
        or error_rate_pct > 0.5
        or "warn" in error_summary_lower
        or "timeout" in error_summary_lower
        or "latency" in error_summary_lower
        or "429" in error_types
    ):
        severity = "WARNING"
        escalation_tier = "P2" if (error_count > 20 or is_tier_1_service) else "P3"
        sla_target = "< 2 hours (P2) or Next Business Day (P3)"
        blast_radius = "MODERATE" if is_tier_1_service else "CONTAINED"

        if "timeout" in error_summary_lower or "latency" in error_summary_lower:
            reasons.append("High latency or timeout conditions observed approaching degradation thresholds.")
        if "429" in error_types or "rate limit" in error_summary_lower:
            reasons.append("Rate limiting or API throttling detected.")
        if error_count > 0:
            reasons.append(f"Observed {error_count} non-blocking warning/error occurrences.")
        if error_rate_pct > 0:
            reasons.append(f"Error rate is {error_rate_pct}% (below critical threshold).")

        actions = [
            f"Create JIRA/tracker ticket for '{service_name}' triage.",
            "Monitor error rate metrics and latency p95/p99 graphs for degradation trends.",
            "Check resource saturation (CPU, RAM, file descriptors, network bandwidth).",
            "Evaluate if retry backoffs or client rate limits need tuning.",
        ]

    # 3. INFO Criteria
    else:
        severity = "INFO"
        escalation_tier = "None"
        sla_target = "No active SLA required"
        blast_radius = "MINIMAL"
        reasons.append("No active outages, critical exceptions, or sustained degradation detected.")
        reasons.append("Normal operational events, routine deployments, or expected client errors.")

        actions = [
            "Log event for routine audit and operational observability.",
            "No immediate SRE action required.",
        ]

    result: dict[str, Any] = {
        "service_name": service_name,
        "severity": severity,
        "escalation_tier": escalation_tier,
        "sla_target": sla_target,
        "blast_radius": blast_radius,
        "error_metrics": {
            "error_count": error_count,
            "total_requests": total_requests,
            "error_rate_pct": error_rate_pct,
        },
        "justification": reasons,
        "recommended_immediate_actions": actions,
    }

    return json.dumps(result, indent=2)
