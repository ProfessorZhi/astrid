"""Compatibility shim for session storage helpers."""

import sys

from astrid.state import session as _impl

sys.modules[__name__] = _impl
