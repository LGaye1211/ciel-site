"""The workflow engine: a ledger of runs, a router of steps, and a notifier of humans.

It deliberately does not call a model. `agent` steps are handed to whichever
agent claims them (Cowork, Claude Code, a cron job); `human` and `approval`
steps are Teams cards whose buttons come back through `decide()`; `auto` steps
are small built-in actions; `notify` steps are fire-and-forget cards.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets as _secrets
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from . import spec
from .cards import card, open_url
from .store import Store, now_iso
from .templating import render, resolve

TERMINAL = {"completed", "skipped", "failed"}
OPEN = {"pending", "ready", "claimed", "waiting"}


class EngineError(ValueError):
    pass


def parse_duration(s: str | None) -> timedelta | None:
    if not s:
        return None
    m = re.fullmatch(r"(\d+)([mhd])", s)
    if not m:
        raise EngineError(f"bad duration {s!r}")
    n, unit = int(m.group(1)), m.group(2)
    return timedelta(**{{'m': 'minutes', 'h': 'hours', 'd': 'days'}[unit]: n})


class Engine:
    def __init__(
        self,
        store: Store,
        notifier,
        callback_base: str = "http://localhost:8787",
        secret: str | None = None,
        now: Callable[[], datetime] | None = None,
        http_opener: Callable[..., Any] | None = None,
    ):
        self.store = store
        self.notifier = notifier
        self.callback_base = callback_base.rstrip("/")
        self.secret = (secret or _secrets.token_hex(16)).encode()
        self.now = now or (lambda: datetime.now(timezone.utc))
        self._http = http_opener or urllib.request.urlopen
        self._types: dict[str, spec.WorkflowType] = {}
        for t in store.list_types():
            got = store.get_type_yaml(t["name"])
            if got:
                self._types[t["name"]] = spec.parse(got[1], source=f"store:{t['name']}@{got[0]}")

    # ----------------------------------------------------------------- types
    def register_type(self, yaml_text: str, source: str = "<inline>") -> spec.WorkflowType:
        wt = spec.parse(yaml_text, source=source)
        existing = self._types.get(wt.name)
        if existing and existing.version > wt.version:
            raise EngineError(f"{wt.name}: version {wt.version} is older than registered version {existing.version}")
        self.store.put_type(wt.name, wt.version, yaml_text)
        self._types[wt.name] = wt
        return wt

    def types(self) -> list[dict]:
        return [spec.describe(t) for t in self._types.values()]

    def get_type(self, name: str) -> spec.WorkflowType:
        try:
            return self._types[name]
        except KeyError:
            raise EngineError(f"unknown workflow type {name!r}; known: {sorted(self._types)}") from None

    def _type_for(self, run: dict) -> spec.WorkflowType:
        wt = self._types.get(run["type"])
        if wt and wt.version == run["version"]:
            return wt
        got = self.store.get_type_yaml(run["type"], run["version"])
        if not got:
            raise EngineError(f"type {run['type']}@{run['version']} missing for run {run['id']}")
        return spec.parse(got[1], source=f"store:{run['type']}@{run['version']}")

    # ------------------------------------------------------------------ runs
    def start(self, type_name: str, inputs: dict, requested_by: str = "", run_id: str | None = None) -> dict:
        wt = self.get_type(type_name)
        problems = wt.validate_inputs(inputs or {})
        if problems:
            raise EngineError("invalid inputs: " + "; ".join(problems))
        run = {
            "id": run_id or f"{wt.name}-{self.now().strftime('%Y%m%d')}-{_secrets.token_hex(3)}",
            "type": wt.name,
            "version": wt.version,
            "status": "running",
            "inputs": inputs or {},
            "requested_by": requested_by,
            "created_at": now_iso(),
            "finished_at": None,
            "steps": {s["id"]: {"status": "pending", "outputs": {}} for s in wt.steps},
        }
        self.store.put_run(run)
        self.store.add_event(run["id"], "run.started", requested_by=requested_by, inputs=inputs)
        self._audit(wt, run, f"Run {run['id']} started by {requested_by or 'unknown'}")
        self._advance(run, wt)
        return self.summary(run)

    def get_run(self, run_id: str) -> dict:
        run = self.store.get_run(run_id)
        if not run:
            raise EngineError(f"unknown run {run_id!r}")
        return run

    def list_runs(self, status: str | None = None, type_name: str | None = None, limit: int = 50) -> list[dict]:
        return [self.summary(r) for r in self.store.list_runs(status, type_name, limit)]

    def summary(self, run: dict) -> dict:
        return {
            "id": run["id"],
            "type": run["type"],
            "version": run["version"],
            "status": run["status"],
            "requested_by": run["requested_by"],
            "created_at": run["created_at"],
            "finished_at": run.get("finished_at"),
            "steps": {sid: {k: v for k, v in st.items() if k in ("status", "outputs", "claimed_by", "deadline", "assigned_to")} for sid, st in run["steps"].items()},
            "work_items": self.work_items(run),
            "waiting_on": [
                {"step": sid, "assigned_to": st.get("assigned_to"), "deadline": st.get("deadline")}
                for sid, st in run["steps"].items() if st["status"] == "waiting"
            ],
        }

    def work_items(self, run: dict) -> list[dict]:
        wt = self._type_for(run)
        return [
            {"run_id": run["id"], "step_id": sid, "title": wt.step(sid).get("title", sid), "skill": wt.step(sid).get("skill"), "status": st["status"], "claimed_by": st.get("claimed_by")}
            for sid, st in run["steps"].items() if st["status"] in ("ready", "claimed")
        ]

    def next_work(self, worker: str | None = None, limit: int = 20) -> list[dict]:
        out = []
        for run in self.store.list_runs(status="running", limit=500):
            for wi in self.work_items(run):
                if wi["status"] == "ready" or wi["claimed_by"] == worker:
                    out.append(wi)
        return out[:limit]

    # ----------------------------------------------------------- agent steps
    def claim(self, run_id: str, step_id: str, worker: str) -> dict:
        run, wt, st, step = self._load(run_id, step_id)
        if step["kind"] != "agent":
            raise EngineError(f"step {step_id} is kind {step['kind']}, only agent steps are claimed")
        if st["status"] == "claimed" and st.get("claimed_by") != worker:
            raise EngineError(f"step {step_id} already claimed by {st['claimed_by']}")
        if st["status"] not in ("ready", "claimed"):
            raise EngineError(f"step {step_id} is {st['status']}, not ready")
        st.update(status="claimed", claimed_by=worker, claimed_at=now_iso())
        self.store.put_run(run)
        self.store.add_event(run_id, "step.claimed", step_id, worker=worker)
        ctx = self._ctx(run)
        return {
            "run_id": run_id,
            "step_id": step_id,
            "title": render(step.get("title", step_id), ctx),
            "skill": step.get("skill"),
            "instructions": render(step["instructions"], ctx),
            "expected_outputs": step.get("outputs", []),
            "inputs": run["inputs"],
            "prior_outputs": {sid: s["outputs"] for sid, s in run["steps"].items() if s["status"] == "completed" and s["outputs"]},
            "how_to_finish": f"call complete_step(run_id={run_id!r}, step_id={step_id!r}, outputs={{...}}) with every expected output, or fail_step with a reason",
        }

    def complete(self, run_id: str, step_id: str, outputs: dict | None, worker: str = "") -> dict:
        run, wt, st, step = self._load(run_id, step_id)
        if st["status"] not in ("ready", "claimed"):
            raise EngineError(f"step {step_id} is {st['status']}; only ready or claimed steps can be completed")
        outputs = outputs or {}
        missing = [k for k in step.get("outputs", []) if k not in outputs]
        if missing:
            raise EngineError(f"step {step_id} requires outputs {missing}")
        st.update(status="completed", outputs=outputs, completed_by=worker, completed_at=now_iso())
        self.store.add_event(run_id, "step.completed", step_id, worker=worker, outputs=outputs)
        self._advance(run, wt)
        return self.summary(run)

    def fail(self, run_id: str, step_id: str, reason: str, worker: str = "") -> dict:
        run, wt, st, step = self._load(run_id, step_id)
        if st["status"] in TERMINAL:
            raise EngineError(f"step {step_id} is already {st['status']}")
        st.update(status="failed", reason=reason, failed_by=worker, failed_at=now_iso())
        self.store.add_event(run_id, "step.failed", step_id, reason=reason, worker=worker)
        self._advance(run, wt)
        return self.summary(run)

    # ----------------------------------------------------------- human steps
    def decide(self, run_id: str, step_id: str, decision: str, decided_by: str = "", comment: str = "") -> dict:
        run, wt, st, step = self._load(run_id, step_id)
        if st["status"] != "waiting":
            raise EngineError(f"step {step_id} is {st['status']}, not waiting for a decision")
        allowed = self._options(step)
        if decision not in allowed:
            raise EngineError(f"decision {decision!r} not in {allowed}")
        st.update(status="completed", outputs={"decision": decision, "decided_by": decided_by, "comment": comment}, completed_at=now_iso())
        self.store.add_event(run_id, "step.decided", step_id, decision=decision, decided_by=decided_by, comment=comment)
        self._advance(run, wt)
        return self.summary(run)

    def decision_token(self, run_id: str, step_id: str, choice: str, ttl: timedelta = timedelta(days=14)) -> str:
        exp = int((self.now() + ttl).timestamp())
        msg = f"{run_id}|{step_id}|{choice}|{exp}"
        sig = hmac.new(self.secret, msg.encode(), hashlib.sha256).hexdigest()[:32]
        return f"{msg}|{sig}".replace("|", ".")

    def verify_token(self, token: str) -> tuple[str, str, str]:
        try:
            run_id, step_id, choice, exp, sig = token.split(".")
        except ValueError:
            raise EngineError("malformed token") from None
        msg = f"{run_id}|{step_id}|{choice}|{exp}"
        want = hmac.new(self.secret, msg.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(want, sig):
            raise EngineError("bad signature")
        if int(exp) < self.now().timestamp():
            raise EngineError("token expired")
        return run_id, step_id, choice

    # ---------------------------------------------------------------- timers
    def tick(self) -> list[dict]:
        """Apply reminders and timeouts. Call from a cron, a Routine, or the MCP `tick` tool."""
        actions = []
        now = self.now()
        for run in self.store.list_runs(status="running", limit=1000):
            wt = self._type_for(run)
            changed = False
            for sid, st in run["steps"].items():
                if st["status"] != "waiting":
                    continue
                step = wt.step(sid)
                if st.get("remind_at") and not st.get("reminded") and now >= _dt(st["remind_at"]):
                    self._send_task_card(wt, run, step, st, reminder=True)
                    st["reminded"] = True
                    actions.append({"run": run["id"], "step": sid, "action": "reminded"})
                    changed = True
                if st.get("deadline") and now >= _dt(st["deadline"]):
                    mode = step.get("on_timeout", "fail")
                    if mode == "escalate" and not st.get("escalated"):
                        st["escalated"] = True
                        st["assigned_to"] = render(step["escalate_to"], self._ctx(run))
                        st["deadline"] = (now + parse_duration(step["timeout"])).isoformat(timespec="seconds")
                        self._send_task_card(wt, run, step, st, escalated=True)
                        actions.append({"run": run["id"], "step": sid, "action": "escalated", "to": st["assigned_to"]})
                    elif mode == "skip":
                        st.update(status="skipped", reason="timeout")
                        actions.append({"run": run["id"], "step": sid, "action": "skipped"})
                    elif mode == "reject":
                        st.update(status="completed", outputs={"decision": "rejected", "decided_by": "timeout", "comment": "no answer before deadline"})
                        actions.append({"run": run["id"], "step": sid, "action": "auto-rejected"})
                    else:
                        st.update(status="failed", reason="timeout")
                        actions.append({"run": run["id"], "step": sid, "action": "failed"})
                    self.store.add_event(run["id"], "step.timeout", sid, mode=mode)
                    changed = True
            if changed:
                self._advance(run, wt)
        return actions

    def cancel(self, run_id: str, reason: str = "") -> dict:
        run = self.get_run(run_id)
        wt = self._type_for(run)
        for st in run["steps"].values():
            if st["status"] in OPEN:
                st.update(status="skipped", reason=f"cancelled: {reason}")
        run.update(status="cancelled", finished_at=now_iso())
        self.store.put_run(run)
        self.store.add_event(run_id, "run.cancelled", reason=reason)
        self._audit(wt, run, f"Run {run_id} cancelled: {reason}")
        return self.summary(run)

    def notify(self, target: dict, title: str, body: str = "", link: str | None = None, facts: dict | None = None) -> str:
        actions = [open_url("Open", link)] if link else None
        return self.notifier.send(target, card(title, body, facts, actions), title)

    # ------------------------------------------------------------- internals
    def _load(self, run_id: str, step_id: str):
        run = self.get_run(run_id)
        if run["status"] != "running":
            raise EngineError(f"run {run_id} is {run['status']}")
        wt = self._type_for(run)
        try:
            step = wt.step(step_id)
        except KeyError:
            raise EngineError(f"unknown step {step_id!r} in {run['type']}") from None
        return run, wt, run["steps"][step_id], step

    def _ctx(self, run: dict) -> dict:
        return {
            "inputs": run["inputs"],
            "steps": {sid: {"status": st["status"], "outputs": st.get("outputs", {})} for sid, st in run["steps"].items()},
            "run": {"id": run["id"], "type": run["type"], "requested_by": run["requested_by"]},
        }

    def _advance(self, run: dict, wt: spec.WorkflowType) -> None:
        progressed = True
        while progressed and run["status"] == "running":
            progressed = False
            for step in wt.steps:
                st = run["steps"][step["id"]]
                if st["status"] != "pending":
                    continue
                needs = [run["steps"][n]["status"] for n in step.get("needs", [])]
                if any(n == "failed" for n in needs):
                    continue
                if not all(n in ("completed", "skipped") for n in needs):
                    continue
                if step.get("when") and not eval_condition(step["when"], self._ctx(run)):
                    st.update(status="skipped", reason="condition false")
                    self.store.add_event(run["id"], "step.skipped", step["id"])
                    progressed = True
                    continue
                self._dispatch(run, wt, step, st)
                progressed = True
        statuses = {st["status"] for st in run["steps"].values()}
        if run["status"] == "running":
            if "failed" in statuses and not (statuses & OPEN - {"pending"}):
                run.update(status="failed", finished_at=now_iso())
                self.store.add_event(run["id"], "run.failed")
                self._audit(wt, run, f"Run {run['id']} failed")
            elif statuses <= TERMINAL:
                run.update(status="completed", finished_at=now_iso())
                self.store.add_event(run["id"], "run.completed")
                self._audit(wt, run, f"Run {run['id']} completed")
        self.store.put_run(run)

    def _dispatch(self, run: dict, wt: spec.WorkflowType, step: dict, st: dict) -> None:
        kind = step["kind"]
        ctx = self._ctx(run)
        if kind == "agent":
            st["status"] = "ready"
            self.store.add_event(run["id"], "step.ready", step["id"])
        elif kind in ("human", "approval"):
            now = self.now()
            st["status"] = "waiting"
            st["assigned_to"] = render(step.get("user") or step.get("channel") or wt.notify.get("channel", ""), ctx)
            t = parse_duration(step.get("timeout"))
            st["deadline"] = (now + t).isoformat(timespec="seconds") if t else None
            r = parse_duration(step.get("remind_after"))
            st["remind_at"] = (now + r).isoformat(timespec="seconds") if r else None
            self._send_task_card(wt, run, step, st)
            self.store.add_event(run["id"], "step.waiting", step["id"], assigned_to=st["assigned_to"], deadline=st["deadline"])
        elif kind == "notify":
            ref = self.notifier.send(self._target(wt, step, ctx), card(render(step.get("title", wt.name), ctx), render(step["body"], ctx), self._facts(run), [open_url("Open", render(step["link"], ctx))] if step.get("link") else None), render(step.get("title", step["body"]), ctx))
            st.update(status="completed", message_ref=ref)
            self.store.add_event(run["id"], "step.notified", step["id"], ref=ref)
        elif kind == "auto":
            try:
                st.update(status="completed", outputs=self._run_action(render(step["action"], ctx)))
                self.store.add_event(run["id"], "step.completed", step["id"], outputs=st["outputs"])
            except Exception as e:  # noqa: BLE001
                st.update(status="failed", reason=str(e))
                self.store.add_event(run["id"], "step.failed", step["id"], reason=str(e))

    def _run_action(self, action: dict) -> dict:
        if action["type"] == "set":
            return dict(action.get("values", {}))
        if action["type"] == "http":
            data = json.dumps(action["json"]).encode() if "json" in action else None
            headers = {"Content-Type": "application/json", **action.get("headers", {})}
            req = urllib.request.Request(action["url"], data=data, headers=headers, method=action.get("method", "POST" if data else "GET"))
            with self._http(req, timeout=20) as resp:
                raw = resp.read().decode()
                try:
                    body = json.loads(raw) if raw else None
                except json.JSONDecodeError:
                    body = raw
                return {"status": resp.status, "body": body}
        raise EngineError(f"unknown action type {action['type']}")

    def _options(self, step: dict) -> list[str]:
        if step["kind"] == "approval":
            return list(step.get("options") or ["approved", "rejected"])
        return list(step.get("options") or ["done"])

    def _target(self, wt: spec.WorkflowType, step: dict, ctx: dict) -> dict:
        if step.get("user"):
            return {"user": render(step["user"], ctx)}
        return {"channel": render(step.get("channel") or wt.notify.get("channel", ""), ctx)}

    def _facts(self, run: dict) -> dict:
        return {"Workflow": run["type"], "Run": run["id"], "Requested by": run["requested_by"]}

    def _send_task_card(self, wt, run, step, st, reminder=False, escalated=False) -> None:
        ctx = self._ctx(run)
        title = render(step.get("title", step["id"]), ctx)
        if reminder:
            title = f"Reminder: {title}"
        if escalated:
            title = f"Escalated: {title}"
        facts = {**self._facts(run), "Due": st.get("deadline") or "no deadline"}
        actions = [open_url(opt.capitalize(), f"{self.callback_base}/decide/{self.decision_token(run['id'], step['id'], opt)}", "positive" if opt in ("approved", "done") else "destructive" if opt == "rejected" else "default") for opt in self._options(step)]
        if step.get("link"):
            actions.append(open_url("Open record", render(step["link"], ctx)))
        c = card(title, render(step.get("body", ""), ctx), facts, actions, footer="Sent by the workflow agent. Replies to this message are not read; use the buttons.")
        target = {"user": st["assigned_to"]} if (step.get("user") or escalated) else self._target(wt, step, ctx)
        st["message_ref"] = self.notifier.send(target, c, title)

    def _audit(self, wt: spec.WorkflowType, run: dict, text: str) -> None:
        ch = wt.notify.get("audit_channel")
        if ch:
            try:
                self.notifier.send({"channel": ch}, card(text, facts=self._facts(run)), text)
            except Exception as e:  # noqa: BLE001
                self.store.add_event(run["id"], "audit.failed", error=str(e))


def eval_condition(c: dict, ctx: dict) -> bool:
    if "all" in c:
        return all(eval_condition(s, ctx) for s in c["all"])
    if "any" in c:
        return any(eval_condition(s, ctx) for s in c["any"])
    if "step" in c:
        v = ctx["steps"].get(c["step"], {}).get("outputs", {}).get(c["output"])
    else:
        v = resolve(c["input"], ctx["inputs"])
    if "exists" in c:
        return (v is not None) == bool(c["exists"])
    if "eq" in c:
        return v == c["eq"]
    if "ne" in c:
        return v != c["ne"]
    if "in" in c:
        return v in c["in"]
    try:
        if "lt" in c:
            return float(v) < float(c["lt"])
        if "gt" in c:
            return float(v) > float(c["gt"])
    except (TypeError, ValueError):
        return False
    return False


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s)
