"""MCP server exposing the engine. Run with `python -m wfmcp` (stdio) or `python -m wfmcp http`.

Environment:
  WFMCP_DB             sqlite path (default ./wfmcp.db)
  WFMCP_WORKFLOWS_DIR  directory of *.yaml workflow types loaded at start (default ./workflows)
  WFMCP_CHANNELS       channels.yaml mapping logical Teams channels to webhooks (default: console)
  WFMCP_CALLBACK_BASE  public base URL of the callback endpoint used in card buttons
  WFMCP_SECRET         HMAC secret for decision links (must match the callback process)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from . import spec
from .engine import Engine
from .store import Store
from .teams import build_notifier_from_config


def build_engine() -> Engine:
    store = Store(os.environ.get("WFMCP_DB", "wfmcp.db"))
    notifier = build_notifier_from_config(os.environ.get("WFMCP_CHANNELS"))
    eng = Engine(store, notifier, callback_base=os.environ.get("WFMCP_CALLBACK_BASE", "http://localhost:8787"), secret=os.environ.get("WFMCP_SECRET"))
    wdir = Path(os.environ.get("WFMCP_WORKFLOWS_DIR", Path(__file__).resolve().parent.parent / "workflows"))
    if wdir.is_dir():
        for f in sorted(wdir.glob("*.y*ml")):
            eng.register_type(f.read_text(), source=str(f))
    return eng


INSTRUCTIONS = """You are talking to a workflow engine. Workflow *types* are YAML specs; *runs* are instances.
Typical loop for an agent worker: next_work -> claim_step -> do the work -> complete_step (or fail_step).
Humans answer `human` and `approval` steps from Teams cards; you may also record their decision with record_decision
when they tell you in chat. To add a workflow type, write YAML (see the author_workflow_type prompt), validate it
with validate_workflow_type, then register_workflow_type. Call tick periodically to apply reminders and timeouts."""


def make_server(engine: Engine | None = None) -> MCPServer:
    eng = engine or build_engine()
    mcp = MCPServer("wfmcp", instructions=INSTRUCTIONS, version="0.1.0")

    # ---- types
    @mcp.tool(description="List registered workflow types with their steps.")
    def list_workflow_types() -> list[dict[str, Any]]:
        return eng.types()

    @mcp.tool(description="Get one workflow type: inputs schema and step graph.")
    def get_workflow_type(name: str) -> dict[str, Any]:
        return spec.describe(eng.get_type(name))

    @mcp.tool(description="Validate workflow type YAML without registering it. Returns ok=true or a list of problems.")
    def validate_workflow_type(yaml_text: str) -> dict[str, Any]:
        try:
            wt = spec.parse(yaml_text)
            return {"ok": True, "name": wt.name, "version": wt.version, "steps": wt.order, "graph": wt.graph()}
        except spec.SpecError as e:
            return {"ok": False, "problems": [p.strip() for p in str(e).split(";")]}

    @mcp.tool(description="Register (or upgrade) a workflow type from YAML. Validation errors are returned, not raised.")
    def register_workflow_type(yaml_text: str) -> dict[str, Any]:
        try:
            wt = eng.register_type(yaml_text)
            return {"ok": True, "name": wt.name, "version": wt.version}
        except (spec.SpecError, ValueError) as e:
            return {"ok": False, "problems": [p.strip() for p in str(e).split(";")]}

    # ---- runs
    @mcp.tool(description="Start a run of a workflow type. Returns the run summary including the first work items.")
    def start_workflow(type_name: str, inputs: dict[str, Any], requested_by: str = "") -> dict[str, Any]:
        return eng.start(type_name, inputs, requested_by)

    @mcp.tool(description="Run status: every step's state and outputs, open work items, and what humans it waits on.")
    def get_run(run_id: str) -> dict[str, Any]:
        return eng.summary(eng.get_run(run_id))

    @mcp.tool(description="Event log of a run, oldest first.")
    def get_run_events(run_id: str) -> list[dict[str, Any]]:
        eng.get_run(run_id)
        return eng.store.events(run_id)

    @mcp.tool(description="List runs, newest first. status: running|completed|failed|cancelled.")
    def list_runs(status: str | None = None, type_name: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        return eng.list_runs(status, type_name, limit)

    @mcp.tool(description="Cancel a running run; open steps are skipped.")
    def cancel_run(run_id: str, reason: str = "") -> dict[str, Any]:
        return eng.cancel(run_id, reason)

    # ---- agent work
    @mcp.tool(description="Agent steps that are ready to be claimed (plus ones already claimed by `worker`).")
    def next_work(worker: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        return eng.next_work(worker, limit)

    @mcp.tool(description="Claim an agent step. Returns rendered instructions, expected outputs, inputs and prior step outputs.")
    def claim_step(run_id: str, step_id: str, worker: str) -> dict[str, Any]:
        return eng.claim(run_id, step_id, worker)

    @mcp.tool(description="Complete an agent step with its outputs. The engine advances the run and returns the new summary.")
    def complete_step(run_id: str, step_id: str, outputs: dict[str, Any], worker: str = "") -> dict[str, Any]:
        return eng.complete(run_id, step_id, outputs, worker)

    @mcp.tool(description="Mark a step failed with a reason. Downstream steps stay pending; the run fails once nothing is open.")
    def fail_step(run_id: str, step_id: str, reason: str, worker: str = "") -> dict[str, Any]:
        return eng.fail(run_id, step_id, reason, worker)

    # ---- humans
    @mcp.tool(description="Record a human decision on a waiting human/approval step (approved, rejected, done, or a custom option).")
    def record_decision(run_id: str, step_id: str, decision: str, decided_by: str, comment: str = "") -> dict[str, Any]:
        return eng.decide(run_id, step_id, decision, decided_by, comment)

    @mcp.tool(description="Send an ad hoc Teams notification. target: {'channel': name} or {'user': email}.")
    def notify(target: dict[str, str], title: str, body: str = "", link: str | None = None) -> dict[str, Any]:
        return {"ref": eng.notify(target, title, body, link)}

    @mcp.tool(description="Apply reminders, timeouts and escalations. Call from a schedule.")
    def tick() -> list[dict[str, Any]]:
        return eng.tick()

    # ---- resources and prompts
    @mcp.resource("workflow://types/{name}", description="YAML of a workflow type")
    def type_yaml(name: str) -> str:
        got = eng.store.get_type_yaml(name)
        if not got:
            raise ValueError(f"unknown type {name}")
        return got[1]

    @mcp.resource("workflow://runs/{run_id}", description="Full JSON state of a run", mime_type="application/json")
    def run_json(run_id: str) -> dict[str, Any]:
        return eng.get_run(run_id)

    @mcp.prompt(description="How to author a new workflow type for this engine")
    def author_workflow_type(goal: str) -> str:
        schema = (Path(__file__).resolve().parent.parent / "schema" / "workflow_type.schema.json").read_text()
        example = (Path(__file__).resolve().parent.parent / "workflows" / "data_fix_approval.yaml").read_text()
        return (
            f"Write a workflow type YAML for this goal:\n\n{goal}\n\n"
            "Rules: steps form a DAG via `needs`; kinds are agent (an AI agent does it and reports outputs), "
            "human (a person marks it done from a Teams card), approval (a person approves or rejects from a Teams card), "
            "auto (built-in http/set action), notify (card only). Put every irreversible action behind an approval step. "
            "Use `when` to branch on a prior step's outputs. Give every human step a timeout and on_timeout. "
            "Template values with {{ inputs.x }} and {{ steps.<id>.outputs.y }}.\n\n"
            f"Validate with validate_workflow_type, then register_workflow_type.\n\nExample:\n```yaml\n{example}\n```\n\nSchema:\n```json\n{schema}\n```"
        )

    return mcp
