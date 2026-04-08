# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for all grader functions."""

import pytest

from oncall_hero.graders import (
    grade,
    grade_task_easy,
    grade_task_hard,
    grade_task_medium,
    grade_task_extreme,
)


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _hard_optimal_hidden():
    return {
        "t3_rollback_target": "3.1.0",
        "t3_tables_rerun": ["revenue_daily", "customer_summary", "marketing_segments"],
        "t3_notified_teams": {"sla", "ads"},
        "rerun_triggered": True,
        "rerun_order_correct": True,
        "rollback_applied": True,
    }

def _extreme_optimal_hidden():
    return {
        "t4_rollback_target": "4.1.5",
        "rerun_triggered": True,
        "verification_done": True,
        "t4_notified_teams": {"revenue", "crm"},
        "is_done": True,
        "rollback_applied": True,
    }


# ------------------------------------------------------------------ #
# grade_task_easy
# ------------------------------------------------------------------ #

class TestGradeTaskEasy:
    def test_optimal_path(self):
        actions = ["inspect_logs", "fix_pipeline_config", "trigger_rerun"]
        hidden = {"inspect_logs_called": True}
        assert grade_task_easy(actions, hidden) == pytest.approx(1.0)

    def test_rerun_before_fix_penalty(self):
        actions = ["inspect_logs", "trigger_rerun", "fix_pipeline_config"]
        hidden = {"inspect_logs_called": True}
        optimal = grade_task_easy(["inspect_logs", "fix_pipeline_config", "trigger_rerun"], {"inspect_logs_called": True})
        penalised = grade_task_easy(actions, hidden)
        assert penalised < optimal - 0.25

    def test_rerun_without_fix_penalty(self):
        actions = ["inspect_logs", "trigger_rerun"]
        hidden = {"inspect_logs_called": True}
        score = grade_task_easy(actions, hidden)
        # 0.30 penalty for rerun without fix; optimal contribution of fix+rerun is ~0.45, so score should be low
        assert score < 0.60

    def test_irrelevant_action_deducts_penalty(self):
        # 3-step base (efficiency=0.10) vs 4-step with check_schema (efficiency=0.05 + 0.10 penalty = -0.15 total)
        base = ["inspect_logs", "fix_pipeline_config", "trigger_rerun"]
        with_irrelevant = ["inspect_logs", "check_schema", "fix_pipeline_config", "trigger_rerun"]
        hidden = {"inspect_logs_called": True}
        assert grade_task_easy(with_irrelevant, hidden) == pytest.approx(
            grade_task_easy(base, hidden) - 0.15  # 0.10 irrelevant penalty + 0.05 efficiency drop
        )

    def test_multiple_irrelevant_actions_stack(self):
        actions = ["check_schema", "rollback_deployment", "fix_pipeline_config"]
        hidden = {"inspect_logs_called": False}
        single_irrelevant = ["check_schema", "fix_pipeline_config"]
        diff = grade_task_easy(single_irrelevant, hidden) - grade_task_easy(actions, hidden)
        assert diff == pytest.approx(0.10)

    def test_skip_task_clamps_to_zero(self):
        assert grade_task_easy(["skip_task"], {}) == pytest.approx(0.0)

    def test_efficiency_3_or_fewer_steps(self):
        actions_3 = ["inspect_logs", "fix_pipeline_config", "trigger_rerun"]
        # Use notify_stakeholder (no penalty) to pad to 5 steps without irrelevant-action penalties
        actions_5 = ["inspect_logs", "notify_stakeholder", "notify_stakeholder", "fix_pipeline_config", "trigger_rerun"]
        hidden = {"inspect_logs_called": True}
        assert grade_task_easy(actions_3, hidden) - grade_task_easy(actions_5, hidden) == pytest.approx(0.10)

    def test_efficiency_exactly_4_steps(self):
        actions_4 = ["inspect_logs", "notify_stakeholder", "fix_pipeline_config", "trigger_rerun"]
        actions_5 = ["inspect_logs", "notify_stakeholder", "notify_stakeholder", "fix_pipeline_config", "trigger_rerun"]
        hidden = {"inspect_logs_called": True}
        diff = grade_task_easy(actions_4, hidden) - grade_task_easy(actions_5, hidden)
        assert diff == pytest.approx(0.05)

    def test_efficiency_5_or_more_steps_zero(self):
        # 7 steps: efficiency=0.0; 3-step optimal: efficiency=0.10
        actions = ["inspect_logs"] * 5 + ["fix_pipeline_config", "trigger_rerun"]
        hidden = {"inspect_logs_called": True}
        score = grade_task_easy(actions, hidden)
        optimal = grade_task_easy(["inspect_logs", "fix_pipeline_config", "trigger_rerun"], {"inspect_logs_called": True})
        assert optimal - score == pytest.approx(0.10)

    def test_sla_always_full_even_with_no_actions(self):
        score = grade_task_easy([], {})
        # 0 steps → efficiency=0.10; no distractor chased → investigation bonus=0.05;
        # sla=0.10; root_cause=0; remediation=0 → total=0.25
        assert score == pytest.approx(0.25)

    def test_no_logs_reduces_root_cause(self):
        actions = ["fix_pipeline_config"]
        hidden = {"inspect_logs_called": False}
        score = grade_task_easy(actions, hidden)
        # investigation: no inspect_logs=0, no distractor=+0.05 → 0.05
        # root_cause: no logs=0, fix present=+0.10 → 0.10
        # remediation: fix present=+0.15, no rerun=0 → 0.15
        # efficiency: 1 step ≤ 3 → 0.10
        # sla: 0.10  →  total = 0.50
        assert score == pytest.approx(0.50)

    def test_result_never_negative(self):
        actions = ["trigger_rerun", "skip_task"] + ["check_schema"] * 10
        assert grade_task_easy(actions, {}) >= 0.0

    def test_result_never_above_one(self):
        actions = ["inspect_logs", "fix_pipeline_config", "trigger_rerun"]
        hidden = {"inspect_logs_called": True}
        assert grade_task_easy(actions, hidden) <= 1.0


