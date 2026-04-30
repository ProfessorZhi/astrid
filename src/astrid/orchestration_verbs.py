"""Compatibility shim for orchestration wording helpers."""

import sys

from astrid.core import orchestration_verbs as _impl

sys.modules[__name__] = _impl
