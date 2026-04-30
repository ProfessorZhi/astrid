"""Compatibility shim for runtime cost tracking."""

import sys

from astrid.runtime import cost_tracker as _impl

sys.modules[__name__] = _impl
