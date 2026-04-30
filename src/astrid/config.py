"""Compatibility shim for runtime configuration."""

import sys

from astrid.runtime import config as _impl

sys.modules[__name__] = _impl
