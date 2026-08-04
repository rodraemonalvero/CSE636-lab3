from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from telemetry import (
    SPAN_FILE,
    close_telemetry,
    configure_tracer,
    genai_span,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent

GROUPED_ALERTS_PATH = PROJECT_ROOT / "output" / "grouped_alerts.json"
LOGS_PATH = PROJECT_ROOT / "data" / "logs_sample.txt"
REPORT_PATH = PROJECT_ROOT / "output" / "rca_report.md"

MAX_LOG_EVIDENCE = 12


@dataclass
class ToolResult:
    """Structured result returned by an RCA tool."""

    tool_name: str
    summary: str
    evidence: list[str]
    data: dict[str, Any]


def load_grouped_alerts() -> list[dict[str, Any]]:
    """Load the alert groups created by alert_grouper.py."""

    if not GROUPED_ALERTS_PATH.exists():
        raise FileNotFoundError(
            "Grouped alert file was not found. Run alert_grouper.py first: "
            f"{GROUPED_ALERTS_PATH}"
        )

    with GROUPED_ALERTS_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        groups = json.load(file)

    if not isinstance(groups, list) or not groups:
        raise ValueError(
            "grouped_alerts.json must contain at least one incident group."
        )

    return groups


def load_logs() -> list[str]:
    """Load structured application and infrastructure logs."""

    if not LOGS_PATH.exists():
        raise FileNotFoundError(
            f"Structured log file was not found: {LOGS_PATH}"
        )

    logs = LOGS_PATH.read_text(
        encoding="utf-8",
    ).splitlines()

    if len(logs) < 200:
        raise ValueError(
            "logs_sample.txt must contain at least 200 lines."
        )

    return logs


def select_primary_incident(
    grouped_alerts: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Select the highest-priority incident.

    Priority is primarily based on alert count. Application-error incidents
    receive additional weight because they directly represent failed service
    behavior.
    """

    def priority_score(group: dict[str, Any]) -> float:
        alert_count = float(group.get("alert_count", 0))
        average_error_rate = float(group.get("average_error_rate", 0))

        application_error_bonus = (
            1000
            if group.get("incident") == "Application Errors"
            else 0
        )

        return (
            application_error_bonus
            + alert_count
            + average_error_rate
        )

    return max(
        grouped_alerts,
        key=priority_score,
    )


def metrics_analysis_tool(
    incident: dict[str, Any],
) -> ToolResult:
    """
    Analyze the grouped metric evidence for the selected incident.

    This is Tool 1 required by the assignment.
    """

    alert_count = int(incident.get("alert_count", 0))
    average_cpu = float(incident.get("average_cpu_pct", 0))
    average_memory = float(incident.get("average_mem_pct", 0))
    average_requests = float(
        incident.get("average_req_per_sec", 0)
    )
    average_error_rate = float(
        incident.get("average_error_rate", 0)
    )

    start_time = str(incident.get("start_time", "unknown"))
    end_time = str(incident.get("end_time", "unknown"))

    sample_alerts = incident.get("sample_alerts", [])

    highest_cpu = max(
        (
            float(alert.get("cpu_pct", 0))
            for alert in sample_alerts
        ),
        default=0,
    )

    highest_error_rate = max(
        (
            float(alert.get("error_rate", 0))
            for alert in sample_alerts
        ),
        default=0,
    )

    evidence = [
        f"Incident category: {incident.get('incident', 'Unknown')}",
        f"Detected alerts in group: {alert_count}",
        f"Incident window: {start_time} through {end_time}",
        f"Average CPU utilization: {average_cpu:.2f}%",
        f"Average memory utilization: {average_memory:.2f}%",
        f"Average request rate: {average_requests:.2f} requests/second",
        f"Average application error rate: {average_error_rate:.3f}",
        f"Highest sampled CPU utilization: {highest_cpu:.2f}%",
        f"Highest sampled error rate: {highest_error_rate:.3f}",
    ]

    if average_error_rate >= 3:
        condition = (
            "The error rate is substantially above the normal baseline, "
            "indicating sustained application failure rather than an isolated "
            "outlier."
        )
    elif average_cpu >= 80:
        condition = (
            "CPU utilization is consistent with compute saturation and may "
            "be contributing to degraded response times."
        )
    elif average_requests >= 450:
        condition = (
            "The request rate indicates a traffic surge that may have "
            "overloaded one or more downstream dependencies."
        )
    else:
        condition = (
            "The incident combines moderate infrastructure pressure with "
            "abnormal service behavior."
        )

    summary = (
        f"The metrics tool evaluated {alert_count} related alerts. "
        f"{condition}"
    )

    return ToolResult(
        tool_name="metrics_analysis_tool",
        summary=summary,
        evidence=evidence,
        data={
            "alert_count": alert_count,
            "start_time": start_time,
            "end_time": end_time,
            "average_cpu_pct": average_cpu,
            "average_mem_pct": average_memory,
            "average_req_per_sec": average_requests,
            "average_error_rate": average_error_rate,
            "highest_sample_cpu_pct": highest_cpu,
            "highest_sample_error_rate": highest_error_rate,
        },
    )


def log_analysis_tool(
    incident: dict[str, Any],
    logs: list[str],
) -> ToolResult:
    """
    Search logs for events related to the selected incident.

    This is Tool 2 required by the assignment.
    """

    incident_name = str(
        incident.get("incident", "General Infrastructure")
    )

    keyword_map = {
        "Application Errors": [
            "level=ERROR",
            "database_timeout",
            "service_unavailable",
            "api_error",
            "connection_pool",
            "cpu_pressure",
        ],
        "CPU Saturation": [
            "cpu_pressure",
            "high_latency",
            "service_unavailable",
            "level=ERROR",
        ],
        "Memory Pressure": [
            "memory_pressure",
            "connection_pool",
            "database_timeout",
            "level=ERROR",
        ],
        "Traffic Spike": [
            "high_latency",
            "request_completed",
            "service_unavailable",
            "level=WARNING",
        ],
        "General Infrastructure": [
            "level=WARNING",
            "level=ERROR",
        ],
    }

    keywords = keyword_map.get(
        incident_name,
        keyword_map["General Infrastructure"],
    )

    matching_logs = [
        line
        for line in logs
        if any(keyword in line for keyword in keywords)
    ]

    selected_logs = matching_logs[:MAX_LOG_EVIDENCE]

    event_counts: dict[str, int] = {}

    important_events = [
        "database_timeout",
        "service_unavailable",
        "cpu_pressure",
        "connection_pool",
        "high_latency",
        "memory_pressure",
        "api_error",
        "authentication_failure",
    ]

    for event in important_events:
        event_counts[event] = sum(
            event in line
            for line in matching_logs
        )

    error_count = sum(
        "level=ERROR" in line
        for line in matching_logs
    )

    warning_count = sum(
        "level=WARNING" in line
        for line in matching_logs
    )

    affected_services: set[str] = set()

    for line in matching_logs:
        for section in line.split():
            if section.startswith("service="):
                affected_services.add(
                    section.removeprefix("service=")
                )

    dominant_event = max(
        event_counts,
        key=event_counts.get,
    )

    summary = (
        f"The log tool found {len(matching_logs)} matching log records, "
        f"including {error_count} errors and {warning_count} warnings. "
        f"The most frequent relevant event was '{dominant_event}'."
    )

    evidence = selected_logs.copy()

    return ToolResult(
        tool_name="log_analysis_tool",
        summary=summary,
        evidence=evidence,
        data={
            "matching_log_count": len(matching_logs),
            "error_count": error_count,
            "warning_count": warning_count,
            "dominant_event": dominant_event,
            "event_counts": event_counts,
            "affected_services": sorted(affected_services),
        },
    )


def infer_root_cause(
    incident: dict[str, Any],
    metrics_result: ToolResult,
    logs_result: ToolResult,
) -> tuple[str, str, list[str]]:
    """Infer a plausible root cause from both tool results."""

    error_rate = float(
        metrics_result.data["average_error_rate"]
    )

    average_cpu = float(
        metrics_result.data["average_cpu_pct"]
    )

    event_counts = logs_result.data["event_counts"]

    database_timeouts = int(
        event_counts.get("database_timeout", 0)
    )

    connection_pool_events = int(
        event_counts.get("connection_pool", 0)
    )

    unavailable_events = int(
        event_counts.get("service_unavailable", 0)
    )

    cpu_pressure_events = int(
        event_counts.get("cpu_pressure", 0)
    )

    if database_timeouts > 0 and connection_pool_events > 0:
        root_cause = (
            "The most plausible root cause is database connection-pool "
            "exhaustion, followed by database request timeouts. As available "
            "connections declined, application requests waited longer or "
            "failed, which increased the error rate and caused upstream "
            "services to report dependency failures."
        )

        mechanism = (
            "Rising workload and CPU pressure increased the number or duration "
            "of database operations. The PostgreSQL connection pool approached "
            "its limit, new requests could not obtain connections promptly, "
            "and database calls timed out. Those timeouts propagated through "
            "the orders service to the API gateway as service-unavailable and "
            "HTTP 500 responses."
        )

    elif cpu_pressure_events > 0 and average_cpu >= 70:
        root_cause = (
            "The most plausible root cause is CPU saturation in an application "
            "service, which reduced request-processing capacity and increased "
            "latency and error rates."
        )

        mechanism = (
            "As CPU availability decreased, requests remained queued for "
            "longer periods. Downstream calls exceeded their timeouts and "
            "upstream services reported dependency failures."
        )

    elif unavailable_events > 0:
        root_cause = (
            "The most plausible root cause is failure or unavailability of an "
            "upstream service dependency."
        )

        mechanism = (
            "Dependent requests could not complete successfully. Retries and "
            "timeout behavior increased load and produced additional errors."
        )

    else:
        root_cause = (
            "The evidence indicates a combined application and infrastructure "
            "degradation, but the available synthetic logs do not establish "
            "one definitive initiating fault."
        )

        mechanism = (
            "Several abnormal signals occurred together and likely reinforced "
            "one another. Additional distributed traces and database metrics "
            "would be needed to determine the precise initiating event."
        )

    confidence_factors = [
        f"Average application error rate was {error_rate:.3f}.",
        (
            f"The log search found {database_timeouts} database-timeout "
            "events."
        ),
        (
            f"The log search found {connection_pool_events} "
            "connection-pool pressure events."
        ),
        (
            f"The log search found {unavailable_events} "
            "service-unavailable events."
        ),
        (
            f"The selected group contained "
            f"{incident.get('alert_count', 0)} related alerts."
        ),
    ]

    return root_cause, mechanism, confidence_factors


def build_recommendations(
    metrics_result: ToolResult,
    logs_result: ToolResult,
) -> tuple[list[str], list[str]]:
    """Create immediate remediation and preventive recommendations."""

    dominant_event = str(
        logs_result.data.get("dominant_event", "")
    )

    immediate_actions = [
        (
            "Confirm the health of PostgreSQL and inspect active, idle, and "
            "waiting database connections."
        ),
        (
            "Temporarily reduce traffic pressure using rate limiting or "
            "controlled load shedding."
        ),
        (
            "Restart only the unhealthy application instances after preserving "
            "logs and diagnostic evidence."
        ),
        (
            "Review timeout and retry behavior to prevent retries from "
            "amplifying the incident."
        ),
    ]

    preventive_actions = [
        (
            "Add alerts for database connection-pool utilization, wait time, "
            "and timeout frequency."
        ),
        (
            "Set bounded retries with exponential backoff and randomized "
            "jitter."
        ),
        (
            "Add service-level dashboards for latency percentiles, error rate, "
            "CPU, memory, request volume, and database saturation."
        ),
        (
            "Use load testing to validate connection-pool size and application "
            "capacity before deployment."
        ),
        (
            "Create an automated cost and token guardrail for the RCA agent, "
            "including maximum input size and daily usage limits."
        ),
    ]

    if dominant_event == "cpu_pressure":
        preventive_actions.append(
            "Configure horizontal scaling based on sustained CPU and request "
            "queue depth."
        )

    if metrics_result.data["average_error_rate"] >= 3:
        immediate_actions.append(
            "Pause nonessential background jobs until the service error rate "
            "returns to its normal operating range."
        )

    return immediate_actions, preventive_actions


def format_bullet_list(items: list[str]) -> str:
    """Convert strings into a Markdown bullet list."""

    return "\n".join(
        f"- {item}"
        for item in items
    )


def format_numbered_list(items: list[str]) -> str:
    """Convert strings into a Markdown numbered list."""

    return "\n".join(
        f"{index}. {item}"
        for index, item in enumerate(items, start=1)
    )


def generate_rca_report(
    incident: dict[str, Any],
    metrics_result: ToolResult,
    logs_result: ToolResult,
) -> str:
    """Generate a structured Markdown RCA report."""

    root_cause, mechanism, confidence_factors = infer_root_cause(
        incident=incident,
        metrics_result=metrics_result,
        logs_result=logs_result,
    )

    immediate_actions, preventive_actions = build_recommendations(
        metrics_result=metrics_result,
        logs_result=logs_result,
    )

    metrics_evidence = format_bullet_list(
        metrics_result.evidence
    )

    log_evidence = format_bullet_list(
        [
            f"`{line}`"
            for line in logs_result.evidence
        ]
    )

    affected_services = ", ".join(
        logs_result.data.get(
            "affected_services",
            [],
        )
    )

    report = f"""# Root Cause Analysis Report

## Incident Summary

- **Incident category:** {incident.get("incident", "Unknown")}
- **Incident start:** {incident.get("start_time", "Unknown")}
- **Incident end:** {incident.get("end_time", "Unknown")}
- **Grouped alerts:** {incident.get("alert_count", 0)}
- **Affected services identified in logs:** {affected_services or "Not determined"}
- **Analysis method:** Agentic RCA using a metrics tool and a log-analysis tool

The anomaly detector identified a sustained period of abnormal application behavior. The alert grouper correlated related metric anomalies into one incident, and the RCA agent invoked two evidence tools before producing this report.

## Tool Execution Summary

### Tool 1 — Metrics Analysis

{metrics_result.summary}

### Tool 2 — Log Analysis

{logs_result.summary}

## Metrics Evidence

{metrics_evidence}

## Log Evidence

{log_evidence}

## Most Plausible Root Cause

{root_cause}

## Causal Mechanism

{mechanism}

## Confidence and Limitations

The conclusion has **moderate-to-high confidence** because both metric anomalies and structured log events support the same failure sequence.

{format_bullet_list(confidence_factors)}

This analysis is based on synthetic data. In a production system, the conclusion should be validated using distributed traces, database performance statistics, deployment history, infrastructure events, and service-owner confirmation.

## Immediate Remediation

{format_numbered_list(immediate_actions)}

## Preventive Measures

{format_numbered_list(preventive_actions)}

## Validation Plan

1. Confirm that database connection wait time and timeout counts decrease after remediation.
2. Verify that application error rate returns to its normal baseline.
3. Confirm that CPU utilization and latency remain stable under expected load.
4. Run a controlled load test to reproduce the failure threshold.
5. Review OpenTelemetry traces to ensure requests no longer fail at the database dependency.

## Observability Requirements

A production dashboard for this system should track:

- Anomaly count and anomaly score
- Application error rate
- CPU and memory utilization
- Request volume and latency percentiles
- Database connection-pool utilization
- Database timeout and retry counts
- RCA-agent input and output tokens
- RCA-agent latency and estimated cost
- Number and type of tools invoked
- RCA execution failures

---

*Generated by the Week 5 instrumented RCA agent.*
"""

    return report


class RCAAgent:
    """
    Small deterministic agent that plans and invokes analysis tools.

    The agent uses an explicit tool registry so its behavior is inspectable and
    reproducible without requiring paid API access.
    """

    def __init__(
        self,
        tracer: Any,
        grouped_alerts: list[dict[str, Any]],
        logs: list[str],
    ) -> None:
        self.tracer = tracer
        self.grouped_alerts = grouped_alerts
        self.logs = logs

        self.tools: dict[str, Callable[..., ToolResult]] = {
            "metrics_analysis_tool": metrics_analysis_tool,
            "log_analysis_tool": log_analysis_tool,
        }

    def run(self) -> str:
        """Select an incident, call two tools, and generate the RCA."""

        incident = select_primary_incident(
            self.grouped_alerts
        )

        agent_input = json.dumps(
            {
                "task": (
                    "Generate a structured root cause analysis using metrics "
                    "and log evidence."
                ),
                "selected_incident": incident,
                "required_tools": list(self.tools.keys()),
            },
            indent=2,
        )

        with genai_span(
            tracer=self.tracer,
            span_name="rca_agent_run",
            input_text=agent_input,
        ) as span_result:

            with self.tracer.start_as_current_span(
                "tool.metrics_analysis"
            ) as tool_span:

                tool_span.set_attribute(
                    "tool.name",
                    "metrics_analysis_tool",
                )

                metrics_result = self.tools[
                    "metrics_analysis_tool"
                ](
                    incident
                )

                tool_span.set_attribute(
                    "tool.result.alert_count",
                    metrics_result.data["alert_count"],
                )

                tool_span.set_attribute(
                    "tool.status",
                    "ok",
                )

            with self.tracer.start_as_current_span(
                "tool.log_analysis"
            ) as tool_span:

                tool_span.set_attribute(
                    "tool.name",
                    "log_analysis_tool",
                )

                logs_result = self.tools[
                    "log_analysis_tool"
                ](
                    incident,
                    self.logs,
                )

                tool_span.set_attribute(
                    "tool.result.matching_logs",
                    logs_result.data["matching_log_count"],
                )

                tool_span.set_attribute(
                    "tool.status",
                    "ok",
                )

            report = generate_rca_report(
                incident=incident,
                metrics_result=metrics_result,
                logs_result=logs_result,
            )

            span_result["output_text"] = report
            span_result["tool_count"] = 2
            span_result["status"] = "ok"

        return report


def save_report(report: str) -> None:
    """Write the generated RCA report to output/rca_report.md."""

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT_PATH.write_text(
        report,
        encoding="utf-8",
    )


def main() -> None:
    """Run the full agentic RCA workflow."""

    grouped_alerts = load_grouped_alerts()
    logs = load_logs()

    tracer, span_output = configure_tracer()

    try:
        agent = RCAAgent(
            tracer=tracer,
            grouped_alerts=grouped_alerts,
            logs=logs,
        )

        report = agent.run()

        save_report(report)

    finally:
        close_telemetry(span_output)

    selected_incident = select_primary_incident(
        grouped_alerts
    )

    print("Agentic RCA completed.")
    print(
        "Selected incident:",
        selected_incident.get(
            "incident",
            "Unknown",
        ),
    )
    print(
        "Tools invoked:",
        "metrics_analysis_tool, log_analysis_tool",
    )
    print(f"RCA report: {REPORT_PATH}")
    print(f"OTel spans: {SPAN_FILE}")
    print(
        "Report size:",
        REPORT_PATH.stat().st_size,
        "bytes",
    )
    print(
        "Span file size:",
        SPAN_FILE.stat().st_size,
        "bytes",
    )


if __name__ == "__main__":
    main()