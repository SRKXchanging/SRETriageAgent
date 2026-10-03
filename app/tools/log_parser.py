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

"""Log parsing tools for SRE incident triage.

Extracts structured events, error frequencies, stack traces, and anomaly
indicators from diverse server log formats (JSON, Syslog, Apache/Nginx, K8s, Stacktraces).
"""

import json
import re
from collections import Counter
from typing import Any

# Common regex patterns for structured/unstructured log formats
ISO_TIMESTAMP_RE = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\b"
)
SYSLOG_TIMESTAMP_RE = re.compile(
    r"^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}"
)
HTTP_ACCESS_RE = re.compile(
    r'(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<time>[^\]]+)\]\s+"(?P<method>[A-Z]+)\s+(?P<path>\S+)\s+HTTP/[0-9.]+"\s+(?P<status>\d{3})\s+(?P<bytes>\S+)'
)
TRACE_ID_RE = re.compile(
    r"(?:trace_id|traceId|correlation_id|request_id|requestId)[=:\s\"']+([a-zA-Z0-9_\-]+)",
    re.IGNORECASE,
)
LOG_LEVEL_RE = re.compile(
    r"\b(CRITICAL|FATAL|ERROR|WARN|WARNING|INFO|DEBUG)\b",
    re.IGNORECASE,
)
SERVICE_BRACKET_RE = re.compile(r"\[([a-zA-Z0-9_\-.]{3,30})\]")
STATUS_CODE_RE = re.compile(
    r"\b(?:status|HTTP|code)[=:\s]+(\d{3})\b",
    re.IGNORECASE,
)
HEX_ID_RE = re.compile(r"\b[0-9a-fA-F]{8,}\b")
IP_ADDR_RE = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
EXCEPTION_HEADER_RE = re.compile(r"^[a-zA-Z0-9_.]+(?:Exception|Error):")


def _normalize_severity(level_str: str | None) -> str:
    """Normalize log level to standard SRE severities."""
    if not level_str:
        return "INFO"
    level = level_str.strip().upper()
    if level in ("FATAL", "CRITICAL", "EMERG", "ALERT"):
        return "CRITICAL"
    if level in ("ERROR", "ERR"):
        return "ERROR"
    if level in ("WARN", "WARNING"):
        return "WARNING"
    if level in ("INFO", "NOTICE"):
        return "INFO"
    if level in ("DEBUG", "TRACE"):
        return "DEBUG"
    return level


def _parse_single_log_line(line: str) -> dict[str, Any]:
    """Parse an individual log line supporting JSON, Access, and Standard Syslog/App formats."""
    stripped = line.strip()
    if not stripped:
        return {}

    # Try parsing as JSON first
    if stripped.startswith(("{", "[")) and stripped.endswith(("}", "]")):
        try:
            data = json.loads(stripped)
            if isinstance(data, dict):
                timestamp = (
                    data.get("timestamp")
                    or data.get("time")
                    or data.get("@timestamp")
                    or data.get("datetime")
                    or ""
                )
                raw_level = (
                    data.get("level")
                    or data.get("severity")
                    or data.get("log_level")
                    or "INFO"
                )
                level = _normalize_severity(str(raw_level))
                service = (
                    data.get("service")
                    or data.get("app")
                    or data.get("component")
                    or data.get("service_name")
                    or "unknown"
                )
                message = (
                    data.get("message")
                    or data.get("msg")
                    or data.get("event")
                    or data.get("error")
                    or str(data)
                )
                status_code = (
                    data.get("status_code")
                    or data.get("status")
                    or data.get("http_status")
                )
                trace_id = (
                    data.get("trace_id")
                    or data.get("traceId")
                    or data.get("correlation_id")
                    or data.get("request_id")
                )
                return {
                    "format": "json",
                    "timestamp": str(timestamp),
                    "level": level,
                    "service": str(service),
                    "message": str(message),
                    "status_code": int(status_code) if status_code is not None and str(status_code).isdigit() else None,
                    "trace_id": str(trace_id) if trace_id else None,
                    "raw": stripped,
                }
        except json.JSONDecodeError:
            pass

    # Try HTTP access log pattern
    access_match = HTTP_ACCESS_RE.search(stripped)
    if access_match:
        status_code = int(access_match.group("status"))
        if status_code >= 500:
            level = "ERROR"
        elif status_code >= 400:
            level = "WARNING"
        else:
            level = "INFO"
        return {
            "format": "http_access",
            "timestamp": access_match.group("time"),
            "level": level,
            "service": "http-server",
            "message": f"{access_match.group('method')} {access_match.group('path')} -> {status_code}",
            "status_code": status_code,
            "trace_id": None,
            "raw": stripped,
        }

    # Try Bracketed / Standard App log pattern
    timestamp = ""
    ts_match = ISO_TIMESTAMP_RE.search(stripped) or SYSLOG_TIMESTAMP_RE.search(stripped)
    if ts_match:
        timestamp = ts_match.group(0)

    # Detect trace ID if present
    trace_id = None
    trace_match = TRACE_ID_RE.search(stripped)
    if trace_match:
        trace_id = trace_match.group(1)

    # Detect log level keyword
    level = "INFO"
    if level_match := LOG_LEVEL_RE.search(stripped):
        level = _normalize_severity(level_match.group(1))

    # Extract service name if in brackets or formatted: e.g. [auth-service]
    service = "unknown"
    if service_match := SERVICE_BRACKET_RE.search(stripped):
        candidate = service_match.group(1)
        if (
            candidate.upper()
            not in ("INFO", "WARN", "WARNING", "ERROR", "CRITICAL", "FATAL", "DEBUG")
            and not candidate.isdigit()
        ):
            service = candidate

    # Status code detection (e.g. status=500, HTTP 503)
    status_code = None
    if status_match := STATUS_CODE_RE.search(stripped):
        status_code = int(status_match.group(1))

    return {
        "format": "text",
        "timestamp": timestamp,
        "level": level,
        "service": service,
        "message": stripped,
        "status_code": status_code,
        "trace_id": trace_id,
        "raw": stripped,
    }


