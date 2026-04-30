"""Compatibility shim for tool registry primitives."""

import sys

from astrid.core import tooling as _impl

sys.modules[__name__] = _impl