# ------------------------------------------------------------------ #
# grade_task_medium
# ------------------------------------------------------------------ #

class TestGradeTaskMedium:
    def _optimal_hidden(self):
        return {
            "t2_discount_added": True,
            "t2_quantity_fixed": True,
            "schema_fixed": True,
            "rerun_triggered": True,
        }

    def test_optimal_path(self):
        actions = ["inspect_logs", "check_schema", "alter_table", "alter_table", "trigger_rerun"]
        assert grade_task_medium(actions, self._optimal_hidden()) == pytest.approx(1.0)

    def test_rollback_red_herring_penalty(self):
        actions = ["inspect_logs", "rollback_deployment", "trigger_rerun"]
        hidden = {"t2_discount_added": False, "t2_quantity_fixed": False}
        score = grade_task_medium(actions, hidden)
        # 0.40 penalty for rollback; no schema fix bonuses
        assert score == pytest.approx(0.0)

    def test_partial_fix_no_restore_bonus(self):
        hidden = {
            "t2_discount_added": True,
            "t2_quantity_fixed": False,
            "schema_fixed": False,
            "rerun_triggered": False,
        }
        actions = ["inspect_logs", "check_schema", "alter_table"]
        score = grade_task_medium(actions, hidden)
        # No 0.20 restore bonus; only inspect(0.10) + check_schema(0.10) + no-rollback(0.10) + discount(0.25)
        assert score == pytest.approx(0.55)

    def test_scale_up_executor_penalty(self):
        actions_clean = ["inspect_logs", "check_schema", "alter_table", "alter_table", "trigger_rerun"]
        actions_penalty = ["inspect_logs", "check_schema", "scale_up_executor", "alter_table", "alter_table", "trigger_rerun"]
        hidden = self._optimal_hidden()
        assert grade_task_medium(actions_penalty, hidden) == pytest.approx(
            grade_task_medium(actions_clean, hidden) - 0.10
        )

    def test_check_schema_before_alter_bonus(self):
        # With check_schema before any alter_table
        actions_ordered = ["check_schema", "alter_table"]
        actions_unordered = ["alter_table", "check_schema"]
        hidden = {"t2_discount_added": True, "t2_quantity_fixed": False, "schema_fixed": False, "rerun_triggered": False}
        assert grade_task_medium(actions_ordered, hidden) > grade_task_medium(actions_unordered, hidden)

    def test_no_rollback_bonus_included(self):
        actions = ["inspect_logs"]
        hidden = {"t2_discount_added": False, "t2_quantity_fixed": False, "schema_fixed": False, "rerun_triggered": False}
        score = grade_task_medium(actions, hidden)
        # inspect(0.10) + no-rollback bonus(0.10) = 0.20
        assert score == pytest.approx(0.20)

    def test_result_clamped_to_zero(self):
        actions = ["rollback_deployment", "scale_up_executor"]
        assert grade_task_medium(actions, {}) == pytest.approx(0.0)

    def test_result_never_above_one(self):
        actions = ["inspect_logs", "check_schema", "alter_table", "alter_table", "trigger_rerun"]
        assert grade_task_medium(actions, self._optimal_hidden()) <= 1.0


