"""Smoke test the MCP surface with the SDK's in-memory client."""
import asyncio
import unittest

from wfmcp.engine import Engine
from wfmcp.server import make_server
from wfmcp.store import Store
from wfmcp.teams import ConsoleNotifier

YAML = """
name: ping
version: 1
steps:
  - id: say
    kind: agent
    instructions: Say hello to {{ inputs.name }}
    outputs: [greeting]
"""


class ServerTests(unittest.TestCase):
    def test_tools_round_trip(self):
        async def go():
            from mcp.client.client import Client
            from mcp.client._memory import InMemoryTransport

            eng = Engine(Store(":memory:"), ConsoleNotifier(), secret="s")
            server = make_server(eng)
            async with Client(InMemoryTransport(server)) as client:
                names = {t.name for t in (await client.list_tools()).tools}
                self.assertTrue({"register_workflow_type", "start_workflow", "claim_step", "complete_step", "record_decision", "tick", "notify"} <= names)
                r = await client.call_tool("validate_workflow_type", {"yaml_text": "name: x\nversion: 1\nsteps: []"})
                self.assertFalse(_val(r)["ok"])
                r = await client.call_tool("register_workflow_type", {"yaml_text": YAML})
                self.assertTrue(_val(r)["ok"])
                r = await client.call_tool("start_workflow", {"type_name": "ping", "inputs": {"name": "Ada"}, "requested_by": "test"})
                run = _val(r)
                r = await client.call_tool("claim_step", {"run_id": run["id"], "step_id": "say", "worker": "t"})
                self.assertEqual(_val(r)["instructions"], "Say hello to Ada")
                r = await client.call_tool("complete_step", {"run_id": run["id"], "step_id": "say", "outputs": {"greeting": "hi"}})
                self.assertEqual(_val(r)["status"], "completed")
                res = await client.read_resource(f"workflow://runs/{run['id']}")
                self.assertIn(run["id"], res.contents[0].text)
                p = await client.get_prompt("author_workflow_type", {"goal": "approve expense"})
                self.assertIn("approve expense", p.messages[0].content.text)

        asyncio.run(go())


def _val(r):
    sc = r.structured_content
    return sc["result"] if isinstance(sc, dict) and "result" in sc and len(sc) == 1 else sc


if __name__ == "__main__":
    unittest.main()
