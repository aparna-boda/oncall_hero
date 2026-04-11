# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
OnCall Hero Environment Implementation.

Simulates production data pipeline incidents.
The agent acts as an on-call data engineer: reading logs,
diagnosing root causes, and applying correct remediation actions.
"""

import copy
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

from oncall_hero.models import OnCallAction, OnCallObservation, OnCallState
from oncall_hero.rewards import compute_step_reward


class OnCallHeroEnvironment(Environment):
    """
    OnCall Hero RL environment.

    The agent receives an incident alert, investigates the pipeline failure,
    and applies the correct sequence of remediation actions to restore service.

    Hidden state (_hidden) tracks all ground-truth information that is not
    visible to the agent — root causes, remediation flags, scoring state.
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        self._episode_id = str(uuid4())
        self._step_count = 0
        self._hidden: dict = {}

    def reset(self, task_id: str = "missing_source_file") -> OnCallObservation:  # type: ignore[override]
        """
        Reset the environment for a new episode.

        Args:
            task_id: Which scenario to load. Defaults to 'missing_source_file'.

        Returns:
            Initial OnCallObservation for the selected task.
        """
        self._episode_id = str(uuid4())
        self._step_count = 0

        self._hidden = {
            "task_id": task_id,
            "true_root_cause": None,
            "pipeline_health": "degraded",
            "config_fixed": False,
            "schema_fixed": False,
            "rollback_applied": False,
            "rollback_version_correct": False,
            "rerun_triggered": False,
            "null_data_detected": False,
            "verification_done": False,
            "red_herring_active": True,
            "current_step": 0,
            "max_steps": 6,
            "is_done": False,
            "terminal_reason": None,
            "investigation_score": 0.0,
            "root_cause_score": 0.0,
            "remediation_score": 0.0,
            "efficiency_score": 0.0,
            "sla_score": 0.0,
            "penalty_total": 0.0,
            "actions_taken": [],
            "sla_critical_tables": [],
            "inspect_logs_called": False,
            "pipeline_name": "sales_etl_pipeline",
            "current_obs": {},
        }

        if task_id == "missing_source_file":
            from oncall_hero.tasks.task_easy import get_initial_observation

            obs_data = get_initial_observation()
            self._hidden["true_root_cause"] = "filename_convention_change"
            self._hidden["max_steps"] = 6

        elif task_id == "schema_drift_bigquery":
            from oncall_hero.tasks.task_medium import get_initial_observation
            
            obs_data = get_initial_observation()
            self._hidden["true_root_cause"] = "schema_drift"
            self._hidden["max_steps"] = 10

        elif task_id == "cascade_collapse":
            from oncall_hero.tasks.task_hard import get_initial_observation
            
            obs_data = get_initial_observation()
            self._hidden["true_root_cause"] = "bad_join_logic"
            self._hidden["max_steps"] = 16

        elif task_id == "silent_data_corruption":
            from oncall_hero.tasks.task_extreme import get_initial_observation
            
            obs_data = get_initial_observation()
            self._hidden["true_root_cause"] = "null_price_column"
            self._hidden["max_steps"] = 18

        else:
            obs_data = {
                "task_id": task_id,
                "error_message": f"Unknown task_id: {task_id}",
                "steps_remaining": 0,
            }

        obs_data["done"] = False
        obs_data["reward"] = 0.0
        self._hidden["current_obs"] = dict(obs_data)

        return OnCallObservation(**obs_data)

    def step(self, action: OnCallAction) -> OnCallObservation:  # type: ignore[override]
        """
        Execute one action in the environment.

        Args:
            action: OnCallAction from the agent.

        Returns:
            Updated OnCallObservation with reward and done flag set.
        """
        # Auto-initialize if step() called without reset() (stateless HTTP mode).
        # Multi-step episodes should use the WebSocket/EnvClient path.
        if not self._hidden:
            self.reset()

        if self._hidden.get("is_done", False):
            from oncall_hero.graders import grade
            task_id_done = self._hidden.get("task_id", "missing_source_file")
            final_score = grade(task_id_done, list(self._hidden.get("actions_taken", [])), self._hidden)
            current = dict(self._hidden.get("current_obs", {}))
            current["last_action_result"] = "Episode already complete."
            current["done"] = True
            current["reward"] = final_score
            current["steps_remaining"] = 0
            return OnCallObservation(**current)

        self._step_count += 1
        self._hidden["current_step"] = self._hidden.get("current_step", 0) + 1

        task_id = self._hidden.get("task_id", "missing_source_file")

        # Snapshot hidden state BEFORE mutation so rewards.py can compare transitions.
        hidden_before = copy.deepcopy(self._hidden)

        if task_id == "missing_source_file":
            from oncall_hero.tasks.task_easy import handle_action
            obs_updates, done = handle_action(action, self._hidden)

        elif task_id == "schema_drift_bigquery":
            from oncall_hero.tasks.task_medium import handle_action
            obs_updates, done = handle_action(action, self._hidden)

        elif task_id == "cascade_collapse":
            from oncall_hero.tasks.task_hard import handle_action
            obs_updates, done = handle_action(action, self._hidden)

        elif task_id == "silent_data_corruption":
            from oncall_hero.tasks.task_extreme import handle_action
            obs_updates, done = handle_action(action, self._hidden)

        else:
            obs_updates = {"last_action_result": f"Unknown task: {task_id}"}
            done = True

        reward = compute_step_reward(
            action.action_type,
            action.target,
            action.parameters,
            hidden_before,
            self._hidden,
            task_id,
            done,
        )

        self._hidden["actions_taken"].append(action.action_type)

        steps_remaining = max(0, self._hidden["max_steps"] - self._hidden["current_step"])
        if steps_remaining == 0 and not done:
            done = True
            suffix = " [Max steps reached — episode ended]"
            obs_updates["last_action_result"] = obs_updates.get("last_action_result", "") + suffix

        if done:
            self._hidden["is_done"] = True
            # Replace step reward with final grader score so the done=True
            # response carries a value strictly in (0.01, 0.99).
            from oncall_hero.graders import grade
            reward = grade(task_id, list(self._hidden["actions_taken"]), self._hidden)
        else:
            # Clamp intermediate rewards to (0.01, 0.99) so every /step
            # response satisfies the openenv strict (0, 1) range requirement.
            reward = max(0.01, min(0.99, reward))

        current = dict(self._hidden.get("current_obs", {}))
        current.update(obs_updates)
        current["steps_remaining"] = steps_remaining
        current["actions_taken"] = list(self._hidden["actions_taken"])
        current["done"] = done
        current["reward"] = reward
        self._hidden["current_obs"] = current

        return OnCallObservation(**current)

    @property
    def state(self) -> State:
        """Return current episode state."""
        kwargs = dict(self._hidden)
        
        # Remove internal tracking fields not defined in OnCallState
        kwargs.pop("current_obs", None)
        kwargs.pop("current_step", None)
        kwargs.pop("max_steps", None)
        kwargs.pop("inspect_logs_called", None)
        kwargs.pop("pipeline_name", None)
        
        # Ensure correct defaults to avoid Pydantic validation errors
        if kwargs.get("true_root_cause") is None:
            kwargs["true_root_cause"] = ""
        if kwargs.get("terminal_reason") is None:
            kwargs["terminal_reason"] = ""
            
        return OnCallState(
            episode_id=self._episode_id,
            step_count=self._step_count,
            **kwargs
        )