# ------------------------------------------------------------------ #
# grade_task_hard
# ------------------------------------------------------------------ #

class TestGradeTaskHard:
    def test_optimal_path(self):
        actions = [
            "inspect_logs", "check_dependencies",
            "rollback_deployment",
            "trigger_rerun", "trigger_rerun", "trigger_rerun",
            "notify_stakeholder", "notify_stakeholder",
        ]
        assert grade_task_hard(actions, _hard_optimal_hidden()) == pytest.approx(1.0)

    def test_wrong_rollback_3_1_1_penalty(self):
        hidden = dict(_hard_optimal_hidden())
        hidden["t3_rollback_target"] = "3.1.1"
        actions = ["inspect_logs", "check_dependencies", "rollback_deployment",
                   "trigger_rerun", "trigger_rerun", "trigger_rerun", "notify_stakeholder"]
        score = grade_task_hard(actions, hidden)
        # 0.40 penalty; should be well below optimal
        assert score < 0.70

    def test_rerun_out_of_order_penalty(self):
        hidden = dict(_hard_optimal_hidden())
        hidden["t3_tables_rerun"] = ["customer_summary", "revenue_daily", "marketing_segments"]
        hidden["rerun_order_correct"] = False
        actions = ["inspect_logs", "check_dependencies", "rollback_deployment",
                   "trigger_rerun", "trigger_rerun", "trigger_rerun", "notify_stakeholder"]
        score = grade_task_hard(actions, hidden)
        optimal = grade_task_hard(
            ["inspect_logs", "check_dependencies", "rollback_deployment",
             "trigger_rerun", "trigger_rerun", "trigger_rerun", "notify_stakeholder"],
            _hard_optimal_hidden()
        )
        assert score < optimal

    def test_rerun_before_rollback_penalty(self):
        hidden = dict(_hard_optimal_hidden())
        hidden["rollback_applied"] = False
        actions = ["inspect_logs", "trigger_rerun"]
        score = grade_task_hard(actions, hidden)
        # 0.30 premature-rerun penalty fires
        assert score < grade_task_hard(["inspect_logs"], _hard_optimal_hidden())

    def test_scale_up_executor_penalty_and_no_bonus(self):
        hidden = dict(_hard_optimal_hidden())
        actions_with = ["inspect_logs", "scale_up_executor", "check_dependencies",
                        "rollback_deployment", "trigger_rerun", "trigger_rerun", "trigger_rerun", "notify_stakeholder"]
        actions_without = ["inspect_logs", "check_dependencies",
                           "rollback_deployment", "trigger_rerun", "trigger_rerun", "trigger_rerun", "notify_stakeholder"]
        # With scale_up: loses 0.08 bonus (now penalised) + 0.20 penalty
        assert grade_task_hard(actions_with, hidden) < grade_task_hard(actions_without, hidden)

    def test_no_alter_table_bonus(self):
        hidden = {"t3_rollback_target": "3.1.0", "t3_tables_rerun": [], "t3_notified_teams": set(),
                  "rollback_applied": True}
        without_alter = ["inspect_logs"]
        with_alter = ["inspect_logs", "alter_table"]
        assert grade_task_hard(without_alter, hidden) > grade_task_hard(with_alter, hidden)

    def test_skip_sla_table_penalty(self):
        hidden = dict(_hard_optimal_hidden())
        actions_skip = ["inspect_logs", "skip_task"]
        actions_clean = ["inspect_logs"]
        assert grade_task_hard(actions_skip, hidden) < grade_task_hard(actions_clean, hidden)

    def test_sla_team_notification_bonus(self):
        hidden_with = {"t3_rollback_target": "3.1.0", "t3_tables_rerun": [], "t3_notified_teams": {"sla"}, "rollback_applied": True}
        hidden_without = {"t3_rollback_target": "3.1.0", "t3_tables_rerun": [], "t3_notified_teams": set(), "rollback_applied": True}
        actions = ["inspect_logs"]
        assert grade_task_hard(actions, hidden_with) - grade_task_hard(actions, hidden_without) == pytest.approx(0.10)

    def test_ads_team_notification_bonus(self):
        hidden_with = {"t3_rollback_target": "3.1.0", "t3_tables_rerun": [], "t3_notified_teams": {"sla", "ads"}, "rollback_applied": True}
        hidden_sla_only = {"t3_rollback_target": "3.1.0", "t3_tables_rerun": [], "t3_notified_teams": {"sla"}, "rollback_applied": True}
        actions = ["inspect_logs"]
        assert grade_task_hard(actions, hidden_with) - grade_task_hard(actions, hidden_sla_only) == pytest.approx(0.10)

    def test_per_table_rerun_bonuses(self):
        base_hidden = {"t3_rollback_target": "3.1.0", "t3_tables_rerun": [], "t3_notified_teams": set(), "rollback_applied": True}
        one_rerun = dict(base_hidden); one_rerun["t3_tables_rerun"] = ["revenue_daily"]
        two_rerun = dict(base_hidden); two_rerun["t3_tables_rerun"] = ["revenue_daily", "customer_summary"]
        three_rerun = dict(base_hidden); three_rerun["t3_tables_rerun"] = ["revenue_daily", "customer_summary", "marketing_segments"]
        actions = ["rollback_deployment", "trigger_rerun", "trigger_rerun", "trigger_rerun"]
        s1 = grade_task_hard(actions, one_rerun)
        s2 = grade_task_hard(actions, two_rerun)
        s3 = grade_task_hard(actions, three_rerun)
        assert s2 - s1 == pytest.approx(0.18)
        assert s3 - s2 == pytest.approx(0.18)

    def test_result_never_negative(self):
        actions = ["rollback_deployment", "scale_up_executor", "skip_task", "trigger_rerun"]
        hidden = {"t3_rollback_target": "3.1.1", "t3_tables_rerun": [], "t3_notified_teams": set(),
                  "rollback_applied": True, "rerun_triggered": False}
        assert grade_task_hard(actions, hidden) >= 0.0

    def test_result_never_above_one(self):
        assert grade_task_hard(
            ["inspect_logs", "check_dependencies", "rollback_deployment",
             "trigger_rerun", "trigger_rerun", "trigger_rerun", "notify_stakeholder"],
            _hard_optimal_hidden()
        ) <= 1.0


