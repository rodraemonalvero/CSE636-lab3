# Week 3 CI/CD Agent-in-the-Loop Demo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Week 3 class demo where Claude Code, given a requirements doc, drives local Jenkins through MCP tools to create a pipeline, produce a red build, diagnose it, apply a human-approved fix, verify green, and write a report.

**Architecture:** Extend the existing Jenkins MCP server (`jenkins_status.py`) with three write/read tools (`create_job`, `trigger_build`, `get_build_log`) so Claude Code can operate Jenkins entirely through MCP. Ship a fresh minimal Python app with a planted bug (the red build), a `REQUIREMENTS.md` that Claude Code reads to run the loop, and an instructor runbook under `weeks/week-03/`. Source is checked out from the class GitHub repo's `main` (mount-free); the fix is delivered by `git push`.

**Tech Stack:** Python 3 (stdlib + `pytest`), the `mcp` + `requests` libraries, Jenkins REST API, Jenkins declarative Pipeline, Markdown.

## Global Constraints

- **Jenkins access via MCP only** — in the demo narrative Claude Code must not call the Jenkins REST API directly; all Jenkins actions go through MCP tools.
- **Human approval gate is mandatory** — Claude Code proposes the fix as a diff and waits for instructor approval before applying/committing/pushing.
- **Minimal-fix only** — change the one line that fixes the bug; never delete, disable, or weaken tests to make the build pass; stop after 2 failed fix attempts and hand back to the human.
- **Mount-free** — no Docker volume/bind-mount edits; no recreating `cstu-jenkins`.
- **App uses Python standard library only** — no third-party runtime deps; `pytest` is pre-installed in the `cstu-jenkins` venv (Week 2 image), so the pipeline runs `pytest` with no `pip install`.
- **MCP server style** — reuse existing env (`JENKINS_URL`/`JENKINS_USER`/`JENKINS_TOKEN`), the `_auth()` helper, and error-string style (`Jenkins API error {code}.`).
- **Weeks conventions** — the runbook follows `weeks/README.md`: learning-path strip, 🎯 at-a-glance, `<details>` check-your-understanding, closing recap; diagrams are linked `.svg` (never inline SVG).
- **Commits** — the user handles git pushes and prefers to commit themselves. Commit steps below produce **local** commits; if the executor is not the user, stage the changes and pause for the user to commit rather than committing unprompted.
- **Branch** — work on `main` (current checkout).

---

## File Structure

- `project/ci-agent-demo/app/pricing.py` — fresh app; contains the planted bug.
- `project/ci-agent-demo/app/test_pricing.py` — 2 tests; 1 fails by design, 1 passes.
- `project/ci-agent-demo/REQUIREMENTS.md` — deliverable A; the agent's input spec.
- `project/ci-agent-demo/README.md` — orientation + the reset command.
- `project/ci-agent-demo/reports/.gitkeep` — where Claude Code writes `run-NN.md`.
- `project/mcp_servers/jenkins_status.py` — **extended** (+`_flow_definition_xml`, `_crumb`, `create_job`, `trigger_build`, `get_build_log`).
- `project/mcp_servers/test_flow_definition_xml.py` — pytest unit test for the pure XML helper.
- `project/mcp_servers/test_jenkins_status.py` — **extended** with a gated write self-test.
- `weeks/week-03/week-03-demo.md` — deliverable B; instructor runbook.
- `CLAUDE.md` — add `project/ci-agent-demo/` to the project inventory.

---

## Task 1: Fresh minimal app with a planted bug

**Files:**
- Create: `project/ci-agent-demo/app/pricing.py`
- Create: `project/ci-agent-demo/app/test_pricing.py`

**Interfaces:**
- Produces: `pricing.item_total(price: float, quantity: int) -> float` (buggy: returns `price + quantity`; correct: `price * quantity`); `pricing.apply_tax(amount: float, rate: float) -> float` (correct).

- [ ] **Step 1: Write the app with the planted bug**

Create `project/ci-agent-demo/app/pricing.py`:

```python
"""Tiny pricing helpers for the Week 3 CI/CD agent demo.

`item_total` contains a deliberate bug (it adds instead of multiplies) so the
CI build goes red. The agent's job is to find and fix exactly this one line.
"""


def item_total(price, quantity):
    """Total cost of `quantity` units at `price` each."""
    return price + quantity  # BUG: should be price * quantity


def apply_tax(amount, rate):
    """Apply a tax `rate` (e.g. 0.08 for 8%) to `amount`, rounded to cents."""
    return round(amount * (1 + rate), 2)
```

