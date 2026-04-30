"""Compatibility shim for runtime logging configuration."""

import sys

from astrid.runtime import logging_config as _impl

sys.modules[__name__] = _impl
