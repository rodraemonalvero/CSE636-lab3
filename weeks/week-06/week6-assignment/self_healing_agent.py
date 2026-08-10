# Student: Rod Raemon Alvero
# Week 6 Assignment - Self-Healing payment-svc Agent

import json
import anthropic


# ---------------------------------------------------------
# Anthropic client
# ---------------------------------------------------------
client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env


# ---------------------------------------------------------
# Safety thresholds / blast-radius controls
# ---------------------------------------------------------
MIN_ERROR_BUDGET_FOR_REMEDIATION = 0.20


# ---------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------
TOOLS = [
    {
        "name": "get_metrics",
        "description": (
            "Get current error rate, latency, and remaining error budget "
            "for a service."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "Service name"
                }
            },
            "required": ["service"]
        }
    },
    {
        "name": "get_recent_logs",
        "description": "Get recent error log lines for a service.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {"type": "string"},
                "tail": {"type": "integer"}
            },
            "required": ["service"]
        }
    },
    {
        "name": "get_deployment_history",
        "description": (
            "Get deployment history and migration status for a service."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {"type": "string"}
            },
            "required": ["service"]
        }
    },
    {
        "name": "dry_run_rollback",
        "description": (
            "Preview a rollback without executing it. "
            "This must run before execute_rollback."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {"type": "string"}
            },
            "required": ["service"]
        }
    },
    {
        "name": "execute_rollback",
        "description": (
            "Request execution of a rollback. The orchestration layer "
            "enforces blast-radius checks and human approval before "
            "the rollback is actually executed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {"type": "string"},
                "approved_by": {"type": "string"}
            },
            # approved_by is added by the orchestration layer
            # after the human approval gate.
            "required": ["service"]
        }
    },
    {
        "name": "verify_service_health",
        "description": (
            "Verify service health after remediation by checking "
            "error rate, latency, and application status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {"type": "string"}
            },
            "required": ["service"]
        }
    }
]


# ---------------------------------------------------------
# Simulated environment state
# ---------------------------------------------------------
SERVICE_STATE = {
    "payment-svc": {
        "current_version": "v1.4.2",
        "previous_version": "v1.4.1",
        "migration_pending": False,
        "rollback_executed": False
    }
}


# ---------------------------------------------------------
# Simulated tool execution
# In production, these calls would go through an MCP server
# or controlled Kubernetes API layer.
# ---------------------------------------------------------
def execute_tool(tool_name: str, tool_input: dict) -> str:
    service = tool_input.get("service")

    if tool_name == "get_metrics":
        if (
            service == "payment-svc"
            and not SERVICE_STATE["payment-svc"]["rollback_executed"]
        ):
            return json.dumps({
                "error_rate": 0.08,
                "p99_latency_ms": 450,
                "error_budget_remaining": 0.42
            })

        return json.dumps({
            "error_rate": 0.01,
            "p99_latency_ms": 145,
            "error_budget_remaining": 0.41
        })

    elif tool_name == "get_recent_logs":
        if (
            service == "payment-svc"
            and not SERVICE_STATE["payment-svc"]["rollback_executed"]
        ):
            return (
                "ERROR NullPointerException in "
                "PaymentProcessor.process() line 142\n"
                "ERROR NullPointerException in "
                "PaymentProcessor.process() line 142\n"
                "WARN  Cart total $12,450.00 exceeded expected range\n"
            )

        return (
            "INFO  Payment request processed successfully\n"
            "INFO  Healthcheck OK"
        )

    elif tool_name == "get_deployment_history":
        if service == "payment-svc":
            state = SERVICE_STATE["payment-svc"]

            return json.dumps({
                "current": state["current_version"],
                "previous": state["previous_version"],
                "deployed_at": "8 minutes ago",
                "migration_pending": state["migration_pending"]
            })

        return json.dumps({})

    elif tool_name == "dry_run_rollback":
        if service != "payment-svc":
            return "DRY RUN FAILED: Service is not allowlisted."

        state = SERVICE_STATE["payment-svc"]

        if state["migration_pending"]:
            return (
                "DRY RUN BLOCKED: Database migration is pending. "
                "Escalation required."
            )

        return (
            f"DRY RUN: Would revert {service} "
            f"{state['current_version']} → "
            f"{state['previous_version']}. "
            "No migration pending. Safe to request approval."
        )

    elif tool_name == "execute_rollback":
        if service != "payment-svc":
            return "ROLLBACK BLOCKED: Service is not allowlisted."

        approver = tool_input.get("approved_by", "unknown")
        state = SERVICE_STATE["payment-svc"]

        old_version = state["current_version"]
        new_version = state["previous_version"]

        state["current_version"] = new_version
        state["rollback_executed"] = True

        return (
            f"ROLLBACK EXECUTED: {service} reverted from "
            f"{old_version} → {new_version}. "
            f"Approved by {approver}. ETA 45 seconds."
        )

    elif tool_name == "verify_service_health":
        if (
            service == "payment-svc"
            and SERVICE_STATE["payment-svc"]["rollback_executed"]
        ):
            return json.dumps({
                "service": service,
                "status": "healthy",
                "error_rate": 0.01,
                "p99_latency_ms": 145,
                "repeated_application_errors": False,
                "verification": "PASSED"
            })

        return json.dumps({
            "service": service,
            "status": "degraded",
            "error_rate": 0.08,
            "p99_latency_ms": 450,
            "verification": "FAILED"
        })

    return f"Unknown tool: {tool_name}"