- [ ] **Step 2: Write the tests (one fails by design, one passes)**

Create `project/ci-agent-demo/app/test_pricing.py`:

```python
from pricing import item_total, apply_tax


def test_item_total():
    # 4 units at $3.00 should cost $12.00. Fails while item_total adds.
    assert item_total(3.0, 4) == 12.0


def test_apply_tax():
    assert apply_tax(100.0, 0.08) == 108.0
```

- [ ] **Step 3: Run the tests and confirm exactly one fails**

Run: `cd project/ci-agent-demo/app && python3 -m pytest -q`
Expected: `1 failed, 1 passed` — `test_item_total` fails with `assert 7.0 == 12.0`, `test_apply_tax` passes.

- [ ] **Step 4: Confirm the fix would make it green (then revert)**

Run:
```bash
cd project/ci-agent-demo/app
sed -i.bak 's/return price + quantity.*/return price * quantity/' pricing.py && python3 -m pytest -q; mv pricing.py.bak pricing.py
```
Expected: with the temporary edit, `2 passed`; then the `mv` restores the buggy file. Confirm `git status` shows `pricing.py` back to the buggy version (no `.bak` left).

- [ ] **Step 5: Commit**

```bash
git add project/ci-agent-demo/app/pricing.py project/ci-agent-demo/app/test_pricing.py
git commit -m "feat(ci-agent-demo): add pricing app with planted bug + tests"
```

---

## Task 2: Pure `_flow_definition_xml` helper (unit-tested)

**Files:**
- Modify: `project/mcp_servers/jenkins_status.py`
- Test: `project/mcp_servers/test_flow_definition_xml.py`

**Interfaces:**
- Produces: `_flow_definition_xml(pipeline_script: str) -> str` — returns a Jenkins Pipeline job `config.xml` string embedding `pipeline_script` as an inline CPS (sandboxed) definition. XML-escapes the script.

- [ ] **Step 1: Write the failing test**

Create `project/mcp_servers/test_flow_definition_xml.py`:

```python
from jenkins_status import _flow_definition_xml


def test_embeds_script_and_structure():
    xml = _flow_definition_xml("pipeline { agent any }")
    assert xml.lstrip().startswith("<?xml")
    assert "<flow-definition" in xml
    assert "CpsFlowDefinition" in xml
    assert "<sandbox>true</sandbox>" in xml
    assert "pipeline { agent any }" in xml


def test_escapes_xml_special_chars():
    xml = _flow_definition_xml("echo '<a> & <b>'")
    # The angle brackets from the script must be escaped so the XML stays valid.
    assert "<a>" not in xml.replace("<flow-definition", "").replace("<definition", "")
    assert "&lt;a&gt;" in xml
    assert "&amp;" in xml
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest project/mcp_servers/test_flow_definition_xml.py -q`
Expected: FAIL — `ImportError: cannot import name '_flow_definition_xml'`.

- [ ] **Step 3: Implement the helper**

In `project/mcp_servers/jenkins_status.py`, add `import html` near the top imports, and add this function just after the `_auth()` helper:

```python
def _flow_definition_xml(pipeline_script):
    """Build config.xml for a Pipeline job with an inline (CPS) script."""
    escaped = html.escape(pipeline_script)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<flow-definition plugin="workflow-job">\n'
        '  <definition class="org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition"'
        ' plugin="workflow-cps">\n'
        f"    <script>{escaped}</script>\n"
        "    <sandbox>true</sandbox>\n"
        "  </definition>\n"
        "  <triggers/>\n"
        "</flow-definition>\n"
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest project/mcp_servers/test_flow_definition_xml.py -q`
Expected: PASS (2 passed). The consolidated root `.venv` already has `mcp` (importing `jenkins_status` pulls it in); the helper itself needs no network.

- [ ] **Step 5: Commit**

```bash
git add project/mcp_servers/jenkins_status.py project/mcp_servers/test_flow_definition_xml.py
git commit -m "feat(mcp): add pure _flow_definition_xml pipeline-config helper"
```

---

## Task 3: `_crumb` helper + `create_job` MCP tool

**Files:**
- Modify: `project/mcp_servers/jenkins_status.py`
- Modify: `project/mcp_servers/test_jenkins_status.py`

