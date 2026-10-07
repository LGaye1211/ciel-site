# wfmcp: a small, flexible workflow engine as an MCP server

A workflow here is a directed graph of steps. The engine keeps the ledger, routes
each step to whoever does that kind of work, and tells humans through MS Teams.
It never calls a model itself. Agents (Cowork, Claude Code, a cron job) pull
`agent` steps over MCP, do the work with their own skills and connectors, and
report outputs back. Humans answer `human` and `approval` steps from Teams cards.

That split is what keeps it simple: the engine is a few hundred lines of state
machine plus SQLite, and all the intelligence lives in the agents and the YAML.

## Concepts

| Term | Meaning |
|---|---|
| Workflow type | A versioned YAML spec: inputs schema plus steps. Validated against `schema/workflow_type.schema.json`. |
| Run | One instance of a type, started with inputs. Lives in SQLite with a full event log. |
| Step kind | `agent` (an AI agent claims it and reports outputs), `human` (a person marks it done from a card), `approval` (a person picks an option from a card), `auto` (built-in `http` or `set` action), `notify` (card only). |
| `needs` | Dependencies. A step dispatches once every dependency is completed or skipped. |
| `when` | A structured condition on inputs or a prior step's outputs. False means the step is skipped. |
| Timers | `timeout`, `remind_after`, `on_timeout` (`fail`, `skip`, `reject`, `escalate` + `escalate_to`). Applied by `tick`. |
| Target | Where a card goes: `user: email` (activity feed) or `channel: logical-name` (Workflows webhook). Logical names map to real URLs in `channels.yaml`, so types stay portable. |

Templates are `{{ inputs.x }}`, `{{ steps.<id>.outputs.y }}`, `{{ run.id }}`. A
string that is exactly one placeholder keeps the value's type, so a map of
changes stays a map.

## Creating a new workflow type

1. Write the YAML. `workflows/data_fix_approval.yaml` is the smallest useful
   example; `workflows/mandate_onboarding_lite.yaml` shows fan-out, escalation
   and a custom-option gate. The MCP prompt `author_workflow_type` hands an agent
   the rules, the example and the schema, so a Cowork or Claude Code user can
   draft one from a one-line goal.
2. Validate: `python -m wfmcp validate workflows/my_type.yaml`, or the
   `validate_workflow_type` tool. All problems are reported in one go
   (unknown steps, cycles, missing fields per kind, bad conditions).
3. Register: drop the file in `workflows/` (loaded at start) or call
   `register_workflow_type` with the YAML. Bump `version` to upgrade; running
   runs keep the version they started with.

Rules of thumb: put every irreversible action behind an `approval` step, give
every human step a `timeout` and an `on_timeout`, and make `agent` steps declare
`outputs` so the engine can refuse incomplete work.

## Executing

```
start_workflow(type_name, inputs, requested_by)   -> run summary with first work items
next_work(worker)                                  -> ready agent steps across runs
claim_step(run_id, step_id, worker)                -> rendered instructions, expected outputs, context
complete_step(run_id, step_id, outputs)            -> engine advances, returns new summary
fail_step(run_id, step_id, reason)
record_decision(run_id, step_id, decision, by)     -> for human/approval steps (also hit by card buttons)
get_run / get_run_events / list_runs / cancel_run
notify(target, title, body, link)                  -> ad hoc Teams card
tick()                                             -> reminders, timeouts, escalations; call from a schedule
```

Resources: `workflow://types/{name}` (YAML) and `workflow://runs/{id}` (JSON).

A Cowork session's loop is: `next_work` → `claim_step` → do it with the named
skill and the Salesforce or Graph connectors → `complete_step`. A scheduled
Cowork task or Claude Code Routine calling `next_work` every few minutes turns
the engine into a queue; nothing waits on an open chat window.

## Teams notifications

Three delivery paths, chosen per target:

- **Channel cards** go to a Teams Workflows "post to a channel when a webhook
  request is received" flow. One URL per logical channel in `channels.yaml`.
  No Graph permissions, five minutes to set up, no per-user delivery.
- **Per-user pings** use the Graph activity feed
  (`/users/{id}/teamwork/sendActivityNotification`, application permission
  `TeamsActivity.Send`). Needs a registered Teams app whose manifest declares
  the activity type `workflowTask`, installed for the user. Configure under
  `graph:` in `channels.yaml`.
- **Audit**: set `notify.audit_channel` on a type and every run start, finish,
  failure and cancellation is posted there.

Buttons on `human` and `approval` cards are signed, expiring links to the
callback endpoint (`python -m wfmcp callback`, `GET /decide/<token>`). A click
records the decision, updates the run and refuses a second click. This is the
MVP trade-off: anyone holding the link can click it, so keep the endpoint on
the internal network. The upgrade path is a Teams bot with Adaptive Card
`Action.Execute`, which carries the clicker's AAD identity; only
`_send_task_card` and the callback change.

## Running

```
python -m venv .venv && .venv/bin/pip install -e .
cp config/channels.example.yaml config/channels.yaml   # fill in webhooks
export WFMCP_CHANNELS=config/channels.yaml WFMCP_SECRET=$(openssl rand -hex 16) \
       WFMCP_CALLBACK_BASE=https://wf.internal.example.com
.venv/bin/python -m wfmcp callback &     # card buttons land here
.venv/bin/python -m wfmcp                # MCP over stdio (or `http` for streamable HTTP)
.venv/bin/python -m unittest discover -s tests
```

Claude Code: `claude mcp add wfmcp -- /path/.venv/bin/python -m wfmcp`.
Cowork: add it as a custom MCP server with the same command, or run `http`
behind your gateway and register the URL. Without `WFMCP_CHANNELS` every card
is printed to the console, which is enough to develop a workflow type.

## Layout

```
wfmcp/spec.py        YAML parsing and validation (schema + graph checks)
wfmcp/engine.py      state machine, timers, decision tokens, actions
wfmcp/store.py       SQLite: types, runs, events
wfmcp/teams.py       Console, Workflows webhook, Graph activity feed notifiers
wfmcp/cards.py       Adaptive Card builders
wfmcp/server.py      MCP tools, resources, prompt
wfmcp/callback.py    HTTP endpoint for card buttons
workflows/           example types, loaded at start
tests/               engine, server (in-memory MCP client) and callback tests
```

## What to add next, in order

1. Bot-based cards with `Action.Execute` for identity-carrying approvals.
2. A `trust` field per agent step (`draft`, `assist`, `auto`) that inserts or
   removes the following approval automatically, so promotion is a config change.
3. Postgres instead of SQLite once more than one engine process is needed.
4. Graph change notifications on the audit channel so human replies become events.
