#!/usr/bin/env python3
"""
Standalone MCP client smoke test for jenkins_status.py.
CSE636 Week 2 Lab — verify the server end-to-end without touching claude.json.

It spawns jenkins_status.py as a subprocess over stdio (exactly how Claude Code
would), performs the MCP handshake, lists the advertised tools, and then calls
`list_jobs` and `get_build_status` — printing whatever the live local Jenkins
REST API returns.

Install: pip install mcp requests
Env (same as the server):
  JENKINS_URL    e.g. "http://localhost:8080"
  JENKINS_USER   e.g. "admin"
  JENKINS_TOKEN  API token
  JOB            job name to check with get_build_status (default: ai-review-demo)

Run:
  JENKINS_URL=http://localhost:8080 JENKINS_USER=admin JENKINS_TOKEN=<token> \
    python test_jenkins_status.py
  # or target a specific job:
  ... JOB=my-job python test_jenkins_status.py
"""
import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "jenkins_status.py")

# Best-effort: load JENKINS_* from project/.env if python-dotenv is
# available. Real env vars still win over .env.
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(HERE), ".env"))
except ImportError:
    pass


def _text(result):
    """Flatten an MCP call_tool result into a plain string."""
    parts = []
    for block in result.content:
        parts.append(getattr(block, "text", str(block)))
    return "\n".join(parts)


async def main():
    if not os.environ.get("JENKINS_URL"):
        print("Set JENKINS_URL (and JENKINS_USER / JENKINS_TOKEN) before running.", file=sys.stderr)
        return 1

    # Run the server with the same interpreter and pass our env through so it
    # sees JENKINS_URL / JENKINS_USER / JENKINS_TOKEN.
    params = StdioServerParameters(
        command=sys.executable,
        args=[SERVER],
        env=os.environ.copy(),
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Tools advertised:", ", ".join(t.name for t in tools.tools))

            print("\n--- list_jobs ---")
            print(_text(await session.call_tool("list_jobs", {})))

            job = os.environ.get("JOB", "ai-review-demo")
            print(f"\n--- get_build_status (job={job}) ---")
            print(_text(await session.call_tool("get_build_status", {"job_name": job})))

            if os.environ.get("MCP_WRITE_TEST") == "1":
                print("\n--- create_job (self-test) ---")
                script = (
                    "pipeline {\n"
                    "  agent any\n"
                    "  stages {\n"
                    "    stage('Hello') {\n"
                    "      steps {\n"
                    "        echo 'hello-from-mcp'\n"
                    "      }\n"
                    "    }\n"
                    "  }\n"
                    "}\n"
                )
                print(_text(await session.call_tool(
                    "create_job",
                    {"name": "mcp-selftest", "pipeline_script": script},
                )))

                print("\n--- trigger_build (self-test) ---")
                print(_text(await session.call_tool(
                    "trigger_build", {"job_name": "mcp-selftest"})))

                # Poll until the build leaves IN_PROGRESS (bounded).
                status = ""
                for _ in range(15):
                    await asyncio.sleep(2)
                    status = _text(await session.call_tool(
                        "get_build_status", {"job_name": "mcp-selftest"}))
                    if "IN_PROGRESS" not in status and "not found" not in status:
                        break
                print("status:", status)

                print("\n--- get_build_log (self-test) ---")
                log = _text(await session.call_tool(
                    "get_build_log", {"job_name": "mcp-selftest"}))
                print("contains 'hello-from-mcp':", "hello-from-mcp" in log)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
