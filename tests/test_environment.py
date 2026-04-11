# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for OnCallHeroEnvironment — reset, step, routing, and state."""

import pytest

from oncall_hero.models import OnCallAction, OnCallObservation, OnCallState
from oncall_hero.server.oncall_hero_environment import OnCallHeroEnvironment


def _act(action_type, target="pipeline", **params):
    return OnCallAction(action_type=action_type, target=target, parameters=params)


# ------------------------------------------------------------------ #
# Reset
# ------------------------------------------------------------------ #

class TestReset:
    def test_returns_oncall_observation(self):
        env = OnCallHeroEnvironment()
        obs = env.reset("missing_source_file")
        assert isinstance(obs, OnCallObservation)

    def test_easy_fields(self):
        obs = OnCallHeroEnvironment().reset("missing_source_file")
        assert obs.task_id == "missing_source_file"
        assert obs.pipeline_name == "sales_etl_pipeline"
        assert obs.steps_remaining == 6

    def test_medium_fields(self):
        obs = OnCallHeroEnvironment().reset("schema_drift_bigquery")
        assert obs.task_id == "schema_drift_bigquery"
        assert obs.pipeline_name == "inventory_load_pipeline"
        assert obs.steps_remaining == 10

    def test_hard_fields(self):
        obs = OnCallHeroEnvironment().reset("cascade_collapse")
        assert obs.task_id == "cascade_collapse"
        assert obs.steps_remaining == 16
        assert obs.sla_breach is True

    def test_extreme_fields(self):
        obs = OnCallHeroEnvironment().reset("silent_data_corruption")
        assert obs.task_id == "silent_data_corruption"
        assert obs.steps_remaining == 18
        assert obs.sla_breach is True

    def test_unknown_task_returns_error_observation(self):
        obs = OnCallHeroEnvironment().reset("bogus_task")
        assert "bogus_task" in obs.error_message or obs.steps_remaining == 0

    def test_reset_clears_previous_state(self):
        env = OnCallHeroEnvironment()
        env.reset("missing_source_file")
        env.step(_act("inspect_logs"))
        env.step(_act("fix_pipeline_config"))
        env.reset("missing_source_file")
        assert env._step_count == 0
        assert env._hidden["is_done"] is False
        assert env._hidden["actions_taken"] == []

    def test_reset_generates_new_episode_id(self):
        env = OnCallHeroEnvironment()
        env.reset("missing_source_file")
        id1 = env._episode_id
        env.reset("missing_source_file")
        id2 = env._episode_id
        assert id1 != id2

    def test_reset_sets_true_root_cause_easy(self):
        env = OnCallHeroEnvironment()
        env.reset("missing_source_file")
        assert env._hidden["true_root_cause"] == "filename_convention_change"

    def test_reset_sets_true_root_cause_hard(self):
        env = OnCallHeroEnvironment()
        env.reset("cascade_collapse")
        assert env._hidden["true_root_cause"] == "bad_join_logic"

    def test_reset_sets_true_root_cause_medium(self):
        env = OnCallHeroEnvironment()
        env.reset("schema_drift_bigquery")
        assert env._hidden["true_root_cause"] == "schema_drift"

    def test_reset_sets_true_root_cause_extreme(self):
        env = OnCallHeroEnvironment()
        env.reset("silent_data_corruption")
        assert env._hidden["true_root_cause"] == "null_price_column"

    def test_reset_done_is_false(self):
        obs = OnCallHeroEnvironment().reset("missing_source_file")
        assert obs.done is False

    def test_reset_reward_is_zero(self):
        obs = OnCallHeroEnvironment().reset("missing_source_file")
        assert obs.reward == pytest.approx(0.0)


# ------------------------------------------------------------------ #
# Step routing — correct task handler called
# ------------------------------------------------------------------ #

class TestStepRouting:
    def test_easy_inspect_logs_reward(self):
        env = OnCallHeroEnvironment()
        env.reset("missing_source_file")
        obs = env.step(_act("inspect_logs"))
        assert obs.reward == pytest.approx(0.05)
        assert obs.done is False

    def test_medium_inspect_logs_reward(self):
        env = OnCallHeroEnvironment()
        env.reset("schema_drift_bigquery")
        obs = env.step(_act("inspect_logs"))
        # Task 2 gives 0.10 for inspect_logs, not 0.05
        assert obs.reward == pytest.approx(0.10)

    def test_hard_inspect_logs_reward(self):
        env = OnCallHeroEnvironment()
        env.reset("cascade_collapse")
        obs = env.step(_act("inspect_logs"))
        assert obs.reward == pytest.approx(0.08)

    def test_extreme_profile_data_reward(self):
        env = OnCallHeroEnvironment()
        env.reset("silent_data_corruption")
        obs = env.step(_act("profile_data"))
        # Pre-fix profile: 0.15
        assert obs.reward == pytest.approx(0.15)

    def test_easy_optimal_sequence_done(self):
        env = OnCallHeroEnvironment()
        env.reset("missing_source_file")
        env.step(_act("inspect_logs"))
        env.step(_act("fix_pipeline_config"))
        obs = env.step(_act("trigger_rerun"))
        assert obs.done is True
        assert obs.reward == pytest.approx(0.99)  # grader score replaces step reward on done

    def test_medium_trigger_rerun_without_fix_fails(self):
        env = OnCallHeroEnvironment()
        env.reset("schema_drift_bigquery")
        env.step(_act("inspect_logs"))
        obs = env.step(_act("trigger_rerun"))
        assert obs.done is False
        assert obs.reward == pytest.approx(-0.20)

    def test_hard_rollback_correct_version(self):
        env = OnCallHeroEnvironment()
        env.reset("cascade_collapse")
        env.step(_act("inspect_logs"))
        obs = env.step(_act("rollback_deployment", version="3.1.0"))
        assert obs.reward == pytest.approx(0.20)

    def test_hard_rollback_wrong_version_penalty(self):
        env = OnCallHeroEnvironment()
        env.reset("cascade_collapse")
        env.step(_act("inspect_logs"))
        obs = env.step(_act("rollback_deployment", version="3.1.1"))
        assert obs.reward == pytest.approx(-0.40)

    def test_extreme_rollback_correct_version(self):
        env = OnCallHeroEnvironment()
        env.reset("silent_data_corruption")
        obs = env.step(_act("rollback_deployment", version="4.1.5"))
        assert obs.reward == pytest.approx(0.15)


