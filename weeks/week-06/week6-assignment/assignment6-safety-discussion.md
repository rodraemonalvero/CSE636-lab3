# Week 6 Assignment - Safety Discussion

**Student:** Rod Raemon Alvero

## Failure Modes

One important failure mode in my self-healing agent is incorrect root-cause analysis. The agent could observe a high error rate shortly after a deployment and incorrectly conclude that the new deployment caused the incident. For example, another dependency or infrastructure problem could be responsible even though the timing makes the deployment look suspicious. To reduce this risk, my agent checks multiple sources of evidence, including service metrics, recent logs, deployment history, and migration status before deciding that a rollback is appropriate.

Another failure mode is an unsafe or unnecessary rollback. A rollback could make the situation worse if a database migration is pending or if the previous application version is incompatible with the current environment. There is also a risk that the LLM could request the wrong tool or provide incorrect parameters. For this reason, destructive actions should never depend only on the model's reasoning.

## Blast-Radius Controls

My implementation uses multiple controls to limit the amount of damage the agent can cause. First, the agent performs a `dry_run_rollback` before attempting the real rollback. This allows the system to check the proposed action without changing the service. Second, the agent checks the remaining error budget and migration status before allowing remediation to continue.

The most important control is the human approval gate. Even when the agent concludes that rollback is appropriate, `execute_rollback` is blocked until a human explicitly approves the action. If the operator enters `no`, the rollback does not occur and the incident is escalated to the human on-call engineer. This prevents the LLM from independently making a destructive production change.

## Testing Before Production

Before connecting this agent to a real Kubernetes environment, I would first test it in a development or staging cluster using simulated incidents. I would test normal incidents as well as edge cases such as a pending migration, low error budget, failed dry run, incorrect service name, missing metrics, and conflicting evidence. I would also test both approval outcomes to confirm that `yes` permits the intended action and `no` always blocks it.

I would then verify post-remediation health checks to make sure the agent does not consider an incident resolved simply because the rollback command succeeded. The service metrics and logs should demonstrate actual recovery.

## Additional Production Guardrails

For production use, I would add Kubernetes RBAC with least-privilege permissions so the agent can modify only approved deployments and namespaces. The LLM should never receive unrestricted shell or `kubectl` access. I would also add service allowlists, schema validation for tool calls, rate limits, retry limits, cooldown periods, and complete audit logging.

Finally, I would maintain an emergency kill switch that immediately disables automated remediation while leaving monitoring available. Agent prompts, tool definitions, permissions, and remediation policies should be version controlled and reviewed before changes are deployed. These controls would allow the agent to reduce incident-response time while keeping high-impact production decisions under human supervision.