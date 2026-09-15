"""Ops-telemetry plugin entry point.

Registers the four-category telemetry hooks via QwenPaw's
``api.register_runtime_hook`` so they fire on every request that
reaches their phase. Install with::

    qwenpaw plugin install <REPO_ROOT>/poc/plugins/ops-telemetry
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from qwenpaw.plugins.api import PluginApi  # type: ignore[import-not-found]


def _bootstrap_poc() -> None:
    """Keep ``poc.hooks`` importable after the plugin is copied into ~/.qwenpaw."""
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2],
        Path("/root/shunde-poc"),
        Path("/Users/linan/Desktop/aicode/shunde"),
    ]
    for cand in candidates:
        if (cand / "poc" / "hooks" / "ops_hooks.py").is_file():
            text = str(cand)
            if text not in sys.path:
                sys.path.insert(0, text)
            return


_bootstrap_poc()
from poc.hooks.ops_hooks import ALL_HOOKS  # noqa: E402

logger = logging.getLogger("poc.plugins.ops_telemetry")


class PocOpsTelemetryPlugin:
    """Install the six POC telemetry hooks into every workspace."""

    plugin_id = "poc-ops-telemetry"
    plugin_name = "运营埋点 Hook（6 Hook / 5 Phase）"

    def register(self, api: PluginApi) -> None:
        for hook in ALL_HOOKS:
            api.register_runtime_hook(hook)
        logger.info(
            "POC ops telemetry plugin registered %d hooks", len(ALL_HOOKS)
        )


plugin = PocOpsTelemetryPlugin()