# ------------------------------------------------------------------ #
# Done and step-limit mechanics
# ------------------------------------------------------------------ #

class TestDoneAndStepLimit:
    def test_step_after_done_returns_complete_message(self):
        env = OnCallHeroEnvironment()
        env.reset("missing_source_file")
        env.step(_act("inspect_logs"))
        env.step(_act("fix_pipeline_config"))
        env.step(_act("trigger_rerun"))  # done=True here
        obs = env.step(_act("inspect_logs"))
        assert obs.done is True
        assert obs.reward == pytest.approx(0.99)  # grader score returned for already-done episodes
        assert obs.steps_remaining == 0
        assert "Episode already complete" in obs.last_action_result

    def test_step_limit_triggers_done(self):
        env = OnCallHeroEnvironment()
        env.reset("missing_source_file")  # max_steps=6
        obs = None
        for _ in range(6):
            obs = env.step(_act("notify_stakeholder", team="any"))
        assert obs.done is True
        assert "Max steps reached" in obs.last_action_result

    def test_steps_remaining_decrements(self):
        env = OnCallHeroEnvironment()
        env.reset("missing_source_file")
        obs1 = env.step(_act("inspect_logs"))
        assert obs1.steps_remaining == 5
        obs2 = env.step(_act("notify_stakeholder", team="any"))
        assert obs2.steps_remaining == 4

    def test_steps_remaining_never_negative(self):
        env = OnCallHeroEnvironment()
        env.reset("missing_source_file")
        obs = None
        for _ in range(8):
            obs = env.step(_act("notify_stakeholder", team="any"))
        assert obs.steps_remaining == 0

    def test_actions_taken_accumulates(self):
        env = OnCallHeroEnvironment()
        env.reset("missing_source_file")
        env.step(_act("inspect_logs"))
        obs = env.step(_act("fix_pipeline_config"))
        assert obs.actions_taken == ["inspect_logs", "fix_pipeline_config"]

    def test_pipeline_health_restored_after_optimal_easy(self):
        env = OnCallHeroEnvironment()
        env.reset("missing_source_file")
        env.step(_act("inspect_logs"))
        env.step(_act("fix_pipeline_config"))
        env.step(_act("trigger_rerun"))
        assert env._hidden["pipeline_health"] == "restored"


# ------------------------------------------------------------------ #
# Auto-init (step without reset)
# ------------------------------------------------------------------ #

class TestAutoInit:
    def test_step_without_reset_returns_observation(self):
        env = OnCallHeroEnvironment()
        obs = env.step(_act("inspect_logs"))
        assert isinstance(obs, OnCallObservation)

    def test_step_without_reset_defaults_to_easy_task(self):
        env = OnCallHeroEnvironment()
        obs = env.step(_act("inspect_logs"))
        # Auto-init uses missing_source_file; inspect_logs reward should be 0.05
        assert obs.reward == pytest.approx(0.05)


# ------------------------------------------------------------------ #
# State property
# ------------------------------------------------------------------ #

class TestStateProperty:
    def test_state_returns_oncall_state(self):
        env = OnCallHeroEnvironment()
        env.reset("missing_source_file")
        assert isinstance(env.state, OnCallState)

    def test_state_reflects_root_cause_medium(self):
        env = OnCallHeroEnvironment()
        env.reset("schema_drift_bigquery")
        assert env.state.true_root_cause == "schema_drift"

    def test_state_is_done_updates_after_terminal_step(self):
        env = OnCallHeroEnvironment()
        env.reset("missing_source_file")
        env.step(_act("inspect_logs"))
        env.step(_act("fix_pipeline_config"))
        env.step(_act("trigger_rerun"))
        assert env.state.is_done is True

    def test_state_is_done_false_before_terminal(self):
        env = OnCallHeroEnvironment()
        env.reset("missing_source_file")
        env.step(_act("inspect_logs"))
        assert env.state.is_done is False

    def test_state_actions_taken_matches_obs(self):
        env = OnCallHeroEnvironment()
        env.reset("missing_source_file")
        env.step(_act("inspect_logs"))
        obs = env.step(_act("fix_pipeline_config"))
        assert env.state.actions_taken == obs.actions_taken

    def test_state_task_id_set_after_reset(self):
        env = OnCallHeroEnvironment()
        env.reset("cascade_collapse")
        assert env.state.task_id == "cascade_collapse"

    def test_state_pipeline_health_starts_degraded(self):
        env = OnCallHeroEnvironment()
        env.reset("missing_source_file")
        assert env.state.pipeline_health == "degraded"
