"""Shared pytest fixtures for hass_mcp tests.

Tests in this suite are intentionally lightweight and use MagicMock for the
``hass`` object rather than spinning up a real Home Assistant instance. We
deliberately do not enable the ``enable_custom_integrations`` fixture
globally — it pops keys from a real hass.data and conflicts with mock tests.
"""

from __future__ import annotations