**Interfaces:**
- Consumes: `_flow_definition_xml` (Task 2), `_auth()`, `JENKINS_URL`.
- Produces: `_crumb() -> dict` (CSRF header dict, `{}` if disabled); MCP tool `create_job(name: str, pipeline_script: str)` — creates the job, or updates its config if it already exists; returns `Job '<name>' created.`/`updated.`.

- [ ] **Step 1: Implement the crumb helper**

In `jenkins_status.py`, add after `_auth()`:

```python
def _crumb():
    """Return a CSRF crumb header dict for POSTs ({} if crumbs are disabled)."""
    try:
        resp = requests.get(
            f"{JENKINS_URL}/crumbIssuer/api/json", auth=_auth(), timeout=10
        )
    except requests.RequestException:
        return {}
    if resp.status_code != 200:
        return {}
    data = resp.json()
    return {data["crumbRequestField"]: data["crumb"]}
```

- [ ] **Step 2: Register the `create_job` tool in `list_tools`**

In `jenkins_status.py`, add this `Tool(...)` entry to the list returned by `list_tools()` (before `list_jobs`):

```python
        Tool(
            name="create_job",
            description=(
                "Creates (or updates) a Jenkins Pipeline job from an inline "
                "pipeline script. Use this to stand up a CI pipeline. If the job "
                "already exists, its configuration is updated."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Job name, e.g. 'ci-agent-demo'.",
                    },
                    "pipeline_script": {
                        "type": "string",
                        "description": "The declarative Jenkinsfile text to run.",
                    },
                },
                "required": ["name", "pipeline_script"],
            },
        ),
```

- [ ] **Step 3: Implement the `create_job` branch in `call_tool`**

In `jenkins_status.py`, add at the top of `call_tool` (before the `list_jobs` branch):

```python
    if name == "create_job":
        job = arguments["name"]
        xml = _flow_definition_xml(arguments["pipeline_script"]).encode("utf-8")
        headers = {"Content-Type": "application/xml", **_crumb()}
        exists = (
            requests.get(
                f"{JENKINS_URL}/job/{job}/api/json", auth=_auth(), timeout=10
            ).status_code
            == 200
        )
        if exists:
            resp = requests.post(
                f"{JENKINS_URL}/job/{job}/config.xml",
                data=xml, headers=headers, auth=_auth(), timeout=10,
            )
            verb = "updated"
        else:
            resp = requests.post(
                f"{JENKINS_URL}/createItem", params={"name": job},
                data=xml, headers=headers, auth=_auth(), timeout=10,
            )
            verb = "created"
        if resp.status_code not in (200, 201):
            return [TextContent(type="text", text=f"Jenkins API error {resp.status_code} on create_job.")]
        return [TextContent(type="text", text=f"Job '{job}' {verb}.")]
```

- [ ] **Step 4: Add a gated write self-test to the test client**

In `project/mcp_servers/test_jenkins_status.py`, after the existing `get_build_status` call inside `main()`, add:

```python
            if os.environ.get("MCP_WRITE_TEST") == "1":
                print("\n--- create_job (self-test) ---")
                script = (
                    "pipeline { agent any stages { stage('Hello') "
                    "{ steps { echo 'hello-from-mcp' } } } }"
                )
                print(_text(await session.call_tool(
                    "create_job",
                    {"name": "mcp-selftest", "pipeline_script": script},
                )))
```

- [ ] **Step 5: Verify against live Jenkins**

