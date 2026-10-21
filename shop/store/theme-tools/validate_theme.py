#!/usr/bin/env python3
"""Offline checks for a Shopify theme folder.

    python validate_theme.py /path/to/theme

Checks:
  1. required folders and files exist
  2. every .json file parses (comments allowed, as Shopify allows them)
  3. every section referenced by a template or group exists, and its settings and
     blocks match that section's schema (ids, select options, ranges, types)
  4. every snippet rendered and every asset referenced exists
  5. config/settings_data.json keys exist in config/settings_schema.json
Exit code 0 when clean, 1 when problems are found, 2 on bad usage.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_theme_zip import strip_json_comments  # noqa: E402

if len(sys.argv) != 2:
    print("usage: validate_theme.py /path/to/theme", file=sys.stderr)
    sys.exit(2)
root = Path(sys.argv[1])
problems = []


def problem(msg):
    problems.append(msg)


def load_json(path):
    return json.loads(strip_json_comments(path.read_text(encoding="utf-8-sig")))


# 1. structure -----------------------------------------------------------------
for folder in ("assets", "config", "layout", "locales", "sections", "snippets", "templates"):
    if not (root / folder).is_dir():
        problem(f"missing folder: {folder}")
for f in ("layout/theme.liquid", "config/settings_schema.json", "config/settings_data.json",
          "locales/en.default.json", "templates/index.json", "templates/product.json",
          "templates/collection.json", "templates/cart.json", "templates/page.json"):
    if not (root / f).is_file():
        problem(f"missing file: {f}")
layout = (root / "layout/theme.liquid").read_text(encoding="utf-8") if (root / "layout/theme.liquid").exists() else ""
for token in ("{{ content_for_header }}", "{{ content_for_layout }}"):
    if token not in layout:
        problem(f"layout/theme.liquid is missing {token}")

# 2. JSON parses ---------------------------------------------------------------
parsed = {}
for p in sorted(root.rglob("*.json")):
    try:
        parsed[p.relative_to(root).as_posix()] = load_json(p)
    except Exception as e:  # noqa: BLE001
        problem(f"invalid JSON: {p.relative_to(root)}: {e}")


def section_schema(section_type):
    path = root / "sections" / f"{section_type}.liquid"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    m = re.search(r"{%-?\s*schema\s*-?%}(.*?){%-?\s*endschema\s*-?%}", text, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except Exception as e:  # noqa: BLE001
        problem(f"invalid schema JSON in sections/{section_type}.liquid: {e}")
        return {}


scheme_ids = set()
sd = parsed.get("config/settings_data.json")
if sd:
    current = sd.get("current")
    block = sd["presets"][current] if isinstance(current, str) else current
    scheme_ids = set(block.get("color_schemes", {}).keys())


def check_value(where, setting, value):
    t = setting.get("type")
    if t == "select":
        allowed = [o["value"] for o in setting.get("options", [])]
        if value not in allowed:
            problem(f"{where}: {setting['id']}={value!r} not in {allowed}")
    elif t == "range":
        lo, hi = setting.get("min"), setting.get("max")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not (lo <= value <= hi):
            problem(f"{where}: {setting['id']}={value!r} outside {lo}..{hi}")
    elif t == "checkbox":
        if not isinstance(value, bool):
            problem(f"{where}: {setting['id']}={value!r} must be true or false")
    elif t == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            problem(f"{where}: {setting['id']}={value!r} must be a number")
    elif t == "color_scheme":
        if scheme_ids and value not in scheme_ids:
            problem(f"{where}: {setting['id']}={value!r} is not a defined color scheme {sorted(scheme_ids)}")


def check_settings(where, schema_settings, given):
    by_id = {s["id"]: s for s in schema_settings if "id" in s}
    for key, value in (given or {}).items():
        if key not in by_id:
            problem(f"{where}: unknown setting {key!r}")
        else:
            check_value(where, by_id[key], value)


def check_instance(where, inst):
    stype = inst.get("type")
    schema = section_schema(stype)
    if schema is None:
        problem(f"{where}: section type {stype!r} has no sections/{stype}.liquid")
        return
    check_settings(where, schema.get("settings", []), inst.get("settings"))
    blocks_schema = {b["type"]: b for b in schema.get("blocks", [])}
    blocks = inst.get("blocks", {}) or {}
    for bid, b in blocks.items():
        btype = b.get("type")
        if btype not in blocks_schema and not any(x.get("type") == "@app" for x in schema.get("blocks", [])):
            problem(f"{where}: block {bid!r} has unknown type {btype!r}")
            continue
        if btype in blocks_schema:
            check_settings(f"{where} > block {bid}", blocks_schema[btype].get("settings", []), b.get("settings"))
    order = inst.get("block_order")
    if order is not None:
        missing = [o for o in order if o not in blocks]
        if missing:
            problem(f"{where}: block_order lists missing blocks {missing}")


for name, data in parsed.items():
    if not (name.startswith("templates/") or name.endswith("-group.json")):
        continue
    secs = data.get("sections")
    if secs is None:
        continue
    for sid, inst in secs.items():
        check_instance(f"{name} > {sid}", inst)
    order = data.get("order", [])
    miss = [o for o in order if o not in secs]
    extra = [k for k in secs if k not in order]
    if miss:
        problem(f"{name}: order lists missing sections {miss}")
    if extra:
        problem(f"{name}: sections not in order {extra}")

# 4. snippets and assets referenced --------------------------------------------
render_re = re.compile(r"{%-?\s*render\s+'([^']+)'")
asset_re = re.compile(r"'([A-Za-z0-9_.\-]+\.(?:css|js|svg|png|jpg|webp|woff2?))'\s*\|\s*(?:asset_url|inline_asset_content|asset_img_url)")
for p in sorted(list((root / "sections").glob("*.liquid")) + list((root / "snippets").glob("*.liquid")) + list((root / "layout").glob("*.liquid"))):
    text = p.read_text(encoding="utf-8")
    rel = p.relative_to(root).as_posix()
    for m in render_re.finditer(text):
        if not (root / "snippets" / f"{m.group(1)}.liquid").is_file():
            problem(f"{rel}: renders missing snippet {m.group(1)!r}")
    for m in asset_re.finditer(text):
        if not (root / "assets" / m.group(1)).is_file():
            problem(f"{rel}: references missing asset {m.group(1)!r}")

# 5. settings_data keys exist in the schema ------------------------------------
schema = parsed.get("config/settings_schema.json", [])
schema_ids = {s["id"] for g in schema for s in g.get("settings", []) if "id" in s}
if sd:
    block = sd["presets"][sd["current"]] if isinstance(sd.get("current"), str) else sd["current"]
    for key in block:
        if key not in schema_ids and key not in ("sections", "content_for_index", "blocks", "color_schemes"):
            problem(f"config/settings_data.json: key {key!r} is not in settings_schema.json")

if problems:
    print("\n".join(problems))
    print(f"\n{len(problems)} problem(s)")
    sys.exit(1)
print("ok: structure, JSON, templates against schemas, snippets and assets")
