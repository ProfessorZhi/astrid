"""Compatibility shim for management CLI commands."""

import sys

from astrid.cli import manage_cli as _impl

sys.modules[__name__] = _impl
