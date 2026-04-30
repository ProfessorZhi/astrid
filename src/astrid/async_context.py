"""Compatibility shim for async context collection."""

import sys

from astrid.core import async_context as _impl

sys.modules[__name__] = _impl
