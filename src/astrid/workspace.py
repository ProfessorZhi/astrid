"""Compatibility shim for workspace path helpers."""

import sys

from astrid.core import workspace as _impl

sys.modules[__name__] = _impl
