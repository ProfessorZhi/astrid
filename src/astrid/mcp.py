"""Compatibility shim for MCP integration helpers."""

import sys

from astrid.integrations import mcp as _impl

sys.modules[__name__] = _impl