# ------------------------------------------------------------------ #
# grade_task_extreme
# ------------------------------------------------------------------ #

class TestGradeTaskExtreme:
    def test_optimal_path(self):
        actions = ["inspect_logs", "profile_data"]
        assert grade_task_extreme(actions, _extreme_optimal_hidden()) == pytest.approx(1.0)

    def test_stop_at_success_penalty(self):
        actions = ["inspect_logs"]
        hidden = {"is_done": True, "t4_notified_teams": set(), "rollback_applied": False}
        score = grade_task_extreme(actions, hidden)
        # 0.80 penalty fires; only +0.10 for inspect_logs → net = -0.70 → clamped to 0.0
        assert score == pytest.approx(0.0)

    def test_rerun_without_rollback_penalty(self):
        hidden = {"rollback_applied": False, "t4_notified_teams": set(), "is_done": False}
        score_with_rerun = grade_task_extreme(["inspect_logs", "trigger_rerun"], hidden)
        score_without_rerun = grade_task_extreme(["inspect_logs"], hidden)
        assert score_with_rerun < score_without_rerun

    def test_missing_crm_notification_penalty(self):
        hidden = dict(_extreme_optimal_hidden())
        hidden["t4_notified_teams"] = {"revenue"}  # crm absent
        actions = ["inspect_logs", "profile_data"]
        score = grade_task_extreme(actions, hidden)
        optimal = grade_task_extreme(["inspect_logs", "profile_data"], _extreme_optimal_hidden())
        assert optimal - score == pytest.approx(0.10 + 0.20)  # missing crm bonus + penalty

    def test_missing_verification_penalty(self):
        hidden = dict(_extreme_optimal_hidden())
        hidden["verification_done"] = False
        actions = ["inspect_logs", "profile_data"]
        score = grade_task_extreme(actions, hidden)
        optimal = grade_task_extreme(["inspect_logs", "profile_data"], _extreme_optimal_hidden())
        # Loses 0.10 verify bonus + 0.20 penalty
        assert optimal - score == pytest.approx(0.10 + 0.20)

    def test_proactive_investigation_bonus(self):
        # Both inspect_logs AND profile_data → +0.05 bonus
        both = grade_task_extreme(["inspect_logs", "profile_data"], {"t4_notified_teams": set(), "is_done": False})
        logs_only = grade_task_extreme(["inspect_logs"], {"t4_notified_teams": set(), "is_done": False})
        profile_only = grade_task_extreme(["profile_data"], {"t4_notified_teams": set(), "is_done": False})
        assert both == pytest.approx(logs_only + 0.15 + 0.05)  # profile(0.15) + bonus(0.05)
        assert both > profile_only + 0.10  # logs(0.10) + bonus(0.05)

    def test_correct_rollback_version_bonus(self):
        hidden_correct = {"t4_rollback_target": "4.1.5", "t4_notified_teams": set(), "is_done": False}
        hidden_wrong = {"t4_rollback_target": None, "t4_notified_teams": set(), "is_done": False}
        actions = ["inspect_logs"]
        assert grade_task_extreme(actions, hidden_correct) - grade_task_extreme(actions, hidden_wrong) == pytest.approx(0.30)

    def test_revenue_notification_bonus(self):
        hidden_with = {"t4_notified_teams": {"revenue"}, "is_done": False}
        hidden_without = {"t4_notified_teams": set(), "is_done": False}
        actions = ["inspect_logs"]
        assert grade_task_extreme(actions, hidden_with) - grade_task_extreme(actions, hidden_without) == pytest.approx(0.10)

    def test_crm_notification_bonus(self):
        hidden_both = {"t4_notified_teams": {"revenue", "crm"}, "is_done": False}
        hidden_revenue_only = {"t4_notified_teams": {"revenue"}, "is_done": False}
        actions = ["inspect_logs"]
        assert grade_task_extreme(actions, hidden_both) - grade_task_extreme(actions, hidden_revenue_only) == pytest.approx(0.10)

    def test_rerun_triggered_bonus(self):
        hidden_with = {"t4_notified_teams": set(), "is_done": False, "rerun_triggered": True, "rollback_applied": True}
        hidden_without = {"t4_notified_teams": set(), "is_done": False, "rerun_triggered": False}
        actions = ["inspect_logs"]
        assert grade_task_extreme(actions, hidden_with) - grade_task_extreme(actions, hidden_without) == pytest.approx(0.10)

    def test_result_never_negative(self):
        hidden = {"rollback_applied": False, "t4_notified_teams": set(), "is_done": True}
        assert grade_task_extreme(["inspect_logs", "trigger_rerun"], hidden) >= 0.0

    def test_result_never_above_one(self):
        assert grade_task_extreme(["inspect_logs", "profile_data"], _extreme_optimal_hidden()) <= 1.0


