"""Compatibility shim for context management helpers."""

import sys

from astrid.core import context_manager as _impl

sys.modules[__name__] = _impl
