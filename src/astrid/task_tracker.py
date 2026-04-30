"""Compatibility shim for runtime task tracking."""

import sys

from astrid.runtime import task_tracker as _impl

sys.modules[__name__] = _impl
