"""Compatibility shim for core shared types."""

import sys

from astrid.core import types as _impl

sys.modules[__name__] = _impl
