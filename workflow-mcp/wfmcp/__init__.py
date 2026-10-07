"""wfmcp: a small, flexible workflow engine exposed over MCP, with MS Teams notifications.

The engine never calls a model. Agents (Cowork, Claude Code) are the workers for
`agent` steps; humans answer `human` and `approval` steps from Teams cards; the
engine is the ledger, the router and the notifier.
"""
__version__ = "0.1.0"
