"""Compatibility shim for prompt helpers."""

import sys

from astrid.core import prompt as _impl

sys.modules[__name__] = _impl