Precondition: `cstu-jenkins` running and `JENKINS_*` in `project/.env`.
Run (from the repo root, using the consolidated root `.venv`):
```bash
MCP_WRITE_TEST=1 .venv/bin/python project/mcp_servers/test_jenkins_status.py
```
Expected: prints `Tools advertised: ... create_job ...`, then `Job 'mcp-selftest' created.` Confirm in the Jenkins UI (http://localhost:8080) that a `mcp-selftest` pipeline job now exists. Re-running prints `Job 'mcp-selftest' updated.`

- [ ] **Step 6: Commit**

```bash
git add project/mcp_servers/jenkins_status.py project/mcp_servers/test_jenkins_status.py
git commit -m "feat(mcp): add _crumb helper and create_job tool"
```

---

## Task 4: `trigger_build` + `get_build_log` MCP tools

**Files:**
- Modify: `project/mcp_servers/jenkins_status.py`
- Modify: `project/mcp_servers/test_jenkins_status.py`

**Interfaces:**
- Consumes: `_crumb()`, `_auth()`, `JENKINS_URL`; existing `get_build_status`.
- Produces: MCP tools `trigger_build(job_name: str)` (returns a "triggered" message) and `get_build_log(job_name: str)` (returns the last build's console text, tail-truncated to 8000 chars).

- [ ] **Step 1: Register both tools in `list_tools`**

In `jenkins_status.py`, add these two `Tool(...)` entries to `list_tools()`:

```python
        Tool(
            name="trigger_build",
            description=(
                "Triggers a build of a Jenkins job. Returns immediately; poll "
                "get_build_status for the result."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "job_name": {"type": "string", "description": "The job to build."}
                },
                "required": ["job_name"],
            },
        ),
        Tool(
            name="get_build_log",
            description=(
                "Returns the console log of the most recent build of a job. Use "
                "this to diagnose why a build failed."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "job_name": {"type": "string", "description": "The job name."}
                },
                "required": ["job_name"],
            },
        ),
```

- [ ] **Step 2: Implement both branches in `call_tool`**

In `jenkins_status.py`, add after the `create_job` branch:

```python
    if name == "trigger_build":
        job = arguments["job_name"]
        resp = requests.post(
            f"{JENKINS_URL}/job/{job}/build", headers=_crumb(), auth=_auth(), timeout=10
        )
        if resp.status_code not in (200, 201, 302):
            return [TextContent(type="text", text=f"Jenkins API error {resp.status_code} on trigger_build.")]
        return [TextContent(
            type="text",
            text=f"Build triggered for '{job}'. Poll get_build_status for the result.",
        )]

    if name == "get_build_log":
        job = arguments["job_name"]
        resp = requests.get(
            f"{JENKINS_URL}/job/{job}/lastBuild/consoleText", auth=_auth(), timeout=10
        )
        if resp.status_code == 404:
            return [TextContent(type="text", text=f"No builds found for '{job}'.")]
        if resp.status_code != 200:
            return [TextContent(type="text", text=f"Jenkins API error {resp.status_code}.")]
        log = resp.text
        if len(log) > 8000:
            log = "...(truncated)...\n" + log[-8000:]
        return [TextContent(type="text", text=log)]
```

- [ ] **Step 3: Extend the write self-test to trigger + poll + read the log**

In `test_jenkins_status.py`, add `import asyncio` if not already imported (it is), and inside the `MCP_WRITE_TEST` block after the `create_job` call, add:

```python
                print("\n--- trigger_build (self-test) ---")
                print(_text(await session.call_tool(
                    "trigger_build", {"job_name": "mcp-selftest"})))

                # Poll until the build leaves IN_PROGRESS (bounded).
                status = ""
                for _ in range(15):
                    await asyncio.sleep(2)
                    status = _text(await session.call_tool(
                        "get_build_status", {"job_name": "mcp-selftest"}))
                    if "IN_PROGRESS" not in status:
                        break
                print("status:", status)

                print("\n--- get_build_log (self-test) ---")
                log = _text(await session.call_tool(
                    "get_build_log", {"job_name": "mcp-selftest"}))
                print("contains 'hello-from-mcp':", "hello-from-mcp" in log)
```

- [ ] **Step 4: Verify against live Jenkins**

Run (from the repo root):
```bash
MCP_WRITE_TEST=1 .venv/bin/python project/mcp_servers/test_jenkins_status.py
```
Expected: `Build triggered for 'mcp-selftest'.`, then `status:` showing `build #1 — SUCCESS` (may take a few seconds), then `contains 'hello-from-mcp': True`.

- [ ] **Step 5: Clean up the self-test job (optional) and commit**

Optionally delete the scratch job in the Jenkins UI (`mcp-selftest` → Delete Pipeline). Then:
```bash
git add project/mcp_servers/jenkins_status.py project/mcp_servers/test_jenkins_status.py
git commit -m "feat(mcp): add trigger_build and get_build_log tools"
```

---

## Task 5: `REQUIREMENTS.md` — the agent's input spec (deliverable A)

**Files:**
- Create: `project/ci-agent-demo/REQUIREMENTS.md`

- [ ] **Step 1: Write the requirements document**

Create `project/ci-agent-demo/REQUIREMENTS.md` with this content:

````markdown
# CI/CD Agent-in-the-Loop — Requirements

You are an autonomous CI/CD engineer operating **local Jenkins** through MCP
tools. Read this document, then execute the loop below. Do not touch Jenkins
any way other than the MCP tools listed.

## Objective

Stand up a CI pipeline for the app in `app/`, drive it to a failing (red)
build, diagnose the failure, apply a **human-approved** minimal fix, and prove
the pipeline goes green — then write a report.

## Success criteria

1. A Jenkins pipeline job named `ci-agent-demo` exists (you create it).
2. Build #1 is RED (the app has a failing test).
3. You correctly identify the failing test and its root cause from the log.
4. You propose a minimal fix and **wait for human approval** before applying it.
5. After approval and a `git push`, a fresh build is GREEN.
6. You write `reports/run-NN.md` (next unused number) summarizing the run.

## Constraints

- **Jenkins only via MCP tools:** `create_job`, `trigger_build`,
  `get_build_status`, `get_build_log`, `list_jobs`. No curl, no REST, no UI.
- **Human approval gate is mandatory.** Present the fix as a diff and stop.
  Do not edit, commit, or push until the instructor approves in the chat.
- **Minimal fix only.** Change the single line that is wrong. Never edit,
  delete, disable, `skip`, or weaken a test to make the build pass.
- **Stop after 2 failed fix attempts** and hand back to the human.

## Pipeline contract

Create `ci-agent-demo` with an inline declarative pipeline that:
1. Checks out the class repo on `main`:
   `git branch: 'main', url: '<CLASS_REPO_HTTPS_URL>'` (add
   `credentialsId: 'github-https'` only if the repo is private).
2. Runs the tests and surfaces failures as a red build:
   `dir('project/ci-agent-demo/app') { sh 'python3 -m pytest -q' }`.

Use `agent any` (single-container `cstu-jenkins`).

## Agent loop

1. Author the Jenkinsfile above; `create_job('ci-agent-demo', <script>)`.
2. `trigger_build('ci-agent-demo')`; poll `get_build_status` until it is not
   IN_PROGRESS.
3. If RED: `get_build_log('ci-agent-demo')`; identify the failing test + cause.
4. Propose the minimal fix as a unified diff. **Wait for approval.**
5. On approval: edit the source, `git commit`, `git push origin main`.
6. `trigger_build` again; poll until GREEN.
7. Write the report (see below). If still red after a 2nd attempt, stop.

## Report format (`reports/run-NN.md`)

```
# CI Agent Run NN — <UTC timestamp>

- Job: ci-agent-demo
- Build #1: <result>   Build #2: <result>

## Failure
- Test: <name>
- Assertion: <what failed>
- Root cause: <one sentence>

## Fix (approved by instructor)
<diff>
Rationale: <one sentence>

## Verification
Build #2: <result> — <n passed>

## MCP calls (audit trail)
- create_job, trigger_build, get_build_status × N, get_build_log, ...
```
````

- [ ] **Step 2: Verify the referenced tool names and paths are correct**

Run: `grep -n "create_job\|trigger_build\|get_build_log\|get_build_status\|list_jobs" project/ci-agent-demo/REQUIREMENTS.md`
Expected: every tool named here exists in `jenkins_status.py` (cross-check with `grep '"name":' project/mcp_servers/jenkins_status.py`). Confirm the app path `project/ci-agent-demo/app` matches Task 1.

- [ ] **Step 3: Commit**

```bash
git add project/ci-agent-demo/REQUIREMENTS.md
git commit -m "docs(ci-agent-demo): add REQUIREMENTS.md agent input spec"
```

---

## Task 6: `README.md` + reports dir + reset command

**Files:**
- Create: `project/ci-agent-demo/README.md`
- Create: `project/ci-agent-demo/reports/.gitkeep`

- [ ] **Step 1: Create the reports directory placeholder**

```bash
mkdir -p project/ci-agent-demo/reports
touch project/ci-agent-demo/reports/.gitkeep
```

- [ ] **Step 2: Write the README**

Create `project/ci-agent-demo/README.md`:

````markdown
# CI/CD Agent-in-the-Loop Demo — Week 3

Claude Code, given [`REQUIREMENTS.md`](REQUIREMENTS.md), operates **local
Jenkins** through MCP tools to: create a pipeline, produce a red build, diagnose
it, apply a **human-approved** fix, and verify the build goes green — then write
a report to [`reports/`](reports/).

This is the Claude-Code-native companion to [`../build-fixer/`](../build-fixer/)
(which uses a hand-written SDK script + a Jenkins `input` gate). Here the agent
*operates* the CI system through a tool interface, with the human approving the
one change that matters.

## Layout

| Path | What it is |
|---|---|
| `REQUIREMENTS.md` | The spec Claude Code reads to run the loop |
| `app/pricing.py` | Tiny app with a planted bug (`item_total` adds instead of multiplies) |
| `app/test_pricing.py` | 2 tests — 1 fails by design, 1 passes |
| `reports/` | Claude Code writes `run-NN.md` here |

## Run it

See the instructor runbook: [`weeks/week-03/week-03-demo.md`](../../weeks/week-03/week-03-demo.md).
The Jenkins MCP server it uses is
[`../mcp_servers/jenkins_status.py`](../mcp_servers/jenkins_status.py).

## Reset (re-arm the demo)

After a run, `main` holds the fixed code. To re-arm the bug for another run,
restore the buggy line and push:

```bash
cd project/ci-agent-demo/app
python3 -c "import pathlib,re; p=pathlib.Path('pricing.py'); \
p.write_text(p.read_text().replace('return price * quantity','return price + quantity  # BUG: should be price * quantity'))"
python3 -m pytest -q          # expect: 1 failed, 1 passed
git commit -am "chore(ci-agent-demo): re-arm planted bug" && git push origin main
```

This is also the "prove it's real" check: revert the fix, re-run the pipeline,
and watch it go red again.
````

- [ ] **Step 3: Verify the reset command round-trips**

Run:
```bash
cd project/ci-agent-demo/app
# simulate a fixed tree, then run the reset from the README
sed -i.bak 's/return price + quantity.*/return price * quantity/' pricing.py && rm pricing.py.bak
python3 -c "import pathlib; p=pathlib.Path('pricing.py'); p.write_text(p.read_text().replace('return price * quantity','return price + quantity  # BUG: should be price * quantity'))"
python3 -m pytest -q
```
Expected: `1 failed, 1 passed` (bug is back). Confirm `git diff` on `pricing.py` is empty (identical to the committed buggy version).

- [ ] **Step 4: Commit**

```bash
git add project/ci-agent-demo/README.md project/ci-agent-demo/reports/.gitkeep
git commit -m "docs(ci-agent-demo): add README and reports dir"
```

---

## Task 7: Instructor runbook `week-03-demo.md` (deliverable B)

**Files:**
- Create: `weeks/week-03/week-03-demo.md`

**Interfaces:**
- Consumes: the MCP tools (Tasks 3–4), `REQUIREMENTS.md` (Task 5), the app (Task 1).

- [ ] **Step 1: Write the runbook**

Create `weeks/week-03/week-03-demo.md`:

````markdown
# Week 3 — Class Demo: Claude Code as the CI/CD Agent in the Loop

![Course learning path with Week 3 (CI/CD) highlighted: 0 Setup, 1 Basics, 2 Tooling, 3 CI/CD, 4 Predict, 5 Observe, 6 Respond, 7 Govern.](images/learning-path.svg)

> 📎 **Supplementary demo for Week 3.** The lecture notes are in
> [week-03-notes.md](week-03-notes.md) and the graded lab in
> [week-03-lab.md](week-03-lab.md). This runbook is a **live instructor demo**:
> Claude Code operates local Jenkins through MCP tools to run a full red→green
> CI/CD loop with a human approval gate.

> 🎯 **At a glance**
>
> | | |
> |---|---|
> | **Prerequisites** | Week 2 Jenkins (`cstu-jenkins`) + the Jenkins MCP server registered in Claude Code |
> | **Time budget** | ~10 min live |
> | **What the class sees** | An agent create a pipeline, hit a red build, diagnose it, ask permission, fix it, and prove it green |
> | **Ties into** | [`project/ci-agent-demo/`](../../project/ci-agent-demo/) and [`jenkins_status.py`](../../project/mcp_servers/jenkins_status.py) |

---

## What the class will see

Claude Code, handed [`REQUIREMENTS.md`](../../project/ci-agent-demo/REQUIREMENTS.md),
drives the whole CI/CD lifecycle against local Jenkins **through MCP tools**:

1. Generates a `Jenkinsfile` and **creates** the pipeline job.
2. **Triggers** build #1 → it goes **red** (the app has a planted bug).
3. Reads the **console log**, diagnoses the failing test.
4. Proposes a minimal fix and **pauses for your approval**. 🚦
5. On approval, pushes the fix and re-runs → **green**.
6. Writes a summary report.

The teaching point: the agent *operates* CI/CD the way an engineer would, but
you keep control at the one decision that matters.

---

## Part A — Setup (once, before class)

**A1. Jenkins up.** Confirm `cstu-jenkins` runs at http://localhost:8080
(Week 2). `docker ps` should list it.

**A2. Jenkins API token.** Manage Jenkins → Users → *your user* → Security →
API Token → Add new token. Put credentials in `project/.env`
(gitignored):

```
JENKINS_URL=http://localhost:8080
JENKINS_USER=<user>
JENKINS_TOKEN=<token>
```

**A3. Register the MCP server** in `~/.claude.json` (absolute paths). Point
`command` at the **consolidated root `.venv`** Python so `mcp` resolves (a bare
`python` dies with `ModuleNotFoundError: No module named 'mcp'`):

```json
{
  "mcpServers": {
    "cse636-jenkins": {
      "command": "/absolute/path/to/CSE636/.venv/bin/python",
      "args": ["/absolute/path/to/CSE636/project/mcp_servers/jenkins_status.py"],
      "env": {
        "JENKINS_URL": "http://localhost:8080",
        "JENKINS_USER": "<user>",
        "JENKINS_TOKEN": "<token>"
      }
    }
  }
}
```

**A4. Smoke-test the MCP write tools** (creates + builds a throwaway job):

```bash
MCP_WRITE_TEST=1 .venv/bin/python project/mcp_servers/test_jenkins_status.py
```

Expect `Job 'mcp-selftest' created.`, a `SUCCESS` status, and
`contains 'hello-from-mcp': True`. Delete `mcp-selftest` in the UI afterward.

**A5. Demo project on `main`.** Ensure `project/ci-agent-demo/` (with the
planted bug) is committed and pushed to the class GitHub repo's `main`, and that
you have local `git push` rights (a PAT via your git credential helper). Edit
the repo URL in `REQUIREMENTS.md`'s pipeline contract to your class repo.

**A6. Confirm the bug is armed:**
`cd project/ci-agent-demo/app && python3 -m pytest -q` → `1 failed, 1 passed`.

---

## Part B — Run it live

**B1. Kick off Claude Code** in the repo root:

```
Read project/ci-agent-demo/REQUIREMENTS.md and run the CI/CD agent loop.
Use only the Jenkins MCP tools. Stop and ask me to approve before you apply
any fix.
```

**B2. Narrate as it works:**

- It authors a `Jenkinsfile` and calls `create_job` → point out *no UI clicks*.
- It calls `trigger_build`, then `get_build_status` a few times → the build is red.
- It calls `get_build_log` and reads the pytest failure.

**B3. The approval gate.** 🚦 Claude Code shows the one-line diff
(`price + quantity` → `price * quantity`) and stops. This is the moment: ask
the class *"should we let it push?"* Then approve.

**B4. Green.** Claude Code pushes to `main`, re-triggers, polls to `SUCCESS`,
and writes `project/ci-agent-demo/reports/run-NN.md`. Open the report.

**B5. Prove it's real.** Run the reset from the
[demo README](../../project/ci-agent-demo/README.md#reset-re-arm-the-demo),
re-trigger, and watch the build go red again — proof the agent was operating
live infrastructure, not narrating.

<details><summary>✅ Did it work? What "success" looks like</summary>

- A `ci-agent-demo` job exists that you never created by hand.
- Build #1 = red, build #2 = green, both visible in the Jenkins UI.
- The fix was pushed **only after** you approved it.
- The report names the failing test, the root cause, and the exact fix.

If Claude Code answers without calling tools, re-check A3 (absolute path) and
A4. If `create_job`/`trigger_build` error, re-check the API token (A2) and that
Jenkins is up (A1).

</details>

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Jenkins API error 403` on create/trigger | CSRF crumb / token issue — re-check A2; the MCP server fetches a crumb automatically |
| Build stays `IN_PROGRESS` forever | No executor free, or a syntax error in the generated Jenkinsfile — open the job's console in the UI |
| Checkout fails in the build | Repo URL wrong in `REQUIREMENTS.md`, or a private repo needs a `github-https` credential |
| `git push` rejected | Local PAT missing/expired; the fix only lands once push succeeds |

---

## Recap

- An agent can *operate* CI/CD, not just write code — creating jobs, triggering
  builds, and reading logs through a small MCP tool surface.
- The **human approval gate** is what makes this safe: the blast radius of an
  autonomous agent is bounded by where you require a human "yes."
- Everything ran on **local Jenkins**, mount-free, with the fix delivered by an
  ordinary `git push`.

➡️ Next: [Week 4 — Predict](../week-04/week-04-notes.md).
````

- [ ] **Step 2: Verify links and conventions**

Run: `grep -n "](.*)" weeks/week-03/week-03-demo.md`
Expected: relative links resolve — `images/learning-path.svg` exists (`ls weeks/week-03/images/learning-path.svg`), `../../project/ci-agent-demo/REQUIREMENTS.md` and `../../project/mcp_servers/jenkins_status.py` exist. Confirm the file opens with the learning-path strip and 🎯 at-a-glance and closes with a recap (per weeks conventions).

- [ ] **Step 3: Commit**

```bash
git add weeks/week-03/week-03-demo.md
git commit -m "docs(week-03): add CI/CD agent-in-the-loop instructor runbook"
```

---

## Task 8: Update `CLAUDE.md` project inventory

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add the new project to the inventory**

In `CLAUDE.md`, in the "Executable code lives under `project/`" list, add a bullet after the `project/build-fixer/` entry:

```markdown
- `project/ci-agent-demo/` — Week 3 (class demo): Claude Code as the CI/CD **agent in the loop**. Given `REQUIREMENTS.md`, Claude Code drives local Jenkins **only through MCP tools** (`create_job`/`trigger_build`/`get_build_log` added to `mcp_servers/jenkins_status.py`) to create a pipeline, produce a red build (a planted bug in `app/pricing.py`), diagnose it, apply a **human-approved** minimal fix, push to `main`, verify green, and write `reports/run-NN.md`. Mount-free; checks out the class repo over GitHub. Runbook: `weeks/week-03/week-03-demo.md`.
```

- [ ] **Step 2: Verify**

Run: `grep -n "ci-agent-demo" CLAUDE.md`
Expected: the new bullet is present under the `project/` inventory.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add ci-agent-demo to CLAUDE.md project inventory"
```

---

## Task 9: Full-loop rehearsal (manual verification)

**Files:** none (verification only).

This task proves the whole demo works before class. Requires `cstu-jenkins` up,
`.env` creds, the MCP server registered, and `project/ci-agent-demo/` pushed to
the class repo `main` (Task 5/6 committed + pushed).

- [ ] **Step 1: Arm the bug**

Run: `cd project/ci-agent-demo/app && python3 -m pytest -q`
Expected: `1 failed, 1 passed`.

- [ ] **Step 2: Run the loop through Claude Code**

In a Claude Code session at the repo root, paste the B1 kickoff prompt from the
runbook. Watch for: `create_job` → `trigger_build` → red `get_build_status` →
`get_build_log` → **a diff + a pause for approval**.

- [ ] **Step 3: Approve and confirm green**

Approve the fix. Confirm Claude Code pushes to `main`, re-triggers, and reaches
`SUCCESS`, and that `project/ci-agent-demo/reports/run-01.md` was written and
names the failing test + fix.

- [ ] **Step 4: Reset**

Run the reset from `project/ci-agent-demo/README.md`; confirm the build goes red
again on the next trigger. The demo is now re-armed.

- [ ] **Step 5: Record the rehearsal**

No commit (the report + any fix commit are demo artifacts). Note any runbook
corrections discovered during rehearsal and fold them back into
`weeks/week-03/week-03-demo.md`.

---

## Self-Review (completed by plan author)

- **Spec coverage:** §4.1 MCP tools → Tasks 2–4; §4.2 app → Task 1; §4.3 pipeline → embedded in `REQUIREMENTS.md` (Task 5) and runbook (Task 7); §4.4 agent loop → Task 5; §4.5 report → Task 5; §5.1 REQUIREMENTS.md → Task 5; §5.2 runbook → Task 7; §5.3 README → Task 6; §6 layout → Tasks 1/6; §7 prerequisites → runbook Part A; CLAUDE.md hygiene → Task 8; verification → Task 9. No gaps.
- **Placeholder scan:** `<CLASS_REPO_HTTPS_URL>`, `<user>`, `<token>`, `run-NN` are intentional per-site values the instructor fills — each is called out where it appears, not a hidden TODO.
- **Type consistency:** tool names (`create_job`, `trigger_build`, `get_build_log`, `get_build_status`, `list_jobs`) and the helper `_flow_definition_xml` / `_crumb` are used identically across Tasks 2–7 and `REQUIREMENTS.md`.
