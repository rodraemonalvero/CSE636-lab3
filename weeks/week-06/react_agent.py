# Student: Rod Raemon Alvero

# react_agent.py
# A ReAct-style agent that uses MCP tools to triage a simulated incident.
# Uses the Anthropic API with tool_use.

import json
import anthropic

# --- Anthropic client ---
client = anthropic.Anthropic()   # reads ANTHROPIC_API_KEY from env

# --- Tool definitions (mirror the MCP server) ---
TOOLS = [
    {
        "name": "get_metrics",
        "description": "Get current error rate and latency for a service",
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "Service name"}
            },
            "required": ["service"]
        }
    },
    {
        "name": "get_recent_logs",
        "description": "Get recent error log lines for a service (last N lines)",
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
        "description": "Get recent deployment history for a service",
        "input_schema": {
            "type": "object",
            "properties": {"service": {"type": "string"}},
            "required": ["service"]
        }
    },
    {
        "name": "dry_run_rollback",
        "description": "Preview a rollback without executing it. Always run this before execute_rollback.",
        "input_schema": {
            "type": "object",
            "properties": {"service": {"type": "string"}},
            "required": ["service"]
        }
    },
    {
        "name": "execute_rollback",
        "description": "Execute a rollback. Human approval is enforced by the orchestration layer before execution.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {"type": "string"},
                "approved_by": {"type": "string"}
            },
            "required": ["service"]
        }
    }
]

# --- Simulated tool execution (in a real system, these call the MCP server) ---
def execute_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "get_metrics":
        s = tool_input["service"]
        if s == "payment-svc":
            return json.dumps({
                "error_rate": 0.08,
                "p99_latency_ms": 450,
                "error_budget_remaining": 0.42
            })
        return json.dumps({
            "error_rate": 0.003,
            "p99_latency_ms": 120,
            "error_budget_remaining": 0.85
        })

    elif tool_name == "get_recent_logs":
        s = tool_input["service"]
        if s == "payment-svc":
            return (
                "ERROR NullPointerException in PaymentProcessor.process() line 142\n"
                "ERROR NullPointerException in PaymentProcessor.process() line 142\n"
                "WARN  Cart total $12,450.00 exceeded expected range\n"
            )
        return "INFO  Request processed in 115ms\nINFO  Healthcheck OK"

    elif tool_name == "get_deployment_history":
        s = tool_input["service"]
        if s == "payment-svc":
            return json.dumps({
                "current": "v1.4.2",
                "previous": "v1.4.1",
                "deployed_at": "8 minutes ago",
                "migration_pending": False
            })
        return json.dumps({
            "current": "v2.1.0",
            "deployed_at": "2 hours ago"
        })

    elif tool_name == "dry_run_rollback":
        s = tool_input["service"]
        return (
            f"DRY RUN: Would revert {s} v1.4.2 → v1.4.1. "
            "No migration pending. Safe to proceed."
        )

    elif tool_name == "execute_rollback":
        s = tool_input["service"]
        approver = tool_input.get("approved_by", "unknown")
        return (
            f"ROLLBACK EXECUTED: {s} reverted to v1.4.1. "
            f"Approved by {approver}. ETA 45s."
        )

    return f"Unknown tool: {tool_name}"

# --- Approval gate ---
def request_human_approval(action: str) -> tuple[bool, str]:
    print(f"\n{'='*60}")
    print(f"[APPROVAL GATE] Agent requests permission to: {action}")
    print(f"{'='*60}")
    response = input("Approve? (yes/no): ").strip().lower()

    if response == "yes":
        approver = input("Enter your name for the audit log: ").strip()
        return True, approver

    return False, ""

# --- Main agent loop ---
def run_agent(incident: str):
    print(f"\n[Agent] Starting triage for incident: {incident}\n")

    system_prompt = """You are an agentic SRE (Site Reliability Engineer).
Your job is to triage incidents using the available tools and recommend or execute remediations.

Rules you MUST follow:
1. Always run dry_run_rollback BEFORE execute_rollback.
2. Before execute_rollback, state that human approval is required, then call execute_rollback.
   The orchestration layer will pause execution, request approval, and add approved_by if approved.
3. Always explain your reasoning before each tool call.
4. If you are not confident (e.g., no matching pattern, migration pending), recommend
   escalation to the human on-call rather than taking action.
5. After resolving an incident (or escalating), summarize what happened in 3-5 bullet points
   suitable for a postmortem draft.
"""

    messages = [
        {
            "role": "user",
            "content": (
                f"Incident alert: {incident}\n\n"
                "Please triage this incident and determine the appropriate remediation."
            )
        }
    ]

    # Agent ReAct loop
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system_prompt,
            tools=TOOLS,
            messages=messages
        )

        # Process the response
        for block in response.content:
            if hasattr(block, "text"):
                print(f"[Agent Thought] {block.text}")

        # Check stop condition
        if response.stop_reason == "end_turn":
            print("\n[Agent] Triage complete.")
            break

        if response.stop_reason != "tool_use":
            print(f"[Agent] Unexpected stop reason: {response.stop_reason}")
            break

        # Process tool calls
        tool_results = []

        for block in response.content:
            if block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input

                print(
                    f"\n[Agent Action] Calling tool: "
                    f"{tool_name}({json.dumps(tool_input)})"
                )

                # Special handling for destructive action
                if tool_name == "execute_rollback":
                    approved, approver = request_human_approval(
                        f"execute_rollback on {tool_input.get('service')}"
                    )

                    if not approved:
                        tool_result = (
                            "Rollback DECLINED by operator. "
                            "Escalate to human on-call for manual intervention."
                        )
                    else:
                        tool_input["approved_by"] = approver
                        tool_result = execute_tool(tool_name, tool_input)

                else:
                    tool_result = execute_tool(tool_name, tool_input)

                print(f"[Tool Result] {tool_result}")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": tool_result
                })

        # Add assistant response and tool results to message history
        messages.append({
            "role": "assistant",
            "content": response.content
        })

        messages.append({
            "role": "user",
            "content": tool_results
        })

if __name__ == "__main__":
    incident_description = (
        "ALERT: payment-svc error rate has been above 5% for the past 4 minutes. "
        "This started approximately 8 minutes after a deployment. "
        "Cart-svc latency is also slightly elevated. "
        "Please investigate and remediate."
    )

    run_agent(incident_description)