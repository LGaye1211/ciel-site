"""Load and validate workflow type definitions (YAML)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema
import yaml

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "workflow_type.schema.json"
_SCHEMA = json.loads(SCHEMA_PATH.read_text())

KIND_REQUIRES = {
    "agent": ["instructions"],
    "human": ["title"],
    "approval": ["title"],
    "notify": ["body"],
    "auto": ["action"],
}


class SpecError(ValueError):
    pass


@dataclass
class WorkflowType:
    name: str
    version: int
    description: str
    inputs_schema: dict
    steps: list[dict]
    notify: dict = field(default_factory=dict)
    owner: str = ""
    raw: dict = field(default_factory=dict)
    source: str = ""

    def step(self, step_id: str) -> dict:
        for s in self.steps:
            if s["id"] == step_id:
                return s
        raise KeyError(step_id)

    @property
    def order(self) -> list[str]:
        return [s["id"] for s in self.steps]

    def validate_inputs(self, inputs: dict) -> list[str]:
        if not self.inputs_schema:
            return []
        v = jsonschema.Draft202012Validator(self.inputs_schema)
        return [f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in v.iter_errors(inputs)]

    def graph(self) -> dict[str, list[str]]:
        return {s["id"]: list(s.get("needs", [])) for s in self.steps}


def parse(yaml_text: str, source: str = "<inline>") -> WorkflowType:
    """Parse and fully validate a workflow type. Raises SpecError with all problems."""
    try:
        raw = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:  # pragma: no cover
        raise SpecError(f"{source}: YAML error: {e}") from e
    if not isinstance(raw, dict):
        raise SpecError(f"{source}: top level must be a mapping")

    errors = [
        f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
        for e in jsonschema.Draft202012Validator(_SCHEMA).iter_errors(raw)
    ]
    if errors:
        raise SpecError(f"{source}: " + "; ".join(errors))

    steps = raw["steps"]
    ids = [s["id"] for s in steps]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        errors.append(f"duplicate step ids: {sorted(dupes)}")
    for s in steps:
        for need in s.get("needs", []):
            if need not in ids:
                errors.append(f"step '{s['id']}' needs unknown step '{need}'")
        for key in KIND_REQUIRES[s["kind"]]:
            if key not in s:
                errors.append(f"step '{s['id']}' of kind '{s['kind']}' requires '{key}'")
        if s.get("on_timeout") == "escalate" and not s.get("escalate_to"):
            errors.append(f"step '{s['id']}' has on_timeout=escalate but no escalate_to")
        if s.get("on_timeout") and not s.get("timeout"):
            errors.append(f"step '{s['id']}' has on_timeout but no timeout")
        w = s.get("when")
        if w:
            errors.extend(_check_condition(w, s["id"], ids))
    cycle = _find_cycle({s["id"]: s.get("needs", []) for s in steps})
    if cycle:
        errors.append(f"dependency cycle: {' -> '.join(cycle)}")
    if errors:
        raise SpecError(f"{source}: " + "; ".join(errors))

    return WorkflowType(
        name=raw["name"],
        version=int(raw["version"]),
        description=raw.get("description", ""),
        inputs_schema=raw.get("inputs", {}),
        steps=steps,
        notify=raw.get("notify", {}),
        owner=raw.get("owner", ""),
        raw=raw,
        source=source,
    )


def _check_condition(c: dict, step_id: str, ids: list[str]) -> list[str]:
    errs: list[str] = []
    if "all" in c or "any" in c:
        for sub in c.get("all", []) + c.get("any", []):
            errs.extend(_check_condition(sub, step_id, ids))
        return errs
    if ("step" in c) == ("input" in c):
        errs.append(f"step '{step_id}': condition needs exactly one of 'step' or 'input'")
    if "step" in c:
        if c["step"] not in ids:
            errs.append(f"step '{step_id}': condition refers to unknown step '{c['step']}'")
        if "output" not in c:
            errs.append(f"step '{step_id}': condition on a step needs 'output'")
    if not any(k in c for k in ("eq", "ne", "lt", "gt", "in", "exists")):
        errs.append(f"step '{step_id}': condition needs an operator (eq, ne, lt, gt, in, exists)")
    return errs


def _find_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    WHITE, GREY, BLACK = 0, 1, 2
    color = {n: WHITE for n in graph}
    stack: list[str] = []

    def visit(n: str) -> list[str] | None:
        color[n] = GREY
        stack.append(n)
        for m in graph.get(n, []):
            if m not in color:
                continue
            if color[m] == GREY:
                return stack[stack.index(m):] + [m]
            if color[m] == WHITE:
                found = visit(m)
                if found:
                    return found
        stack.pop()
        color[n] = BLACK
        return None

    for n in graph:
        if color[n] == WHITE:
            found = visit(n)
            if found:
                return found
    return None


def load_dir(path: str | Path) -> list[WorkflowType]:
    out = []
    for f in sorted(Path(path).glob("*.y*ml")):
        out.append(parse(f.read_text(), source=str(f)))
    return out


def describe(wt: WorkflowType) -> dict[str, Any]:
    return {
        "name": wt.name,
        "version": wt.version,
        "description": wt.description,
        "owner": wt.owner,
        "inputs": wt.inputs_schema,
        "steps": [
            {k: s[k] for k in ("id", "kind", "title", "needs", "when", "timeout", "on_timeout", "skill", "outputs") if k in s}
            for s in wt.steps
        ],
    }
