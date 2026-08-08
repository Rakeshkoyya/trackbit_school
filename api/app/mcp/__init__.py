"""The MCP server — Streamable HTTP transport over the shared tool registry.

`D-93`: one tool pool, two transports. This package is the second transport;
Lucy is the first. Nothing here knows what a tool *does* — it maps JSON-RPC onto
`services/lucy/registry.py` and back.

Everything in this package was written against the 2025-11-25 MCP specification
and Claude's connector documentation, fetched at implementation time rather than
recalled — `MCP-SERVER-PLAN.md` warns that training data on MCP is stale, and
three details here would each have been wrong from memory: the discovery
handshake is a **401** (a `WWW-Authenticate` header on a 200 is ignored), the
tool schema field is `inputSchema` (camelCase, unlike everything else in this
codebase), and the protected-resource `resource` must equal the URL the user
typed into Claude *exactly*, path included.
"""

from app.mcp.server import mcp_router, well_known_router

__all__ = ["mcp_router", "well_known_router"]
