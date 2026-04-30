"""Runtime coordination for Astrid frontends.

Keep this package import light: compatibility shims import modules under
``astrid.runtime`` during early startup, before the agent loop is initialized.
"""
