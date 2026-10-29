"""Tests for Australian Emergency Hazards integration."""

from .deprecations import install_deprecation_report_handler  # noqa: TID251 - test helper, not production code

# Before conftest imports the integration, so import-time reports are caught too.
install_deprecation_report_handler()
