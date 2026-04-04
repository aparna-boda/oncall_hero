# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
FastAPI application for the OnCall Hero Environment.

Exposes the OnCallHeroEnvironment over HTTP endpoints compatible with EnvClient.

Endpoints:
    - POST /reset: Reset the environment and start a new episode
    - POST /step: Execute an action
    - GET /state: Get current environment state
    - GET /schema: Get action/observation schemas
    - GET /health: Health check

Usage:
    # Development:
    cd oncall_hero && uv run server

    # Production:
    uvicorn server.app:app --host 0.0.0.0 --port 8000 --workers 4
"""

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:  # pragma: no cover
    raise ImportError(
        "openenv is required. Install dependencies with '\n    uv sync\n'"
    ) from e

from oncall_hero.models import OnCallAction, OnCallObservation
from oncall_hero.server.oncall_hero_environment import OnCallHeroEnvironment


app = create_app(
    OnCallHeroEnvironment,
    OnCallAction,
    OnCallObservation,
    env_name="oncall_hero",
    max_concurrent_envs=1,
)


def main(host: str = "0.0.0.0", port: int = 8000):
    """Entry point for direct execution via uv run or python -m."""
    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
