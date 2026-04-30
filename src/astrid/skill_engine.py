"""Compatibility shim for skill engine integration."""

import sys

from astrid.integrations import skill_engine as _impl

sys.modules[__name__] = _impl
