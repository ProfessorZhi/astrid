"""Compatibility shim for local tool shortcut parsing."""

import sys

from astrid.runtime import local_tool_shortcuts as _impl

sys.modules[__name__] = _impl
