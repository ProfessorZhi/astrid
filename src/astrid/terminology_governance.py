"""Compatibility shim for terminology governance integration."""

import sys

from astrid.integrations import terminology_governance as _impl

sys.modules[__name__] = _impl
