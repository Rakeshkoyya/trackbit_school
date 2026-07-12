"""Lucy — the agentic chat layer.

Importing this package registers every tool (read + write) into
`registry.REGISTRY`; the registry itself stays transport-agnostic so a future
MCP server can expose the exact same tools."""

from app.services.lucy import tools_read  # noqa: F401  (registers read tools)

try:  # write tools land in LU-3; the package must import cleanly without them
    from app.services.lucy import tools_write  # noqa: F401
except ImportError:  # pragma: no cover
    pass