# ------------------------------------------------------------------ #
# grade() dispatcher
# ------------------------------------------------------------------ #

class TestGradeDispatcher:
    def test_dispatches_easy(self):
        actions = ["inspect_logs", "fix_pipeline_config", "trigger_rerun"]
        hidden = {"inspect_logs_called": True}
        assert grade("missing_source_file", actions, hidden) == grade_task_easy(actions, hidden)

    def test_dispatches_medium(self):
        assert grade("schema_drift_bigquery", [], {}) == grade_task_medium([], {})

    def test_dispatches_hard(self):
        assert grade("cascade_collapse", [], {}) == grade_task_hard([], {})

    def test_dispatches_extreme(self):
        assert grade("silent_data_corruption", [], {}) == grade_task_extreme([], {})

    def test_unknown_task_returns_zero(self):
        assert grade("nonexistent_task", [], {}) == pytest.approx(0.0)

    def test_dispatcher_passes_hidden_state(self):
        hidden = {"t2_discount_added": True, "t2_quantity_fixed": True, "schema_fixed": True, "rerun_triggered": True}
        direct = grade_task_medium(["inspect_logs", "check_schema"], hidden)
        via_dispatcher = grade("schema_drift_bigquery", ["inspect_logs", "check_schema"], hidden)
        assert via_dispatcher == pytest.approx(direct)


