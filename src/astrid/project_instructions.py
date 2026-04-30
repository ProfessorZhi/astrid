"""Compatibility shim for project instruction loading."""

import sys

from astrid.core import project_instructions as _impl

sys.modules[__name__] = _impl
