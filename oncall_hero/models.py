# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Data models for the OnCall Hero Environment.

OnCall Hero simulates production data pipeline incidents.
An AI agent acts as an on-call data engineer.
"""

from typing import Any, Dict, List

from openenv.core.env_server.types import Action, Observation, State
from pydantic import Field

VALID_ACTION_TYPES = [
    "inspect_logs",
    "check_schema",
    "check_dependencies",
    "check_resource_utilization",
    "profile_data",
    "alter_table",
    "scale_up_executor",
    "rollback_deployment",
    "fix_pipeline_config",
    "trigger_rerun",
    "notify_stakeholder",
    "skip_task",
]


class OnCallAction(Action):
    """Action taken by the agent in the OnCall Hero environment."""

    action_type: str = Field(..., description="One of 12 valid action types")
    target: str = Field(..., description="Pipeline or table being acted on")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action-specific parameters")
    justification: str = Field(default="", description="Agent reasoning for this action")


class OnCallObservation(Observation):
    """Observation returned by the OnCall Hero environment."""

    incident_id: str = Field(default="")
    task_id: str = Field(default="")
    pipeline_name: str = Field(default="")
    failed_task: str = Field(default="")
    error_message: str = Field(default="")
    dag_task_statuses: Dict[str, str] = Field(default_factory=dict)
    sla_breach: bool = Field(default=False)
    sla_time_remaining_seconds: int = Field(default=-1)
    active_incidents: List[Dict] = Field(default_factory=list)
    source_schema: List[Dict] = Field(default_factory=list)
    target_schema: List[Dict] = Field(default_factory=list)
    dependency_map: Dict = Field(default_factory=dict)
    row_counts: Dict = Field(default_factory=dict)
    log_details: str = Field(default="")
    resource_metrics: Dict = Field(default_factory=dict)
    data_profile: Dict = Field(default_factory=dict)
    deployment_history: List[Dict] = Field(default_factory=list)
    incident_history: List[str] = Field(default_factory=list)
    steps_remaining: int = Field(default=0)
    last_action_result: str = Field(default="")
    actions_taken: List[str] = Field(default_factory=list)


class OnCallState(State):
    """Full internal truth — visible only via state() endpoint."""
    
    true_root_cause: str = Field(default="")
    correct_action_sequence: List[str] = Field(default_factory=list)
    red_herring_active: bool = Field(default=False)
    red_herring_description: str = Field(default="")
    pipeline_health: str = Field(default="broken")
    schema_fixed: bool = Field(default=False)
    config_fixed: bool = Field(default=False)
    rollback_applied: bool = Field(default=False)
    rollback_version_correct: bool = Field(default=False)
    rerun_triggered: bool = Field(default=False)
    rerun_order_correct: bool = Field(default=False)
    null_data_detected: bool = Field(default=False)
    verification_done: bool = Field(default=False)
    sla_critical_tables: List[str] = Field(default_factory=list)
    noisy_neighbour_acknowledged: bool = Field(default=False)
    deployment_history_checked: bool = Field(default=False)
    task_id: str = Field(default="")
    is_done: bool = Field(default=False)
    terminal_reason: str = Field(default="")
    investigation_score: float = Field(default=0.0)
    root_cause_score: float = Field(default=0.0)
    remediation_score: float = Field(default=0.0)
    efficiency_score: float = Field(default=0.0)
    sla_score: float = Field(default=0.0)
    penalty_total: float = Field(default=0.0)
