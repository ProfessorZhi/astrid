"""Compatibility shim for file review helpers."""

import sys

from astrid.core import file_review as _impl

sys.modules[__name__] = _impl
