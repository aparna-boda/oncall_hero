# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""OnCall Hero Environment Client."""

from typing import Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State

from oncall_hero.models import OnCallAction, OnCallObservation


class OnCallHeroEnv(
    EnvClient[OnCallAction, OnCallObservation, State]
):
    """
    Client for the OnCall Hero Environment.

    Maintains a persistent WebSocket connection to the environment server,
    enabling efficient multi-step interactions.

    Example:
        >>> with OnCallHeroEnv(base_url="http://localhost:8000") as client:
        ...     result = client.reset(task_id="missing_source_file")
        ...     print(result.observation.error_message)
        ...
        ...     result = client.step(OnCallAction(
        ...         action_type="inspect_logs",
        ...         target="extract_s3_sales",
        ...         justification="Check what failed"
        ...     ))
        ...     print(result.observation.log_details)
    """

    def _step_payload(self, action: OnCallAction) -> Dict:
        """Convert OnCallAction to JSON payload for the step endpoint."""
        return {
            "action_type": action.action_type,
            "target": action.target,
            "parameters": action.parameters,
            "justification": action.justification,
        }

    def _parse_result(self, payload: Dict) -> StepResult[OnCallObservation]:
        """Parse server step response into StepResult[OnCallObservation]."""
        obs_data = payload.get("observation", {})
        observation = OnCallObservation(**obs_data)

        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> State:
        """Parse server state response into State object."""
        return State(
            episode_id=payload.get("episode_id", ""),
            step_count=payload.get("step_count", 0),
        )
