"""Compatibility shim for API retry helpers."""

import sys

from astrid.integrations import api_retry as _impl

sys.modules[__name__] = _impl
