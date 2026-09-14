# -*- coding: utf-8 -*-
"""QwenPaw plugin entry point that mounts the POC /health router.

Install with::

    qwenpaw plugin install <REPO_ROOT>/poc/plugins/health

After install, ``GET /api/poc/health`` returns ``{"status": "ok"}``.

Note: a plugin is *invoked* by QwenPaw through a discoverable entry
point; for development-time smoke testing this file can also be run
directly to confirm the router wires up correctly::

    python -m poc.plugins.health.plugin
"""

from __future__ import annotations

import logging

from qwenpaw.plugins.api import PluginApi  # type: ignore[import-not-found]

from .router import router

logger = logging.getLogger("poc.plugins.health")


class PocHealthPlugin:
    """Mount ``GET /api/poc/health`` on the host FastAPI app."""

    plugin_id = "poc-health"
    plugin_name = "POC Health Check"

    def register(self, api: PluginApi) -> None:
        """Called by QwenPaw once during plugin install."""
        api.register_http_router(
            router,
            prefix="/poc",
            tags=["poc-health"],
        )
        logger.info("POC health plugin registered at /api/poc/health")


plugin = PocHealthPlugin()


def main() -> None:
    """Dev entry: print the route table to confirm registration."""
    for r in router.routes:
        if hasattr(r, "methods") and hasattr(r, "path"):
            print(",".join(sorted(r.methods)), r.path)