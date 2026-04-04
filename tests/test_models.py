# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for OnCallAction, OnCallObservation, and OnCallState models."""

import pytest
from pydantic import ValidationError

from oncall_hero.models import OnCallAction, OnCallObservation, OnCallState


# ------------------------------------------------------------------ #
# OnCallAction
# ------------------------------------------------------------------ #

class TestOnCallAction:
    def test_required_fields_stored(self):
        a = OnCallAction(action_type="inspect_logs", target="my_pipeline")
        assert a.action_type == "inspect_logs"
        assert a.target == "my_pipeline"

    def test_parameters_defaults_to_empty_dict(self):
        a = OnCallAction(action_type="inspect_logs", target="p")
        assert a.parameters == {}

    def test_justification_defaults_to_empty_string(self):
        a = OnCallAction(action_type="inspect_logs", target="p")
        assert a.justification == ""

    def test_parameters_default_factory_is_isolated(self):
        a1 = OnCallAction(action_type="inspect_logs", target="p")
        a2 = OnCallAction(action_type="inspect_logs", target="p")
        a1.parameters["key"] = "value"
        assert "key" not in a2.parameters

    def test_missing_action_type_raises(self):
        with pytest.raises(ValidationError):
            OnCallAction(target="pipeline")  # type: ignore[call-arg]

    def test_missing_target_raises(self):
        with pytest.raises(ValidationError):
            OnCallAction(action_type="inspect_logs")  # type: ignore[call-arg]

    def test_parameters_stores_nested_dict(self):
        a = OnCallAction(
            action_type="alter_table",
            target="inventory",
            parameters={"column": "discount_pct", "type": "FLOAT"},
        )
        assert a.parameters["column"] == "discount_pct"
        assert a.parameters["type"] == "FLOAT"

    def test_parameters_stores_version_string(self):
        a = OnCallAction(
            action_type="rollback_deployment",
            target="pipeline",
            parameters={"version": "3.1.0"},
        )
        assert a.parameters["version"] == "3.1.0"

    def test_justification_stored(self):
        a = OnCallAction(
            action_type="inspect_logs",
            target="p",
            justification="checking logs first",
        )
        assert a.justification == "checking logs first"


# ------------------------------------------------------------------ #
# OnCallObservation
# ------------------------------------------------------------------ #

class TestOnCallObservation:
    def test_all_defaults(self):
        obs = OnCallObservation()
        assert obs.incident_id == ""
        assert obs.task_id == ""
        assert obs.pipeline_name == ""
        assert obs.failed_task == ""
        assert obs.error_message == ""
        assert obs.dag_task_statuses == {}
        assert obs.sla_breach is False
        assert obs.sla_time_remaining_seconds == -1
        assert obs.active_incidents == []
        assert obs.source_schema == []
        assert obs.target_schema == []
        assert obs.dependency_map == {}
        assert obs.row_counts == {}
        assert obs.log_details == ""
        assert obs.resource_metrics == {}
        assert obs.data_profile == {}
        assert obs.deployment_history == []
        assert obs.incident_history == []
        assert obs.steps_remaining == 0
        assert obs.last_action_result == ""
        assert obs.actions_taken == []

    def test_base_class_defaults(self):
        obs = OnCallObservation()
        assert obs.done is False
        assert obs.reward is None

    def test_sla_breach_true(self):
        obs = OnCallObservation(sla_breach=True)
        assert obs.sla_breach is True

    def test_sla_breach_false(self):
        obs = OnCallObservation(sla_breach=False)
        assert obs.sla_breach is False

    def test_dag_task_statuses_roundtrip(self):
        statuses = {
            "extract": "success",
            "transform": "failed",
            "load": "pending",
        }
        obs = OnCallObservation(dag_task_statuses=statuses)
        assert obs.dag_task_statuses == statuses

    def test_list_fields_are_independent(self):
        obs1 = OnCallObservation()
        obs2 = OnCallObservation()
        obs1.actions_taken.append("inspect_logs")
        assert obs2.actions_taken == []

    def test_active_incidents_list_is_independent(self):
        obs1 = OnCallObservation()
        obs2 = OnCallObservation()
        obs1.active_incidents.append({"pipeline": "x"})
        assert obs2.active_incidents == []

    def test_steps_remaining_stored(self):
        obs = OnCallObservation(steps_remaining=10)
        assert obs.steps_remaining == 10

    def test_done_and_reward_stored(self):
        obs = OnCallObservation(done=True, reward=0.65)
        assert obs.done is True
        assert obs.reward == pytest.approx(0.65)

    def test_incident_history_stored(self):
        obs = OnCallObservation(incident_history=["event1", "event2"])
        assert obs.incident_history == ["event1", "event2"]


# ------------------------------------------------------------------ #
# OnCallState
# ------------------------------------------------------------------ #

class TestOnCallState:
    def test_all_score_defaults_zero(self):
        s = OnCallState()
        assert s.investigation_score == 0.0
        assert s.root_cause_score == 0.0
        assert s.remediation_score == 0.0
        assert s.efficiency_score == 0.0
        assert s.sla_score == 0.0
        assert s.penalty_total == 0.0

    def test_boolean_defaults(self):
        s = OnCallState()
        assert s.is_done is False
        assert s.schema_fixed is False
        assert s.config_fixed is False
        assert s.rollback_applied is False
        assert s.rollback_version_correct is False
        assert s.rerun_triggered is False
        assert s.rerun_order_correct is False
        assert s.null_data_detected is False
        assert s.verification_done is False
        assert s.red_herring_active is False
        assert s.noisy_neighbour_acknowledged is False
        assert s.deployment_history_checked is False

    def test_string_defaults(self):
        s = OnCallState()
        assert s.true_root_cause == ""
        assert s.terminal_reason == ""
        assert s.pipeline_health == "broken"
        assert s.task_id == ""
        assert s.red_herring_description == ""

    def test_list_defaults(self):
        s = OnCallState()
        assert s.correct_action_sequence == []
        assert s.sla_critical_tables == []

    def test_score_fields_accept_float(self):
        s = OnCallState(
            investigation_score=0.75,
            root_cause_score=0.75,
            remediation_score=0.75,
            efficiency_score=0.75,
            sla_score=0.75,
            penalty_total=0.75,
        )
        for field in [
            s.investigation_score, s.root_cause_score, s.remediation_score,
            s.efficiency_score, s.sla_score, s.penalty_total,
        ]:
            assert field == pytest.approx(0.75)

    def test_sla_critical_tables_stored(self):
        s = OnCallState(sla_critical_tables=["revenue_daily", "customer_summary"])
        assert s.sla_critical_tables == ["revenue_daily", "customer_summary"]

    def test_pipeline_health_custom_value(self):
        s = OnCallState(pipeline_health="restored")
        assert s.pipeline_health == "restored"

    def test_is_done_true(self):
        s = OnCallState(is_done=True)
        assert s.is_done is True
