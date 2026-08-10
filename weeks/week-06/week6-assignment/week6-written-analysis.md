# Week 6 Assignment — Self-Healing Payment Service

**Student:** Rod Raemon Alvero

## 1. Autonomy Boundary

The proposed self-healing payment service uses bounded autonomy rather than giving the SRE agent unrestricted control over production. The agent can automatically receive incident alerts, inspect metrics and logs, review deployment information, identify likely causes, and recommend a remediation. These actions are low-risk because they gather information or produce recommendations without directly changing the production environment.

The autonomy levels in the architecture are divided into clear stages. At L1, observability is automatic: metrics and logs are collected and made available for incident detection. At L2, the SRE agent analyzes the available evidence and recommends an action, such as rolling back `payment-svc` after detecting an error increase following a deployment. The agent may also perform non-destructive validation, such as a dry-run rollback, without requiring approval.

At L3, any action that changes the production environment requires explicit human approval. For example, the agent cannot execute a rollback of `payment-svc` simply because it believes the rollback is safe. It must present the proposed action to the human operator and wait for approval. If approval is denied, the agent should stop the automated remediation and escalate the incident for manual intervention.

The system also includes an L0 kill switch. This gives a human operator the ability to immediately disable agent actions if the agent behaves unexpectedly or if an emergency requires manual control. This boundary provides useful automation for repetitive incident investigation while keeping potentially destructive production changes under human authority.

## 2. Tool / API Surface

The SRE agent should have access only to a small, explicitly defined set of tools instead of receiving unrestricted access to the production environment. Each tool should follow least-privilege principles and provide only the permissions necessary for its specific task.

The agent uses `get_metrics` to retrieve service health information such as error rate, latency, and remaining error budget. This is a read-only operation and does not modify the environment. The `get_recent_logs` tool provides recent application logs so the agent can identify errors and patterns related to an incident. It is also read-only. The `get_deployment_history` tool allows the agent to determine which application version is currently running, what version was previously deployed, and whether a migration is pending.

For remediation, the agent has two separate rollback tools. The `dry_run_rollback` tool previews the rollback and verifies that the proposed action is safe without changing the production service. This tool can be called autonomously. The `execute_rollback` tool performs the actual production change and therefore has a much stronger restriction: it can only run after explicit human approval has been captured.

In a real Kubernetes implementation, these tools would be exposed through a controlled API or MCP server rather than giving the language model direct shell or unrestricted `kubectl` access. Read-only tools would use Kubernetes permissions such as `get`, `list`, and `watch` for approved resources. The remediation tool would receive narrowly scoped permission to modify only the intended deployment and namespace. Every tool invocation should also record the requested action, timestamp, target service, result, and human approver when applicable. This creates an auditable boundary between the agent's reasoning and the operations it is actually permitted to perform.

## 3. Failure-Mode Analysis

An agent-driven remediation system introduces failure modes that do not exist in a traditional alert-only system. One major risk is incorrect root-cause analysis. For example, the agent could see an increase in `payment-svc` errors after a deployment and incorrectly assume that the deployment caused the problem. To reduce this risk, the agent should correlate multiple sources such as metrics, logs, deployment history, and dependency health before recommending remediation.

A second failure mode is choosing an unsafe remediation. A rollback may appear appropriate but could cause additional problems if a database migration or incompatible dependency change occurred with the deployment. The system therefore requires a dry-run before rollback and should refuse autonomous remediation when a migration is pending or when the evidence is uncertain. In these situations, the incident should be escalated to the human on-call engineer.

Another risk is repeated or runaway remediation. An agent could continuously retry a rollback or repeatedly modify a service when the expected recovery does not occur. Rate limits, retry limits, action cooldown periods, and the kill switch should prevent this behavior. The system should also verify service health after a remediation instead of assuming that a successful API response means the incident has been resolved.

Tool failures are another concern. Metrics could be stale, logs could be incomplete, or an API could return an error. The agent should treat missing or contradictory evidence as uncertainty rather than inventing a conclusion. It should fail safely and escalate instead of taking a destructive action.

Finally, the language model itself could produce an unexpected tool request or incorrect parameters. Tool calls therefore need schema validation, allowlisted services and actions, least-privilege credentials, and an independent approval check outside the model. The human approval gate must be enforced by the orchestration layer so that a model cannot bypass it simply by generating an `execute_rollback` request.

## 4. Governance Plan

The self-healing system should operate under a governance model that defines who can authorize actions, what the agent is permitted to change, and how every decision is recorded. The agent should use least-privilege access and should only interact with approved services and tools. Read-only investigation can occur automatically, while production-changing actions such as rollback require explicit approval from an authorized human operator.

Every agent action should be auditable. The system should record the incident identifier, timestamp, evidence examined, tools called, proposed remediation, dry-run result, approval decision, approver identity, execution result, and post-remediation health status. These records would support incident reviews and make it possible to determine why an automated decision was made.

Access control should also be separated by responsibility. The language model should not directly possess unrestricted Kubernetes credentials. Instead, an orchestration or MCP layer should validate tool requests and enforce Kubernetes RBAC policies. The production namespace and permitted actions should be allowlisted. Human approval must also be enforced outside the model so that prompt instructions alone are never treated as a security boundary.

The governance plan should include operational limits. Rollbacks should have retry limits and cooldown periods, and repeated failures should automatically escalate to the on-call engineer. The kill switch must allow an authorized operator to immediately disable automated actions while preserving monitoring and diagnostic capabilities. Changes to the agent's prompts, tool definitions, permissions, or remediation policies should be version controlled and reviewed before deployment.

Finally, the organization should periodically review agent performance using metrics such as successful remediation rate, false recommendations, human approval and rejection rates, mean time to recovery, and the number of escalations. The agent should begin with limited permissions in a staging environment and receive greater production responsibility only after testing demonstrates reliable and predictable behavior.