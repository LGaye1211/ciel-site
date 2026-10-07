"""CLI: `python -m wfmcp` (MCP over stdio), `python -m wfmcp http`, `python -m wfmcp callback`, `python -m wfmcp validate file.yaml`."""
from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    cmd = argv[0] if argv else "stdio"
    if cmd == "validate":
        from . import spec

        rc = 0
        for f in argv[1:]:
            try:
                wt = spec.parse(open(f).read(), source=f)
                print(f"ok  {f}: {wt.name}@{wt.version} steps={wt.order}")
            except spec.SpecError as e:
                rc = 1
                print(f"ERR {e}")
        return rc
    from .server import build_engine, make_server

    if cmd == "callback":
        from .callback import serve

        serve(build_engine())
        return 0
    server = make_server()
    server.run(transport="streamable-http" if cmd == "http" else "stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
