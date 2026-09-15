"""Ops-telemetry plugin entry point.

Bundles the JSONL sink next to this file so ``qwenpaw plugin install``
copies a working writer even when ``/root/shunde-poc/poc/hooks`` is stale.

    qwenpaw plugin install <REPO_ROOT>/poc/plugins/ops-telemetry
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from qwenpaw.plugins.api import PluginApi  # type: ignore[import-not-found]

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from sink.ops_hooks import ALL_HOOKS  # noqa: E402
from sink import telemetry as _telemetry  # noqa: E402

_pin_candidates = [Path("/root/shunde-poc")]
for _parent in _HERE.parents:
    if (_parent / "poc" / "hooks" / "ops_hooks.py").is_file():
        _pin_candidates.append(_parent)
        break
_telemetry.pin_host_sandbox(_pin_candidates)

logger = logging.getLogger("poc.plugins.ops_telemetry")


class PocOpsTelemetryPlugin:
    """Install the six POC telemetry hooks into every workspace."""

    plugin_id = "poc-ops-telemetry"
    plugin_name = "运营埋点 Hook（6 Hook / 5 Phase）"

    def register(self, api: PluginApi) -> None:
        for hook in ALL_HOOKS:
            api.register_runtime_hook(hook)
        path = _telemetry.write_plugin_loaded([h.name for h in ALL_HOOKS])
        logger.info(
            "POC ops telemetry plugin registered %d hooks jsonl=%s",
            len(ALL_HOOKS),
            path,
        )


plugin = PocOpsTelemetryPlugin()
