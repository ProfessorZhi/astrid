"""Compatibility shim for the Anthropic model adapter."""

import sys

from astrid.integrations import anthropic_adapter as _impl

sys.modules[__name__] = _impl
