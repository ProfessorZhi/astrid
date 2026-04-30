"""Compatibility shim for hook integration helpers."""

import sys

from astrid.integrations import hooks as _impl

sys.modules[__name__] = _impl
