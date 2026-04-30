"""Compatibility shim for runtime background task tracking."""

import sys

from astrid.runtime import background_tasks as _impl

sys.modules[__name__] = _impl
