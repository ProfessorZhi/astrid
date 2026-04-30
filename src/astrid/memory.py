"""Compatibility shim for basic memory helpers."""

import sys

from astrid.state import memory as _impl

sys.modules[__name__] = _impl