def _extract_stack_traces(raw_logs: str) -> list[dict[str, str]]:
    """Identify and isolate multi-line exception stack traces."""
    traces = []
    lines = raw_logs.splitlines()
    in_trace = False
    current_trace: list[str] = []
    trace_type = "unknown"

    for line in lines:
        stripped = line.strip()
        # Python traceback
        if "Traceback (most recent call last):" in stripped:
            if current_trace:
                traces.append({"type": trace_type, "trace": "\n".join(current_trace)})
                current_trace = []
            in_trace = True
            trace_type = "Python"
            current_trace.append(line)
        # Java exception
        elif re.search(r"(?:Exception|Error):", stripped) and not in_trace and ("Exception" in stripped or "Error" in stripped):
            in_trace = True
            trace_type = "Java/Application"
            current_trace.append(line)
        # In trace continuation
        elif in_trace:
            if (
                stripped.startswith("at ")  # Java / JS / Node
                or stripped.startswith('File "')  # Python
                or stripped.startswith("goroutine ")  # Go
                or stripped.startswith("Caused by:")
                or EXCEPTION_HEADER_RE.match(stripped)
            ):
                current_trace.append(line)
            elif not stripped:
                continue
            else:
                traces.append({"type": trace_type, "trace": "\n".join(current_trace)})
                current_trace = []
                in_trace = False

    if current_trace:
        traces.append({"type": trace_type, "trace": "\n".join(current_trace)})

    return traces


