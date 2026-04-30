"""Compatibility shim for the installer CLI."""

import sys

from astrid.cli import install as _impl

sys.modules[__name__] = _impl
