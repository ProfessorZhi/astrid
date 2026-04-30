"""Compatibility shim for the mock model adapter."""

import sys

from astrid.integrations import mock_model as _impl

sys.modules[__name__] = _impl
