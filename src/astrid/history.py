"""Compatibility shim for history storage helpers."""

import sys

from astrid.state import history as _impl

sys.modules[__name__] = _impl
