"""Ops-telemetry plugin entry point.

Registers the four-category telemetry hooks via QwenPaw's
``api.register_runtime_hook`` so they fire on every request that
reaches their phase. Install with::

    qwenpaw plugin install <REPO_ROOT>/poc/plugins/ops-telemetry
"""

from __future__ import annotations

import logging

from qwenpaw.plugins.api import PluginApi  # type: ignore[import-not-found]

from poc.hooks.ops_hooks import ALL_HOOKS

logger = logging.getLogger("poc.plugins.ops_telemetry")


class PocOpsTelemetryPlugin:
    """Install the six POC telemetry hooks into every workspace."""

    plugin_id = "poc-ops-telemetry"
    plugin_name = "POC Ops Telemetry"

    def register(self, api: PluginApi) -> None:
        for hook in ALL_HOOKS:
            api.register_runtime_hook(hook)
        logger.info(
            "POC ops telemetry plugin registered %d hooks", len(ALL_HOOKS)
        )