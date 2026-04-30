"""Compatibility shim for bootstrap integration helpers."""

import sys

from astrid.integrations import bootstrap_system as _impl

sys.modules[__name__] = _impl