def parse_server_logs(raw_logs: str) -> str:
    """Parses raw multiline server logs and extracts structured SRE telemetry.

    Supports JSON logs, Syslog, Apache/Nginx web logs, Kubernetes/Docker container
    logs, and application stack traces. Aggregates error frequencies, service breakdowns,
    HTTP status distributions, and detected stack traces.

    Args:
        raw_logs: A string containing raw server log lines to parse.

    Returns:
        A JSON string containing:
            - summary: Total lines, parsed events count, time window.
            - severity_breakdown: Counts of CRITICAL, ERROR, WARNING, INFO, DEBUG events.
            - impacted_services: List of affected service components.
            - status_code_distribution: Counts of HTTP 5xx, 4xx, 2xx codes.
            - top_error_patterns: Top unique error occurrences with frequency.
            - stack_traces: Extracted full stack traces.
            - sample_parsed_events: Up to 15 parsed structured events for immediate inspection.
    """
    if not raw_logs or not raw_logs.strip():
        return json.dumps({"error": "Empty log input provided.", "summary": {}})

    lines = raw_logs.strip().splitlines()
    parsed_events: list[dict[str, Any]] = []
    level_counts: Counter[str] = Counter()
    service_counts: Counter[str] = Counter()
    status_counts: Counter[int] = Counter()
    error_patterns: Counter[str] = Counter()
    timestamps: list[str] = []

    for line in lines:
        if not line.strip():
            continue
        event = _parse_single_log_line(line)
        if event:
            parsed_events.append(event)
            level = event.get("level", "INFO")
            level_counts[level] += 1

            service = event.get("service")
            if service and service != "unknown":
                service_counts[service] += 1

            status = event.get("status_code")
            if status:
                status_counts[status] += 1

            if level in ("CRITICAL", "ERROR"):
                # Clean message to cluster common error messages
                clean_msg = HEX_ID_RE.sub("<ID>", event.get("message", ""))
                clean_msg = IP_ADDR_RE.sub("<IP>", clean_msg)
                clean_msg = clean_msg[:120]  # truncate long lines
                error_patterns[clean_msg] += 1

            if event.get("timestamp"):
                timestamps.append(event["timestamp"])

    stack_traces = _extract_stack_traces(raw_logs)

    time_range = {
        "start": timestamps[0] if timestamps else "unknown",
        "end": timestamps[-1] if timestamps else "unknown",
    }

    result = {
        "summary": {
            "total_lines_received": len(lines),
            "parsed_events_count": len(parsed_events),
            "time_range": time_range,
        },
        "severity_breakdown": {
            "CRITICAL": level_counts.get("CRITICAL", 0),
            "ERROR": level_counts.get("ERROR", 0),
            "WARNING": level_counts.get("WARNING", 0),
            "INFO": level_counts.get("INFO", 0),
            "DEBUG": level_counts.get("DEBUG", 0),
        },
        "impacted_services": list(service_counts.keys()),
        "status_code_distribution": {str(k): v for k, v in status_counts.items()},
        "top_error_patterns": [
            {"pattern": pattern, "count": count}
            for pattern, count in error_patterns.most_common(10)
        ],
        "stack_traces_detected": len(stack_traces),
        "stack_traces": stack_traces[:5],  # Top 5 stack traces
        "sample_parsed_events": parsed_events[:15],
    }

    return json.dumps(result, indent=2)


def filter_logs(
    raw_logs: str,
    level: str = "",
    service: str = "",
    keyword: str = "",
    max_results: int = 50,
) -> str:
    """Filters log lines by severity level, service name, or specific keyword.

    Useful for zooming into specific failures, isolating an impacted microservice,
    or retrieving relevant context from voluminous log files.

    Args:
        raw_logs: The raw log text to search.
        level: Filter by severity level (e.g., 'CRITICAL', 'ERROR', 'WARNING', 'INFO').
        service: Filter by service name (e.g., 'auth-service', 'payment-gateway').
        keyword: Substring or error pattern to search for (e.g., 'timeout', '503', 'OOM').
        max_results: Maximum number of matching log lines to return (default: 50).

    Returns:
        A JSON string containing the count of matches and list of matched log lines.
    """
    if not raw_logs or not raw_logs.strip():
        return json.dumps({"matched_count": 0, "logs": []})

    lines = raw_logs.strip().splitlines()
    matches: list[dict[str, Any]] = []
    norm_level = level.strip().upper() if level else ""
    norm_keyword = keyword.strip().lower() if keyword else ""
    norm_service = service.strip().lower() if service else ""

    allowed_levels = ("ERROR", "CRITICAL") if norm_level == "ERROR" else (norm_level,)

    for line in lines:
        if not line.strip():
            continue

        # Early filter by keyword before parsing
        if norm_keyword and norm_keyword not in line.lower():
            continue

        event = _parse_single_log_line(line)
        if not event:
            continue

        # Check level
        if norm_level and event.get("level", "").upper() not in allowed_levels:
            continue

        # Check service
        if norm_service and norm_service not in event.get("service", "").lower():
            continue

        matches.append(event)
        if len(matches) >= max_results:
            break

    return json.dumps(
        {
            "filter_criteria": {
                "level": level or None,
                "service": service or None,
                "keyword": keyword or None,
            },
            "matched_count": len(matches),
            "logs": matches,
        },
        indent=2,
    )
