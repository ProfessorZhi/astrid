"""Compatibility shim for skill integration helpers."""

import sys

from astrid.integrations import skills as _impl

sys.modules[__name__] = _impl
