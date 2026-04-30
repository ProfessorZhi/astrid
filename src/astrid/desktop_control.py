"""Compatibility shim for desktop control integration."""

import sys

from astrid.integrations import desktop_control as _impl

sys.modules[__name__] = _impl
