# MCP servers — CI build status

Two minimal [MCP](https://modelcontextprotocol.io) servers for the CSE636 Week 2
lab (Part 2). Each exposes "is my build green?" tools to an AI agent (Claude
Code) over stdio. They are intentionally **parallel** — same concept, two CI
backends — so you can see that MCP is CI-agnostic:

| Server | Backend | Tools | Auth scope |
|---|---|---|---|
| [`jenkins_status.py`](jenkins_status.py) | Local Jenkins REST API (`cstu-jenkins` on `http://localhost:8080`) | `list_jobs`, `get_build_status` | Jenkins user + API token |
| [`actions_status.py`](actions_status.py) | GitHub Actions REST API | `list_workflows`, `get_run_status` | GitHub PAT, `actions:read` on one repo |

Each server has a companion **test client** that spawns it over stdio, performs
the MCP handshake, and calls both tools — so you can verify end-to-end without
registering it in `claude.json`:

- [`test_jenkins_status.py`](test_jenkins_status.py)
- [`test_actions_status.py`](test_actions_status.py)

## Install

These servers run under the repo's **consolidated root `.venv`** (see the root
`requirements.txt`), which already includes `mcp` and `requests`:

```bash
# from the repo root
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Or install just what these servers need into an interpreter of your choice:

```bash
pip install mcp requests
```

## Jenkins server

Needs a running Jenkins and a user + API token
(Manage Jenkins → Users → *your user* → Security → API Token → Add new token).

```bash
# Run standalone — blocks on stdin waiting for MCP JSON-RPC (Ctrl-C to exit).
# This only confirms it launches without import errors.
JENKINS_URL=http://localhost:8080 JENKINS_USER=admin JENKINS_TOKEN=<token> \
  python jenkins_status.py

# Verify end-to-end (recommended): spawn + handshake + call both tools.
# Auto-loads JENKINS_* / JOB from project/.env if present.
JENKINS_URL=http://localhost:8080 JENKINS_USER=admin JENKINS_TOKEN=<token> \
  python test_jenkins_status.py
```

Expected:

```
Tools advertised: get_build_status, list_jobs

--- list_jobs ---
Jenkins jobs: ai-review-demo, ...

--- get_build_status (job=ai-review-demo) ---
Job 'ai-review-demo': build #24 — SUCCESS
```

Env: `JENKINS_URL`, `JENKINS_USER`, `JENKINS_TOKEN` (and `JOB` for the test
client, default `ai-review-demo`).

## GitHub Actions server

Needs a token with `actions:read` (a fine-grained PAT scoped to one repo is
ideal — least privilege) and `REPO` as `owner/name`.

```bash
GH_TOKEN=<token> REPO=<owner>/<repo> python actions_status.py           # standalone
GH_TOKEN=<token> REPO=<owner>/<repo> python test_actions_status.py      # end-to-end
# optional branch filter for get_run_status:
GH_TOKEN=<token> REPO=<owner>/<repo> BRANCH=main python test_actions_status.py
```

Env: `GH_TOKEN`, `REPO` (and `BRANCH` for the test client).

## Register with Claude Code

Register the server in one of three config scopes — pick by how widely you want
it available:

| Scope | File | Available in |
|---|---|---|
| **project** | `.mcp.json` at the repo root | anyone who opens this repo |
| user | `~/.claude.json` | every project on your machine |
| local | `.claude/settings.local.json` | just you, just this repo |

Create your own project-scoped `.mcp.json` at the **repo root** (it is
**gitignored** — see below — so it does not ship with the repo; each user
generates their own with the correct absolute paths for their machine):

```json
{
  "mcpServers": {
    "cse636-jenkins": {
      "command": "/absolute/path/to/CSE636/.venv/bin/python",
      "args": ["/absolute/path/to/CSE636/project/mcp_servers/jenkins_status.py"],
      "env": {
        "JENKINS_URL": "http://localhost:8080",
        "JENKINS_USER": "admin",
        "JENKINS_TOKEN": "${JENKINS_TOKEN}"
      }
    }
  }
}
```

**`.mcp.json` is gitignored** for two reasons: its `command`/`args` are
**absolute paths** specific to your machine, and it can hold secrets. Even so,
keep the token out of the file by using `"${JENKINS_TOKEN}"` — Claude Code
expands `${VAR}` from the environment at launch. Export the real token in your
shell (or `project/.env`, also gitignored) before starting Claude Code:

```bash
export JENKINS_TOKEN=<your-token>   # Manage Jenkins → your user → Security → API Token
```

Or let the CLI write `.mcp.json` for you instead of editing it by hand:

```bash
cd /path/to/CSE636
claude mcp add cse636-jenkins \
  --scope project \
  --env JENKINS_URL=http://localhost:8080 \
  --env JENKINS_USER=admin \
  --env JENKINS_TOKEN=$JENKINS_TOKEN \
  -- /path/to/CSE636/.venv/bin/python \
     /path/to/CSE636/project/mcp_servers/jenkins_status.py
```

**Pin `command` to the venv's Python** — don't use bare `"python"`. Claude Code
launches the server non-interactively, so a bare `python` resolves against
whatever `PATH` the Claude Code process inherited (almost never your activated
venv), and the server dies with `ModuleNotFoundError: No module named 'mcp'`.
Pointing `command` at `.venv/bin/python` by absolute path makes the interpreter
explicit and self-contained — for the same reason the server-script path must be
absolute. On Windows the interpreter is `.venv\Scripts\python.exe`.

**MCP servers load at session startup**, so a freshly added server does *not*
attach to a session that's already running — start a new `claude` session (or
`/mcp reconnect` in an interactive one). Verify with `claude mcp list` — it
should show `cse636-jenkins ✓ connected`.

Then: `claude "List all Jenkins jobs and tell me the status of the ai-review-demo job."`
A real tool call reports **live** state (actual job names + build number/result),
not a plausible guess. Sanity check: stop Jenkins and ask again — the call now
fails/empties, proving the agent queried live infrastructure.

## Notes

- **Entry point.** `stdio_server()` takes no arguments and yields a
  `(read, write)` stream pair; drive the server with
  `await app.run(read, write, app.create_initialization_options())`.
  `asyncio.run(stdio_server(app))` does **not** work — `stdio_server` is an
  async *context manager*, not a coroutine.
- **The test clients use `sys.executable`**, so the server subprocess runs under
  the same interpreter/venv where you installed `mcp` — no path mismatch. (The
  Claude Code **registration** has no such guarantee, which is why `command`
  must point at the venv Python explicitly — see above.)
- **Behind a TLS-inspecting proxy** (e.g. Zscaler), the GitHub server may hit
  `CERTIFICATE_VERIFY_FAILED` reaching `api.github.com`. The Jenkins server
  talks to `localhost` over plain HTTP and is unaffected. See the Week 2 lab's
  CA-trust note for the fix.
