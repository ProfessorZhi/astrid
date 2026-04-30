"""Compatibility shim for sub-agent orchestration."""

import sys

from astrid.core import sub_agents as _impl

sys.modules[__name__] = _impl
