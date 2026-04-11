# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Unit tests for oncall_hero/rewards.py pure functions.

Each test passes synthetic hidden_before/hidden_after dicts to verify
reward constants and branching logic without running the full environment.
"""

import pytest
from oncall_hero.rewards import (
    normalize_reward,
    compute_investigation_reward,
    compute_remediation_reward,
    compute_penalty,
    compute_step_reward,
)


# ------------------------------------------------------------------ #
# normalize_reward
# ------------------------------------------------------------------ #

class TestNormalizeReward:
    def test_value_within_range_unchanged(self):
        assert normalize_reward(0.5) == pytest.approx(0.5)

    def test_zero_unchanged(self):
        assert normalize_reward(0.0) == pytest.approx(0.0)

    def test_positive_clamped_to_one(self):
        assert normalize_reward(2.0) == pytest.approx(1.0)

    def test_negative_clamped_to_minus_one(self):
        assert normalize_reward(-5.0) == pytest.approx(-1.0)

    def test_exactly_one_unchanged(self):
        assert normalize_reward(1.0) == pytest.approx(1.0)

    def test_exactly_minus_one_unchanged(self):
        assert normalize_reward(-1.0) == pytest.approx(-1.0)


# ------------------------------------------------------------------ #
# compute_investigation_reward
# ------------------------------------------------------------------ #

class TestComputeInvestigationReward:
    def test_easy_inspect_logs(self):
        r = compute_investigation_reward("inspect_logs", "missing_source_file", {})
        assert r == pytest.approx(0.05)

    def test_medium_inspect_logs(self):
        r = compute_investigation_reward("inspect_logs", "schema_drift_bigquery", {})
        assert r == pytest.approx(0.10)

    def test_medium_check_schema(self):
        r = compute_investigation_reward("check_schema", "schema_drift_bigquery", {})
        assert r == pytest.approx(0.10)

    def test_hard_inspect_logs(self):
        r = compute_investigation_reward("inspect_logs", "cascade_collapse", {})
        assert r == pytest.approx(0.08)

    def test_hard_check_dependencies(self):
        r = compute_investigation_reward("check_dependencies", "cascade_collapse", {})
        assert r == pytest.approx(0.08)

    def test_hard_profile_data(self):
        r = compute_investigation_reward("profile_data", "cascade_collapse", {})
        assert r == pytest.approx(0.08)

    def test_hard_check_resource(self):
        r = compute_investigation_reward("check_resource_utilization", "cascade_collapse", {})
        assert r == pytest.approx(0.06)

    def test_extreme_inspect_logs(self):
        r = compute_investigation_reward("inspect_logs", "silent_data_corruption", {})
        assert r == pytest.approx(0.10)

    def test_unknown_task_returns_zero(self):
        r = compute_investigation_reward("inspect_logs", "nonexistent_task", {})
        assert r == pytest.approx(0.0)

    def test_non_investigation_action_returns_zero(self):
        r = compute_investigation_reward("trigger_rerun", "missing_source_file", {})
        assert r == pytest.approx(0.0)


# ------------------------------------------------------------------ #
# compute_remediation_reward — Easy
# ------------------------------------------------------------------ #

class TestRemediationEasy:
    def test_fix_config_after_logs(self):
        r = compute_remediation_reward(
            "fix_pipeline_config", "pipeline", {},
            "missing_source_file", {"inspect_logs_called": True},
        )
        assert r == pytest.approx(0.25)

    def test_fix_config_without_logs_no_reward(self):
        r = compute_remediation_reward(
            "fix_pipeline_config", "pipeline", {},
            "missing_source_file", {"inspect_logs_called": False},
        )
        assert r == pytest.approx(0.0)

    def test_trigger_rerun_after_fix(self):
        r = compute_remediation_reward(
            "trigger_rerun", "pipeline", {},
            "missing_source_file", {"config_fixed": True},
        )
        assert r == pytest.approx(0.65)

    def test_trigger_rerun_before_fix_no_reward(self):
        r = compute_remediation_reward(
            "trigger_rerun", "pipeline", {},
            "missing_source_file", {"config_fixed": False},
        )
        assert r == pytest.approx(0.0)


# ------------------------------------------------------------------ #
# compute_remediation_reward — Medium
# ------------------------------------------------------------------ #

class TestRemediationMedium:
    def test_alter_discount_pct_float(self):
        r = compute_remediation_reward(
            "alter_table", "pipeline", {"column": "discount_pct", "type": "FLOAT"},
            "schema_drift_bigquery", {"check_schema_called": True, "t2_discount_added": False},
        )
        assert r == pytest.approx(0.15)

    def test_alter_discount_pct_float64(self):
        r = compute_remediation_reward(
            "alter_table", "pipeline", {"column": "discount_pct", "type": "FLOAT64"},
            "schema_drift_bigquery", {"check_schema_called": True, "t2_discount_added": False},
        )
        assert r == pytest.approx(0.15)

    def test_alter_already_added_no_reward(self):
        r = compute_remediation_reward(
            "alter_table", "pipeline", {"column": "discount_pct", "type": "FLOAT"},
            "schema_drift_bigquery", {"check_schema_called": True, "t2_discount_added": True},
        )
        assert r == pytest.approx(0.0)

    def test_alter_quantity_bigint(self):
        r = compute_remediation_reward(
            "alter_table", "pipeline", {"column": "quantity", "type": "BIGINT"},
            "schema_drift_bigquery", {"check_schema_called": True, "t2_quantity_fixed": False},
        )
        assert r == pytest.approx(0.15)

    def test_alter_without_check_schema_no_reward(self):
        r = compute_remediation_reward(
            "alter_table", "pipeline", {"column": "discount_pct", "type": "FLOAT"},
            "schema_drift_bigquery", {"check_schema_called": False, "t2_discount_added": False},
        )
        assert r == pytest.approx(0.0)

    def test_trigger_rerun_both_fixed(self):
        r = compute_remediation_reward(
            "trigger_rerun", "pipeline", {},
            "schema_drift_bigquery",
            {"t2_discount_added": True, "t2_quantity_fixed": True},
        )
        assert r == pytest.approx(0.55)

    def test_trigger_rerun_partial_fix_no_reward(self):
        r = compute_remediation_reward(
            "trigger_rerun", "pipeline", {},
            "schema_drift_bigquery",
            {"t2_discount_added": True, "t2_quantity_fixed": False},
        )
        assert r == pytest.approx(0.0)


# ------------------------------------------------------------------ #
# compute_remediation_reward — Hard
# ------------------------------------------------------------------ #

class TestRemediationHard:
    def test_rollback_310(self):
        r = compute_remediation_reward(
            "rollback_deployment", "pipeline", {"version": "3.1.0"},
            "cascade_collapse", {},
        )
        assert r == pytest.approx(0.20)

    def test_rollback_311_no_reward(self):
        r = compute_remediation_reward(
            "rollback_deployment", "pipeline", {"version": "3.1.1"},
            "cascade_collapse", {},
        )
        assert r == pytest.approx(0.0)

    def test_sla_rerun_in_order_revenue_daily(self):
        r = compute_remediation_reward(
            "trigger_rerun", "revenue_daily", {},
            "cascade_collapse",
            {"rollback_applied": True, "rollback_version_correct": True, "t3_tables_rerun": []},
        )
        assert r == pytest.approx(0.18)

    def test_sla_rerun_in_order_customer_summary(self):
        r = compute_remediation_reward(
            "trigger_rerun", "customer_summary", {},
            "cascade_collapse",
            {"rollback_applied": True, "rollback_version_correct": True,
             "t3_tables_rerun": ["revenue_daily"]},
        )
        assert r == pytest.approx(0.18)

    def test_sla_rerun_wrong_order_no_reward(self):
        r = compute_remediation_reward(
            "trigger_rerun", "marketing_segments", {},
            "cascade_collapse",
            {"rollback_applied": True, "rollback_version_correct": True, "t3_tables_rerun": []},
        )
        assert r == pytest.approx(0.0)

    def test_sla_rerun_before_rollback_no_reward(self):
        r = compute_remediation_reward(
            "trigger_rerun", "revenue_daily", {},
            "cascade_collapse",
            {"rollback_applied": False, "rollback_version_correct": False, "t3_tables_rerun": []},
        )
        assert r == pytest.approx(0.0)

    def test_notify_sla_team(self):
        r = compute_remediation_reward(
            "notify_stakeholder", "pipeline", {"team": "sla_team"},
            "cascade_collapse", {"t3_notified_teams": set()},
        )
        assert r == pytest.approx(0.10)

    def test_notify_ads_team(self):
        r = compute_remediation_reward(
            "notify_stakeholder", "pipeline", {"team": "ads_team"},
            "cascade_collapse", {"t3_notified_teams": set()},
        )
        assert r == pytest.approx(0.10)

    def test_notify_already_notified_no_reward(self):
        r = compute_remediation_reward(
            "notify_stakeholder", "pipeline", {"team": "sla_team"},
            "cascade_collapse", {"t3_notified_teams": {"sla"}},
        )
        assert r == pytest.approx(0.0)


# ------------------------------------------------------------------ #
# compute_remediation_reward — Extreme
# ------------------------------------------------------------------ #

class TestRemediationExtreme:
    def test_profile_data_before_fix(self):
        r = compute_remediation_reward(
            "profile_data", "pipeline", {},
            "silent_data_corruption",
            {"rerun_triggered": False, "rollback_applied": False},
        )
        assert r == pytest.approx(0.15)

    def test_profile_data_after_fix(self):
        r = compute_remediation_reward(
            "profile_data", "pipeline", {},
            "silent_data_corruption",
            {"rerun_triggered": True, "rollback_applied": True},
        )
        assert r == pytest.approx(0.10)

    def test_rollback_correct_version(self):
        r = compute_remediation_reward(
            "rollback_deployment", "pipeline", {"version": "4.1.5"},
            "silent_data_corruption", {},
        )
        assert r == pytest.approx(0.15)

    def test_rollback_wrong_version_no_reward(self):
        r = compute_remediation_reward(
            "rollback_deployment", "pipeline", {"version": "4.2.0"},
            "silent_data_corruption", {},
        )
        assert r == pytest.approx(0.0)

    def test_trigger_rerun_after_rollback(self):
        r = compute_remediation_reward(
            "trigger_rerun", "pipeline", {},
            "silent_data_corruption", {"rollback_applied": True},
        )
        assert r == pytest.approx(0.10)

    def test_trigger_rerun_before_rollback_no_reward(self):
        r = compute_remediation_reward(
            "trigger_rerun", "pipeline", {},
            "silent_data_corruption", {"rollback_applied": False},
        )
        assert r == pytest.approx(0.0)

    def test_notify_revenue_team(self):
        r = compute_remediation_reward(
            "notify_stakeholder", "pipeline", {"team": "revenue_team"},
            "silent_data_corruption", {"t4_notified_teams": set()},
        )
        assert r == pytest.approx(0.10)

    def test_notify_crm_team(self):
        r = compute_remediation_reward(
            "notify_stakeholder", "pipeline", {"team": "crm_team"},
            "silent_data_corruption", {"t4_notified_teams": set()},
        )
        assert r == pytest.approx(0.10)

    def test_notify_already_notified_no_reward(self):
        r = compute_remediation_reward(
            "notify_stakeholder", "pipeline", {"team": "revenue_team"},
            "silent_data_corruption", {"t4_notified_teams": {"revenue"}},
        )
        assert r == pytest.approx(0.0)


# ------------------------------------------------------------------ #
# compute_penalty — Easy
# ------------------------------------------------------------------ #

class TestPenaltyEasy:
    def test_fix_config_without_logs(self):
        p = compute_penalty("fix_pipeline_config", "pipeline", {}, "missing_source_file",
                            {"inspect_logs_called": False})
        assert p == pytest.approx(-0.05)

    def test_fix_config_after_logs_no_penalty(self):
        p = compute_penalty("fix_pipeline_config", "pipeline", {}, "missing_source_file",
                            {"inspect_logs_called": True})
        assert p == pytest.approx(0.0)

    def test_premature_rerun(self):
        p = compute_penalty("trigger_rerun", "pipeline", {}, "missing_source_file",
                            {"config_fixed": False})
        assert p == pytest.approx(-0.30)

    def test_scale_up(self):
        p = compute_penalty("scale_up_executor", "pipeline", {}, "missing_source_file", {})
        assert p == pytest.approx(-0.10)

    def test_rollback(self):
        p = compute_penalty("rollback_deployment", "pipeline", {}, "missing_source_file", {})
        assert p == pytest.approx(-0.10)

    def test_alter_table(self):
        p = compute_penalty("alter_table", "pipeline", {}, "missing_source_file", {})
        assert p == pytest.approx(-0.10)

    def test_skip_task(self):
        p = compute_penalty("skip_task", "pipeline", {}, "missing_source_file", {})
        assert p == pytest.approx(-0.30)

    def test_check_schema_irrelevant(self):
        p = compute_penalty("check_schema", "pipeline", {}, "missing_source_file", {})
        assert p == pytest.approx(-0.05)

    def test_check_dependencies_irrelevant(self):
        p = compute_penalty("check_dependencies", "pipeline", {}, "missing_source_file", {})
        assert p == pytest.approx(-0.05)

    def test_profile_data_irrelevant(self):
        p = compute_penalty("profile_data", "pipeline", {}, "missing_source_file", {})
        assert p == pytest.approx(-0.05)

    def test_check_resource_irrelevant(self):
        p = compute_penalty("check_resource_utilization", "pipeline", {}, "missing_source_file", {})
        assert p == pytest.approx(-0.05)

    def test_inspect_logs_no_penalty(self):
        p = compute_penalty("inspect_logs", "pipeline", {}, "missing_source_file", {})
        assert p == pytest.approx(0.0)


# ------------------------------------------------------------------ #
# compute_penalty — Medium
# ------------------------------------------------------------------ #

class TestPenaltyMedium:
    def test_rollback_is_heavy_penalty(self):
        p = compute_penalty("rollback_deployment", "pipeline", {}, "schema_drift_bigquery", {})
        assert p == pytest.approx(-0.40)

    def test_premature_rerun(self):
        p = compute_penalty("trigger_rerun", "pipeline", {}, "schema_drift_bigquery",
                            {"t2_discount_added": False, "t2_quantity_fixed": False})
        assert p == pytest.approx(-0.20)

    def test_alter_without_schema(self):
        p = compute_penalty("alter_table", "pipeline", {"column": "discount_pct", "type": "FLOAT"},
                            "schema_drift_bigquery", {"check_schema_called": False})
        assert p == pytest.approx(-0.10)

    def test_alter_quantity_downgrade(self):
        p = compute_penalty("alter_table", "pipeline", {"column": "quantity", "type": "INT"},
                            "schema_drift_bigquery", {"check_schema_called": True})
        assert p == pytest.approx(-0.30)

    def test_alter_unknown_column(self):
        p = compute_penalty("alter_table", "pipeline", {"column": "bad_col", "type": "STRING"},
                            "schema_drift_bigquery", {"check_schema_called": True})
        assert p == pytest.approx(-0.10)

    def test_scale_up(self):
        p = compute_penalty("scale_up_executor", "pipeline", {}, "schema_drift_bigquery", {})
        assert p == pytest.approx(-0.10)

    def test_skip(self):
        p = compute_penalty("skip_task", "pipeline", {}, "schema_drift_bigquery", {})
        assert p == pytest.approx(-0.30)

    def test_check_dependencies_irrelevant(self):
        p = compute_penalty("check_dependencies", "pipeline", {}, "schema_drift_bigquery", {})
        assert p == pytest.approx(-0.05)

    def test_inspect_logs_no_penalty(self):
        p = compute_penalty("inspect_logs", "pipeline", {}, "schema_drift_bigquery", {})
        assert p == pytest.approx(0.0)


# ------------------------------------------------------------------ #
# compute_penalty — Hard
# ------------------------------------------------------------------ #

class TestPenaltyHard:
    def test_rollback_311_catastrophic(self):
        p = compute_penalty("rollback_deployment", "pipeline", {"version": "3.1.1"},
                            "cascade_collapse", {})
        assert p == pytest.approx(-0.40)

    def test_rollback_unknown_version(self):
        p = compute_penalty("rollback_deployment", "pipeline", {"version": "2.0.0"},
                            "cascade_collapse", {})
        assert p == pytest.approx(-0.10)

    def test_rollback_correct_version_no_penalty(self):
        p = compute_penalty("rollback_deployment", "pipeline", {"version": "3.1.0"},
                            "cascade_collapse", {})
        assert p == pytest.approx(0.0)

    def test_premature_rerun_before_rollback(self):
        p = compute_penalty("trigger_rerun", "revenue_daily", {},
                            "cascade_collapse", {"rollback_applied": False})
        assert p == pytest.approx(-0.30)

    def test_rerun_on_bad_version(self):
        p = compute_penalty("trigger_rerun", "revenue_daily", {},
                            "cascade_collapse",
                            {"rollback_applied": True, "rollback_version_correct": False})
        assert p == pytest.approx(-0.30)

    def test_rerun_all_tables(self):
        p = compute_penalty("trigger_rerun", "all", {},
                            "cascade_collapse",
                            {"rollback_applied": True, "rollback_version_correct": True,
                             "t3_tables_rerun": []})
        assert p == pytest.approx(-0.20)

    def test_rerun_wrong_order(self):
        p = compute_penalty("trigger_rerun", "marketing_segments", {},
                            "cascade_collapse",
                            {"rollback_applied": True, "rollback_version_correct": True,
                             "t3_tables_rerun": []})
        assert p == pytest.approx(-0.30)

    def test_rerun_correct_order_no_penalty(self):
        p = compute_penalty("trigger_rerun", "revenue_daily", {},
                            "cascade_collapse",
                            {"rollback_applied": True, "rollback_version_correct": True,
                             "t3_tables_rerun": []})
        assert p == pytest.approx(0.0)

    def test_scale_up(self):
        p = compute_penalty("scale_up_executor", "pipeline", {}, "cascade_collapse", {})
        assert p == pytest.approx(-0.20)

    def test_alter_orders_archive(self):
        p = compute_penalty("alter_table", "orders_archive", {}, "cascade_collapse", {})
        assert p == pytest.approx(-0.30)

    def test_alter_other_table(self):
        p = compute_penalty("alter_table", "revenue_daily", {}, "cascade_collapse", {})
        assert p == pytest.approx(-0.20)

    def test_check_schema_minor_penalty(self):
        p = compute_penalty("check_schema", "pipeline", {}, "cascade_collapse", {})
        assert p == pytest.approx(-0.05)

    def test_skip_sla_table(self):
        p = compute_penalty("skip_task", "revenue_daily", {},
                            "cascade_collapse",
                            {"sla_critical_tables": ["revenue_daily", "customer_summary",
                                                     "marketing_segments"]})
        assert p == pytest.approx(-0.30)


# ------------------------------------------------------------------ #
# compute_penalty — Extreme
# ------------------------------------------------------------------ #

class TestPenaltyExtreme:
    def test_premature_rerun(self):
        p = compute_penalty("trigger_rerun", "pipeline", {}, "silent_data_corruption",
                            {"rollback_applied": False})
        assert p == pytest.approx(-0.30)

    def test_rerun_after_rollback_no_penalty(self):
        p = compute_penalty("trigger_rerun", "pipeline", {}, "silent_data_corruption",
                            {"rollback_applied": True})
        assert p == pytest.approx(0.0)

    def test_rollback_wrong_version_penalty(self):
        p = compute_penalty("rollback_deployment", "pipeline", {"version": "4.2.0"},
                            "silent_data_corruption", {})
        assert p == pytest.approx(-0.10)

    def test_rollback_correct_version_no_penalty(self):
        p = compute_penalty("rollback_deployment", "pipeline", {"version": "4.1.5"},
                            "silent_data_corruption", {})
        assert p == pytest.approx(0.0)

    def test_alter_table(self):
        p = compute_penalty("alter_table", "pipeline", {}, "silent_data_corruption", {})
        assert p == pytest.approx(-0.20)

    def test_scale_up(self):
        p = compute_penalty("scale_up_executor", "pipeline", {}, "silent_data_corruption", {})
        assert p == pytest.approx(-0.10)

    def test_check_schema(self):
        p = compute_penalty("check_schema", "pipeline", {}, "silent_data_corruption", {})
        assert p == pytest.approx(-0.05)

    def test_check_dependencies(self):
        p = compute_penalty("check_dependencies", "pipeline", {}, "silent_data_corruption", {})
        assert p == pytest.approx(-0.05)

    def test_check_resource(self):
        p = compute_penalty("check_resource_utilization", "pipeline", {}, "silent_data_corruption", {})
        assert p == pytest.approx(-0.05)

    def test_fix_config(self):
        p = compute_penalty("fix_pipeline_config", "pipeline", {}, "silent_data_corruption", {})
        assert p == pytest.approx(-0.05)

    def test_skip(self):
        p = compute_penalty("skip_task", "pipeline", {}, "silent_data_corruption", {})
        assert p == pytest.approx(-0.50)

    def test_inspect_logs_no_penalty(self):
        p = compute_penalty("inspect_logs", "pipeline", {}, "silent_data_corruption", {})
        assert p == pytest.approx(0.0)


# ------------------------------------------------------------------ #
# compute_step_reward — integration of investigation + remediation + penalty
# ------------------------------------------------------------------ #

class TestComputeStepReward:
    def test_unknown_task_returns_zero(self):
        r = compute_step_reward("inspect_logs", "pipeline", {}, {}, {}, "unknown_task", False)
        assert r == pytest.approx(0.0)

    def test_easy_optimal_step1_inspect_logs(self):
        r = compute_step_reward("inspect_logs", "pipeline", {}, {}, {}, "missing_source_file", False)
        assert r == pytest.approx(0.05)

    def test_easy_optimal_step2_fix_config(self):
        hidden = {"inspect_logs_called": True, "config_fixed": False}
        r = compute_step_reward("fix_pipeline_config", "pipeline", {}, hidden, hidden,
                                "missing_source_file", False)
        assert r == pytest.approx(0.25)

    def test_easy_optimal_step3_rerun(self):
        hidden = {"config_fixed": True}
        r = compute_step_reward("trigger_rerun", "pipeline", {}, hidden, hidden,
                                "missing_source_file", True)
        assert r == pytest.approx(0.65)

    def test_easy_trap_premature_rerun(self):
        hidden = {"config_fixed": False}
        r = compute_step_reward("trigger_rerun", "pipeline", {}, hidden, hidden,
                                "missing_source_file", False)
        assert r == pytest.approx(-0.30)

    def test_hard_rollback_311_penalty_dominates(self):
        # remediation = 0.0 (wrong version), penalty = -0.40 → net = -0.40
        r = compute_step_reward("rollback_deployment", "pipeline", {"version": "3.1.1"},
                                {}, {}, "cascade_collapse", False)
        assert r == pytest.approx(-0.40)

    def test_hard_rollback_310_reward(self):
        # remediation = 0.20, penalty = 0.0 → net = 0.20
        r = compute_step_reward("rollback_deployment", "pipeline", {"version": "3.1.0"},
                                {}, {}, "cascade_collapse", False)
        assert r == pytest.approx(0.20)

    def test_medium_rollback_heavy_penalty(self):
        r = compute_step_reward("rollback_deployment", "pipeline", {},
                                {}, {}, "schema_drift_bigquery", False)
        assert r == pytest.approx(-0.40)

    def test_extreme_wrong_rollback_penalty(self):
        r = compute_step_reward("rollback_deployment", "pipeline", {"version": "4.2.0"},
                                {}, {}, "silent_data_corruption", False)
        assert r == pytest.approx(-0.10)

    def test_extreme_correct_rollback_reward(self):
        r = compute_step_reward("rollback_deployment", "pipeline", {"version": "4.1.5"},
                                {}, {}, "silent_data_corruption", False)
        assert r == pytest.approx(0.15)

    def test_result_clamped_above_one(self):
        # investigation + remediation stacking can't exceed 1.0
        hidden = {"config_fixed": True}
        # trigger_rerun on easy gives +0.65 (no investigation for trigger_rerun)
        r = compute_step_reward("trigger_rerun", "pipeline", {}, hidden, hidden,
                                "missing_source_file", True)
        assert r <= 1.0

    def test_result_clamped_below_minus_one(self):
        # Even the heaviest combos won't drop below -1.0
        r = compute_step_reward("skip_task", "pipeline", {}, {}, {},
                                "silent_data_corruption", True)
        assert r >= -1.0
