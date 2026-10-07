"""Minimal `{{ path.to.value }}` templating over a context dict. No logic, no deps."""
from __future__ import annotations

import re
from typing import Any

_PAT = re.compile(r"\{\{\s*([A-Za-z0-9_.\-]+)\s*\}\}")


def resolve(path: str, ctx: dict) -> Any:
    cur: Any = ctx
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return None
    return cur


def render(value: Any, ctx: dict) -> Any:
    """Render templates inside strings, dicts and lists.

    A string that is exactly one placeholder returns the raw value, so numbers
    and dicts survive. Any other string is substituted as text.
    """
    if isinstance(value, str):
        m = _PAT.fullmatch(value.strip())
        if m:
            found = resolve(m.group(1), ctx)
            return found if found is not None else ""
        return _PAT.sub(lambda mm: _as_text(resolve(mm.group(1), ctx)), value)
    if isinstance(value, dict):
        return {k: render(v, ctx) for k, v in value.items()}
    if isinstance(value, list):
        return [render(v, ctx) for v in value]
    return value


def _as_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        import json

        return json.dumps(v, ensure_ascii=False)
    return str(v)