# ---------------------------------------------------------
# Human approval gate
# ---------------------------------------------------------
def request_human_approval(action: str) -> tuple[bool, str]:
    print(f"\n{'=' * 60}")
    print(f"[APPROVAL GATE] Agent requests permission to: {action}")
    print(f"{'=' * 60}")

    response = input("Approve? (yes/no): ").strip().lower()

    if response == "yes":
        approver = input(
            "Enter your name for the audit log: "
        ).strip()

        return True, approver

    return False, ""


# ---------------------------------------------------------
# Main ReAct agent loop
# ---------------------------------------------------------
def run_agent(incident: str):
    print(
        f"\n[Agent] Starting self-healing triage for incident: "
        f"{incident}\n"
    )

    # Tracks safety evidence independently of the language model.
    safety_state = {
        "latest_error_budget": None,
        "migration_pending": None,
        "dry_run_completed": False
    }

    system_prompt = """
You are an agentic SRE responsible for triaging a simulated payment-svc
incident and recommending or executing safe remediation.

Follow this runbook:

1. Investigate the incident using metrics, logs, and deployment history.
2. Explain your reasoning before every tool call.
3. Check the remaining error budget before remediation.
4. If error_budget_remaining is below 0.20, do not attempt rollback.
   Escalate to the human on-call.
5. If migration_pending is true, do not attempt rollback.
   Escalate to the human on-call.
6. Always call dry_run_rollback before execute_rollback.
7. If the evidence supports rollback and all safety controls pass,
   explain that human approval is required and then call
   execute_rollback with the service name.
8. The orchestration layer will pause execution, obtain human approval,
   and add approved_by. Never attempt to bypass this approval gate.
9. If the human declines approval, stop remediation and escalate.
10. After a successful rollback, call verify_service_health.
11. Finish with a 3-5 bullet postmortem draft describing the trigger,
    evidence, decision, remediation or escalation, and verification.
"""

    messages = [
        {
            "role": "user",
            "content": (
                f"Incident alert: {incident}\n\n"
                "Follow the payment-svc runbook and determine the "
                "appropriate safe remediation."
            )
        }
    ]

    # -----------------------------------------------------
    # ReAct loop
    # -----------------------------------------------------
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system_prompt,
            tools=TOOLS,
            messages=messages
        )

        # Log reasoning text
        for block in response.content:
            if hasattr(block, "text") and block.text:
                print(f"[Agent Thought] {block.text}")

        # Normal completion
        if response.stop_reason == "end_turn":
            print("\n[Agent] Triage complete.")
            break

        if response.stop_reason != "tool_use":
            print(
                f"[Agent] Unexpected stop reason: "
                f"{response.stop_reason}"
            )
            break

        tool_results = []

        # -------------------------------------------------
        # Process tool calls
        # -------------------------------------------------
        for block in response.content:
            if block.type != "tool_use":
                continue

            tool_name = block.name
            tool_input = block.input

            print(
                f"\n[Agent Action] Calling tool: "
                f"{tool_name}({json.dumps(tool_input)})"
            )

            # ---------------------------------------------
            # Destructive action:
            # enforce blast-radius controls independently
            # of the LLM before asking for approval.
            # ---------------------------------------------
            if tool_name == "execute_rollback":

                # Blast-radius control #1:
                # dry-run must have completed successfully.
                if not safety_state["dry_run_completed"]:
                    tool_result = (
                        "ROLLBACK BLOCKED: Required dry-run has not "
                        "completed successfully. Escalate to human "
                        "on-call."
                    )

                # Blast-radius control #2:
                # protect critically low error budget.
                elif (
                    safety_state["latest_error_budget"] is None
                    or safety_state["latest_error_budget"]
                    < MIN_ERROR_BUDGET_FOR_REMEDIATION
                ):
                    tool_result = (
                        "ROLLBACK BLOCKED: Error budget is below the "
                        "safe remediation threshold or was not checked. "
                        "Escalate to human on-call."
                    )

                # Additional protection:
                # do not roll back across pending migration.
                elif safety_state["migration_pending"] is True:
                    tool_result = (
                        "ROLLBACK BLOCKED: Migration is pending. "
                        "Escalate to human on-call."
                    )

                else:
                    approved, approver = request_human_approval(
                        f"execute_rollback on "
                        f"{tool_input.get('service')}"
                    )

                    if not approved:
                        tool_result = (
                            "Rollback DECLINED by operator. "
                            "Escalate to human on-call for manual "
                            "intervention."
                        )
                    else:
                        tool_input["approved_by"] = approver
                        tool_result = execute_tool(
                            tool_name,
                            tool_input
                        )

            else:
                tool_result = execute_tool(
                    tool_name,
                    tool_input
                )

                # -----------------------------------------
                # Update independent safety state
                # -----------------------------------------
                if tool_name == "get_metrics":
                    try:
                        metric_data = json.loads(tool_result)
                        safety_state["latest_error_budget"] = (
                            metric_data.get(
                                "error_budget_remaining"
                            )
                        )
                    except json.JSONDecodeError:
                        safety_state["latest_error_budget"] = None

                elif tool_name == "get_deployment_history":
                    try:
                        deployment_data = json.loads(tool_result)
                        safety_state["migration_pending"] = (
                            deployment_data.get(
                                "migration_pending"
                            )
                        )
                    except json.JSONDecodeError:
                        safety_state["migration_pending"] = None

                elif tool_name == "dry_run_rollback":
                    safety_state["dry_run_completed"] = (
                        tool_result.startswith("DRY RUN:")
                        and "Safe to request approval" in tool_result
                    )

            print(f"[Tool Result] {tool_result}")

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": tool_result
            })

        # Continue ReAct conversation
        messages.append({
            "role": "assistant",
            "content": response.content
        })

        messages.append({
            "role": "user",
            "content": tool_results
        })


# ---------------------------------------------------------
# Simulated incident
# ---------------------------------------------------------
if __name__ == "__main__":
    incident_description = (
        "ALERT: payment-svc error rate has remained above 5% "
        "for the past 4 minutes. "
        "The issue began approximately 8 minutes after deployment "
        "of v1.4.2. Investigate and safely remediate the incident."
    )

    run_agent(incident_description)