# ------------------------------------------------------------------ #
# Task handler trap paths (direct handle_action calls)
# ------------------------------------------------------------------ #

class TestTaskHandlerTraps:
    """
    Verify trap paths, red herrings, and wrong sequencing.

    handle_action() now returns (obs_updates, done) only.
    Rewards are computed via compute_step_reward() using before/after hidden snapshots.
    """

    def _act(self, action_type, target="pipeline", **params):
        from oncall_hero.models import OnCallAction
        return OnCallAction(action_type=action_type, target=target, parameters=params)

    def _run(self, handle_action_fn, action, hidden_start, task_id):
        """Helper: mutate a deep copy, compute reward, return (obs, reward, done, hidden_after)."""
        import copy
        from oncall_hero.rewards import compute_step_reward
        hidden_before = copy.deepcopy(hidden_start)
        hidden_after = copy.deepcopy(hidden_start)
        obs, done = handle_action_fn(action, hidden_after)
        reward = compute_step_reward(
            action.action_type, action.target, action.parameters,
            hidden_before, hidden_after, task_id, done,
        )
        return obs, reward, done, hidden_after

    # --- Easy traps ---
    def test_easy_rollback_is_irrelevant(self):
        from oncall_hero.tasks.task_easy import handle_action
        _, reward, _, _ = self._run(handle_action, self._act("rollback_deployment", version="1.0.0"), {}, "missing_source_file")
        assert reward < 0

    def test_easy_scale_up_is_irrelevant(self):
        from oncall_hero.tasks.task_easy import handle_action
        _, reward, _, _ = self._run(handle_action, self._act("scale_up_executor"), {}, "missing_source_file")
        assert reward < 0

    def test_easy_skip_task_done(self):
        from oncall_hero.tasks.task_easy import handle_action
        _, reward, done, _ = self._run(handle_action, self._act("skip_task"), {}, "missing_source_file")
        assert done is True
        assert reward < 0

    def test_easy_rerun_before_fix_penalised(self):
        from oncall_hero.tasks.task_easy import handle_action
        _, reward, _, _ = self._run(handle_action, self._act("trigger_rerun"), {"inspect_logs_called": True}, "missing_source_file")
        assert reward < 0

    def test_easy_fix_then_rerun_succeeds(self):
        from oncall_hero.tasks.task_easy import handle_action
        import copy
        from oncall_hero.rewards import compute_step_reward
        hidden = {"inspect_logs_called": True}
        handle_action(self._act("inspect_logs"), hidden)
        handle_action(self._act("fix_pipeline_config"), hidden)
        hb = copy.deepcopy(hidden)
        ha = copy.deepcopy(hidden)
        _, done = handle_action(self._act("trigger_rerun"), ha)
        reward = compute_step_reward("trigger_rerun", "pipeline", {}, hb, ha, "missing_source_file", done)
        assert done is True
        assert reward > 0

    # --- Medium traps ---
    def test_medium_alter_without_check_schema_penalised(self):
        from oncall_hero.tasks.task_medium import handle_action
        _, reward, _, _ = self._run(handle_action, self._act("alter_table", column="quantity", type="BIGINT"), {}, "schema_drift_bigquery")
        assert reward < 0

    def test_medium_alter_wrong_type_penalised(self):
        from oncall_hero.tasks.task_medium import handle_action
        _, reward, _, _ = self._run(handle_action, self._act("alter_table", column="quantity", type="INT"), {"check_schema_called": True, "t2_discount_added": False, "t2_quantity_fixed": False}, "schema_drift_bigquery")
        assert reward < 0

    def test_medium_alter_unknown_column_penalised(self):
        from oncall_hero.tasks.task_medium import handle_action
        _, reward, _, _ = self._run(handle_action, self._act("alter_table", column="nonexistent", type="STRING"), {"check_schema_called": True, "t2_discount_added": False, "t2_quantity_fixed": False}, "schema_drift_bigquery")
        assert reward < 0

    def test_medium_rollback_red_herring_penalised(self):
        from oncall_hero.tasks.task_medium import handle_action
        _, reward, _, _ = self._run(handle_action, self._act("rollback_deployment"), {}, "schema_drift_bigquery")
        assert reward == pytest.approx(-0.40)

    def test_medium_skip_task_terminal_and_penalised(self):
        from oncall_hero.tasks.task_medium import handle_action
        _, reward, done, _ = self._run(handle_action, self._act("skip_task"), {}, "schema_drift_bigquery")
        assert done is True
        assert reward < 0

    def test_medium_rerun_with_partial_fix_fails(self):
        from oncall_hero.tasks.task_medium import handle_action
        hidden = {"check_schema_called": True, "t2_discount_added": True, "t2_quantity_fixed": False}
        _, reward, done, _ = self._run(handle_action, self._act("trigger_rerun"), hidden, "schema_drift_bigquery")
        assert done is False
        assert reward < 0

    # --- Hard traps ---
    def test_hard_rollback_3_1_1_catastrophic(self):
        from oncall_hero.tasks.task_hard import handle_action
        _, reward, _, _ = self._run(handle_action, self._act("rollback_deployment", version="3.1.1"), {}, "cascade_collapse")
        assert reward == pytest.approx(-0.40)

    def test_hard_rerun_before_rollback_penalised(self):
        from oncall_hero.tasks.task_hard import handle_action
        _, reward, _, _ = self._run(handle_action, self._act("trigger_rerun", target="revenue_daily"), {}, "cascade_collapse")
        assert reward < 0

    def test_hard_rerun_all_tables_penalised(self):
        from oncall_hero.tasks.task_hard import handle_action
        hidden = {"rollback_applied": True, "rollback_version_correct": True, "t3_rollback_target": "3.1.0", "t3_tables_rerun": [], "t3_notified_teams": set()}
        _, reward, _, _ = self._run(handle_action, self._act("trigger_rerun", target="all"), hidden, "cascade_collapse")
        assert reward < 0

    def test_hard_rerun_wrong_order_penalised(self):
        from oncall_hero.tasks.task_hard import handle_action
        hidden = {
            "rollback_applied": True, "rollback_version_correct": True,
            "t3_rollback_target": "3.1.0", "t3_tables_rerun": [], "t3_notified_teams": set(),
        }
        _, reward, _, _ = self._run(handle_action, self._act("trigger_rerun", target="customer_summary"), hidden, "cascade_collapse")
        assert reward < 0

    def test_hard_skip_sla_table_penalised(self):
        from oncall_hero.tasks.task_hard import handle_action
        hidden = {"sla_critical_tables": ["revenue_daily", "customer_summary", "marketing_segments"], "t3_rollback_target": None, "t3_tables_rerun": [], "t3_notified_teams": set()}
        _, reward, _, _ = self._run(handle_action, self._act("skip_task", target="revenue_daily"), hidden, "cascade_collapse")
        assert reward < 0

    def test_hard_scale_up_executor_penalised(self):
        from oncall_hero.tasks.task_hard import handle_action
        _, reward, _, _ = self._run(handle_action, self._act("scale_up_executor"), {}, "cascade_collapse")
        assert reward < 0

    # --- Extreme traps ---
    def test_extreme_rerun_before_rollback_penalised(self):
        from oncall_hero.tasks.task_extreme import handle_action
        _, reward, _, _ = self._run(handle_action, self._act("trigger_rerun"), {}, "silent_data_corruption")
        assert reward < 0

    def test_extreme_wrong_rollback_version_penalised(self):
        from oncall_hero.tasks.task_extreme import handle_action
        _, reward, _, _ = self._run(handle_action, self._act("rollback_deployment", version="4.2.0"), {}, "silent_data_corruption")
        assert reward < 0

    def test_extreme_skip_task_terminal_and_penalised(self):
        from oncall_hero.tasks.task_extreme import handle_action
        _, reward, done, _ = self._run(handle_action, self._act("skip_task"), {}, "silent_data_corruption")
        assert done is True
        assert reward < 0

    def test_extreme_profile_data_post_fix_gives_verify_reward(self):
        from oncall_hero.tasks.task_extreme import handle_action
        import copy
        from oncall_hero.rewards import compute_step_reward
        hidden_start = {"rerun_triggered": True, "rollback_applied": True, "t4_notified_teams": set()}
        hb = copy.deepcopy(hidden_start)
        ha = copy.deepcopy(hidden_start)
        _, done = handle_action(self._act("profile_data"), ha)
        reward = compute_step_reward("profile_data", "pipeline", {}, hb, ha, "silent_data_corruption", done)
        assert reward == pytest.approx(0.10)
        assert ha.get("verification_done") is True

    def test_extreme_notify_duplicate_team_no_double_reward(self):
        from oncall_hero.tasks.task_extreme import handle_action
        import copy
        from oncall_hero.rewards import compute_step_reward
        hidden = {"t4_notified_teams": set()}
        handle_action(self._act("notify_stakeholder", team="revenue_team"), hidden)
        hb = copy.deepcopy(hidden)
        ha = copy.deepcopy(hidden)
        _, done = handle_action(self._act("notify_stakeholder", team="revenue_team"), ha)
        reward = compute_step_reward("notify_stakeholder", "pipeline", {"team": "revenue_team"}, hb, ha, "silent_data_corruption", done)
        assert reward == pytest.approx(0.0)

    def test_extreme_done_only_after_verify_and_both_notified(self):
        from oncall_hero.tasks.task_extreme import handle_action
        hidden = {"t4_notified_teams": set(), "rerun_triggered": True, "rollback_applied": True}
        handle_action(self._act("profile_data"), hidden)
        _, done = handle_action(self._act("notify_stakeholder", team="revenue_team"), hidden)
        assert done is False
        _, done = handle_action(self._act("notify_stakeholder", team="crm_team"), hidden)
        assert done is True


# ------------------------------------------------------------------ #
# Grader score bounds across all task types
# ------------------------------------------------------------------ #

class TestGraderBounds:
    """Fuzz the graders with extreme inputs and verify [0.0, 1.0] is always respected."""

    @pytest.mark.parametrize("grader,task_id", [
        (grade_task_easy, "missing_source_file"),
        (grade_task_medium, "schema_drift_bigquery"),
        (grade_task_hard, "cascade_collapse"),
        (grade_task_extreme, "silent_data_corruption"),
    ])
    def test_empty_actions_in_bounds(self, grader, task_id):
        score = grader([], {})
        assert 0.0 <= score <= 1.0

    @pytest.mark.parametrize("grader", [grade_task_easy, grade_task_medium, grade_task_hard, grade_task_extreme])
    def test_all_penalised_actions_never_below_zero(self, grader):
        actions = ["skip_task", "scale_up_executor", "rollback_deployment", "trigger_rerun"]
        hidden = {"rollback_applied": False, "is_done": True, "t4_notified_teams": set(),
                  "t3_rollback_target": "3.1.1", "t3_notified_teams": set(),
                  "rerun_triggered": True, "rerun_order_correct": False}
        assert grader(actions, hidden) >= 0.0
