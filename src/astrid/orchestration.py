"""Compatibility shim for orchestration helpers."""

import sys

from astrid.core import orchestration as _impl

sys.modules[__name__] = _impl
