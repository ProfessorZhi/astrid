"""Compatibility shim for interactive slash commands."""

import sys

from astrid.cli import cli_commands as _impl

sys.modules[__name__] = _impl
