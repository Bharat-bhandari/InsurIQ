"""PolicyDesk MCP server package (Step 5.2 SPIKE).

Exposes ONE tool — get_waiting_periods — through the MCP protocol so it can be
registered behind the TrueFoundry MCP Gateway. THIN wrapper only: the handler
delegates to the canonical `_get_waiting_periods_body()` in src.tools.registry.
No chaos, no retry, no tool logic here — those stay client-side in the graph
(CONTEXT.md §A4)."""
