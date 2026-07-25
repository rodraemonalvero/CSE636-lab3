# Week 3 Lab — Build-Fixer Agent with Human Approval Gate

## 1. Overview

This lab implements an AI-assisted Continuous Integration (CI) pipeline using Jenkins and Docker. The objective was to create a workflow where an AI build-fixer agent detects a failed build, analyzes the failure, proposes a correction, and requires human approval before the pipeline continues.

The project demonstrates how AI can assist developers during CI while maintaining safety through human review and clearly defined guardrails.

---

## 2. Pipeline Workflow

The implemented Jenkins pipeline performs the following steps:

1. Checkout the latest source code from GitHub.
2. Run the automated test suite.
3. Detect build or test failures.
4. Execute the AI remediation agent.
5. Generate a root cause analysis and proposed fix.
6. Pause the pipeline at a human approval gate.
7. Continue only after manual approval.

This workflow allows the AI agent to assist developers without automatically modifying or accepting code changes.

---

## 3. Intentional Build Failure

The project included an intentional defect in the calculator application to demonstrate the AI-assisted remediation workflow.

The incorrect implementation was:

```python
def add(a, b):
    return a - b
```

The correct implementation is:

```python
def add(a, b):
    return a + b
```

Running the test suite caused the build to fail, which triggered the AI remediation stage.

---

## 4. Evidence

The following screenshots demonstrate the workflow:

- Local test failure before remediation.
- Buggy calculator source code.
- AI remediation proposal.
- Jenkins human approval gate.
- Successful Jenkins pipeline execution.
- Jenkins dashboard.
- Docker containers running.

These screenshots document the complete AI-assisted CI workflow from failure detection through successful pipeline completion.

---

## 5. AI Agent Evaluation

The AI remediation agent correctly analyzed the build failure and identified the root cause before generating a proposed correction.

The generated `root_cause` accurately explained why the build failed, and the `fix_description` correctly described the required fix. The proposed remediation stayed within the intended scope and did not recommend unrelated changes to the application.

The pipeline paused at the human approval gate before continuing, allowing the proposed fix to be reviewed by a developer. This approval step prevents unsafe or incorrect changes from being accepted automatically.

---

## 6. Prompt and Guardrail Improvement

One improvement I would make is to further restrict the AI agent's system prompt so that it explicitly refuses to modify files outside the approved source directory or attempt to fix unsupported failure types.

I would also keep the human approval gate as a mandatory step. Even when the AI proposes a reasonable solution, a developer should always verify the proposed change before accepting it into the project.

These additional guardrails would further reduce the blast radius of the AI agent while maintaining developer control over the CI pipeline.

---

## 7. Conclusion

This lab demonstrated how an AI-assisted build-fixer agent can improve a Continuous Integration workflow by analyzing failed builds, explaining the root cause, proposing a correction, and requiring human approval before continuing.

The combination of AI assistance and human review provides a safer approach to automated software maintenance by improving developer productivity while preventing unintended changes from being applied automatically.