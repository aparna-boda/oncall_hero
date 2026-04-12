# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Reward computation module for OnCall Hero.

Pure functions only — no state mutation, no side effects.
Called by environment.step() AFTER handle_action() has already mutated hidden state.

Entry point: compute_step_reward(action_type, target, params, hidden_before, hidden_after, task_id, done)

All reward constants are centralised here. To tune rewards, edit the dicts below —
no task handler files need to change.
"""

from typing import Any, Dict


def _normalize_team(team: str) -> str:
    """Canonical team name used consistently across rewards, task handlers, and graders."""
    team = str(team).strip().lower()
    if "sla" in team:
        return "sla"
    if "analytics" in team:
        return "analytics"
    if "business" in team:
        return "business"
    if "ads" in team:
        return "ads"
    if "revenue" in team or "dashboard" in team:
        return "revenue"
    if "crm" in team or "upstream" in team:
        return "crm"
    return team

# ------------------------------------------------------------------ #
# Reward constants — single source of truth
# ------------------------------------------------------------------ #

# Investigation rewards: given for gathering useful diagnostic evidence.
INVESTIGATION_REWARDS: Dict[str, Dict[str, float]] = {
    "missing_source_file": {
        "inspect_logs": 0.05,
    },
    "schema_drift_bigquery": {
        "inspect_logs": 0.10,
        "check_schema": 0.10,
    },
    "cascade_collapse": {
        "inspect_logs": 0.08,
        "check_dependencies": 0.08,
        "profile_data": 0.08,
        "check_resource_utilization": 0.06,
    },
    "silent_data_corruption": {
        "inspect_logs": 0.10,
        "profile_data_prefx": 0.15,   # first profile before fix
        "profile_data_postfix": 0.10,  # verify profile after fix
    },
}

# Remediation rewards: given for correct fix actions.
REMEDIATION_REWARDS: Dict[str, float] = {
    "easy_fix_config":         0.25,
    "easy_rerun_success":      0.65,
    "medium_alter_correct":    0.15,
    "medium_rerun_success":    0.55,
    "hard_rollback_310":       0.20,
    "hard_sla_rerun_correct":  0.18,
    "hard_notify_team":        0.10,
    "extreme_rollback_415":    0.15,
    "extreme_rerun_success":   0.10,
    "extreme_notify_team":     0.10,
}

# Penalty values: negative rewards for harmful or wasteful actions.
PENALTY_VALUES: Dict[str, float] = {
    # Easy
    "easy_fix_no_logs":          -0.05,
    "easy_premature_rerun":      -0.30,
    "easy_scale_up":             -0.10,
    "easy_rollback":             -0.10,
    "easy_alter":                -0.10,
    "easy_skip":                 -0.30,
    "easy_irrelevant":           -0.05,  # check_schema, check_deps, profile, check_resource
    # Medium
    "medium_alter_no_schema":    -0.10,
    "medium_alter_wrong_type":   -0.10,
    "medium_alter_downgrade":    -0.30,
    "medium_alter_unknown_col":  -0.10,
    "medium_rollback":           -0.40,
    "medium_premature_rerun":    -0.20,
    "medium_scale_up":           -0.10,
    "medium_skip":               -0.30,
    "medium_irrelevant":         -0.05,
    # Hard
    "hard_rollback_311":         -0.40,
    "hard_rollback_unknown":     -0.10,
    "hard_premature_rerun":      -0.30,
    "hard_rerun_bad_version":    -0.30,
    "hard_rerun_all_tables":     -0.20,
    "hard_rerun_wrong_order":    -0.30,
    "hard_rerun_unknown_target": -0.10,
    "hard_scale_up":             -0.20,
    "hard_alter_orders_archive": -0.30,
    "hard_alter_other":          -0.20,
    "hard_check_schema":         -0.05,
    "hard_fix_config":           -0.05,
    "hard_skip_sla":             -0.30,
    # Extreme
    "extreme_premature_rerun":   -0.30,
    "extreme_rollback_unknown":  -0.10,
    "extreme_alter":             -0.20,
    "extreme_scale_up":          -0.10,
    "extreme_check_schema":      -0.05,
    "extreme_check_deps":        -0.05,
    "extreme_check_resource":    -0.05,
    "extreme_fix_config":        -0.05,
    "extreme_skip":              -0.50,
}


# ------------------------------------------------------------------ #
# Normalisation
# ------------------------------------------------------------------ #

def normalize_reward(raw: float) -> float:
    """Clamp a raw step reward to (0.01, 0.99) — strict (0,1) range required by validator."""
    return max(0.01, min(0.99, raw))


# ------------------------------------------------------------------ #
# Per-task reward helpers (pure — hidden dicts treated as read-only)
# ------------------------------------------------------------------ #

def compute_investigation_reward(
    action_type: str,
    task_id: str,
    hidden_before: Dict[str, Any],
) -> float:
    """
    Return the investigation reward for a diagnostic action.
    Returns 0.0 for non-investigation actions or unknown task_ids.
    """
    table = INVESTIGATION_REWARDS.get(task_id, {})
    return table.get(action_type, 0.0)


def compute_remediation_reward(
    action_type: str,
    target: str,
    params: Dict[str, Any],
    task_id: str,
    hidden_before: Dict[str, Any],
) -> float:
    """
    Return the remediation reward for a fix/restore action.
    Returns 0.0 when the action is not a remediation step or preconditions fail.
    """
    if task_id == "missing_source_file":
        return _easy_remediation(action_type, hidden_before)
    if task_id == "schema_drift_bigquery":
        return _medium_remediation(action_type, params, hidden_before)
    if task_id == "cascade_collapse":
        return _hard_remediation(action_type, target, params, hidden_before)
    if task_id == "silent_data_corruption":
        return _extreme_remediation(action_type, params, hidden_before)
    return 0.0


def compute_penalty(
    action_type: str,
    target: str,
    params: Dict[str, Any],
    task_id: str,
    hidden_before: Dict[str, Any],
) -> float:
    """
    Return the penalty (negative float) for a harmful/wasteful action.
    Returns 0.0 when no penalty applies.
    """
    if task_id == "missing_source_file":
        return _easy_penalty(action_type, hidden_before)
    if task_id == "schema_drift_bigquery":
        return _medium_penalty(action_type, target, params, hidden_before)
    if task_id == "cascade_collapse":
        return _hard_penalty(action_type, target, params, hidden_before)
    if task_id == "silent_data_corruption":
        return _extreme_penalty(action_type, params, hidden_before)
    return 0.0


# ------------------------------------------------------------------ #
# Main entry point
# ------------------------------------------------------------------ #

def compute_step_reward(
    action_type: str,
    target: str,
    params: Dict[str, Any],
    hidden_before: Dict[str, Any],
    hidden_after: Dict[str, Any],
    task_id: str,
    done: bool,
) -> float:
    """
    Compute the numeric reward for one environment step.

    Called by environment.step() after handle_action() has mutated hidden state.
    hidden_before is a deep-copy snapshot taken before mutation.
    hidden_after is the live hidden dict after mutation.

    Returns a float clamped to [-1.0, 1.0].
    """
    investigation = compute_investigation_reward(action_type, task_id, hidden_before)
    remediation = compute_remediation_reward(action_type, target, params, task_id, hidden_before)
    penalty = compute_penalty(action_type, target, params, task_id, hidden_before)

    # Avoid double-counting: investigation and remediation are mutually exclusive per action.
    # Penalty is additive on top.
    raw = investigation + remediation + penalty
    return normalize_reward(raw)


# ------------------------------------------------------------------ #
# Private helpers — Task 1 (Easy)
# ------------------------------------------------------------------ #

def _easy_remediation(action_type: str, hidden_before: Dict[str, Any]) -> float:
    if action_type == "fix_pipeline_config" and hidden_before.get("inspect_logs_called"):
        return REMEDIATION_REWARDS["easy_fix_config"]
    if action_type == "trigger_rerun" and hidden_before.get("config_fixed"):
        return REMEDIATION_REWARDS["easy_rerun_success"]
    return 0.0


def _easy_penalty(action_type: str, hidden_before: Dict[str, Any]) -> float:
    if action_type == "fix_pipeline_config" and not hidden_before.get("inspect_logs_called"):
        return PENALTY_VALUES["easy_fix_no_logs"]
    if action_type == "trigger_rerun" and not hidden_before.get("config_fixed"):
        return PENALTY_VALUES["easy_premature_rerun"]
    if action_type == "scale_up_executor":
        return PENALTY_VALUES["easy_scale_up"]
    if action_type == "rollback_deployment":
        return PENALTY_VALUES["easy_rollback"]
    if action_type == "alter_table":
        return PENALTY_VALUES["easy_alter"]
    if action_type == "skip_task":
        return PENALTY_VALUES["easy_skip"]
    if action_type in ("check_schema", "check_dependencies", "profile_data",
                       "check_resource_utilization"):
        return PENALTY_VALUES["easy_irrelevant"]
    return 0.0


# ------------------------------------------------------------------ #
# Private helpers — Task 2 (Medium)
# ------------------------------------------------------------------ #

def _medium_remediation(
    action_type: str,
    params: Dict[str, Any],
    hidden_before: Dict[str, Any],
) -> float:
    if action_type == "alter_table" and hidden_before.get("check_schema_called"):
        col = params.get("column", "").lower()
        typ = params.get("type", "").upper()
        if col == "discount_pct" and typ in ("FLOAT", "FLOAT64"):
            if not hidden_before.get("t2_discount_added"):
                return REMEDIATION_REWARDS["medium_alter_correct"]
        if col == "quantity" and typ in ("BIGINT", "INT64"):
            if not hidden_before.get("t2_quantity_fixed"):
                return REMEDIATION_REWARDS["medium_alter_correct"]
    if action_type == "trigger_rerun":
        if hidden_before.get("t2_discount_added") and hidden_before.get("t2_quantity_fixed"):
            return REMEDIATION_REWARDS["medium_rerun_success"]
    return 0.0


def _medium_penalty(
    action_type: str,
    target: str,
    params: Dict[str, Any],
    hidden_before: Dict[str, Any],
) -> float:
    if action_type == "rollback_deployment":
        return PENALTY_VALUES["medium_rollback"]
    if action_type == "trigger_rerun":
        if not (hidden_before.get("t2_discount_added") and hidden_before.get("t2_quantity_fixed")):
            return PENALTY_VALUES["medium_premature_rerun"]
    if action_type == "alter_table":
        if not hidden_before.get("check_schema_called"):
            return PENALTY_VALUES["medium_alter_no_schema"]
        col = params.get("column", "").lower()
        typ = params.get("type", "").upper()
        if col == "quantity" and typ in ("INT", "INTEGER", "INT32"):
            return PENALTY_VALUES["medium_alter_downgrade"]
        if col in ("discount_pct", "quantity") and typ not in (
            "FLOAT", "FLOAT64", "BIGINT", "INT64"
        ):
            return PENALTY_VALUES["medium_alter_wrong_type"]
        if col not in ("discount_pct", "quantity"):
            return PENALTY_VALUES["medium_alter_unknown_col"]
    if action_type == "scale_up_executor":
        return PENALTY_VALUES["medium_scale_up"]
    if action_type == "skip_task":
        return PENALTY_VALUES["medium_skip"]
    if action_type in ("check_dependencies", "check_resource_utilization", "profile_data"):
        return PENALTY_VALUES["medium_irrelevant"]
    return 0.0


# ------------------------------------------------------------------ #
# Private helpers — Task 3 (Hard)
# ------------------------------------------------------------------ #

_HARD_SLA_ORDER = ["revenue_daily", "customer_summary", "marketing_segments"]


def _hard_remediation(
    action_type: str,
    target: str,
    params: Dict[str, Any],
    hidden_before: Dict[str, Any],
) -> float:
    if action_type == "rollback_deployment":
        if params.get("version") == "3.1.0":
            return REMEDIATION_REWARDS["hard_rollback_310"]
    if action_type == "trigger_rerun":
        if not hidden_before.get("rollback_applied"):
            return 0.0  # penalty handled in compute_penalty
        if not hidden_before.get("rollback_version_correct"):
            return 0.0
        if target in _HARD_SLA_ORDER:
            current_list = hidden_before.get("t3_tables_rerun", [])
            idx = len(current_list)
            if idx < len(_HARD_SLA_ORDER) and target == _HARD_SLA_ORDER[idx]:
                return REMEDIATION_REWARDS["hard_sla_rerun_correct"]
    if action_type == "notify_stakeholder":
        team = _normalize_team(params.get("team", ""))
        notified = hidden_before.get("t3_notified_teams", set())
        if team in ("sla", "analytics", "business", "ads") and team not in notified:
            return REMEDIATION_REWARDS["hard_notify_team"]
    return 0.0


def _hard_penalty(
    action_type: str,
    target: str,
    params: Dict[str, Any],
    hidden_before: Dict[str, Any],
) -> float:
    if action_type == "rollback_deployment":
        version = params.get("version", "")
        if version == "3.1.1":
            return PENALTY_VALUES["hard_rollback_311"]
        if version != "3.1.0":
            return PENALTY_VALUES["hard_rollback_unknown"]
        return 0.0  # 3.1.0 is correct — reward handled in remediation
    if action_type == "scale_up_executor":
        return PENALTY_VALUES["hard_scale_up"]
    if action_type == "alter_table":
        if target == "orders_archive":
            return PENALTY_VALUES["hard_alter_orders_archive"]
        return PENALTY_VALUES["hard_alter_other"]
    if action_type == "check_schema":
        return PENALTY_VALUES["hard_check_schema"]
    if action_type == "fix_pipeline_config":
        return PENALTY_VALUES["hard_fix_config"]
    if action_type == "trigger_rerun":
        if not hidden_before.get("rollback_applied"):
            return PENALTY_VALUES["hard_premature_rerun"]
        if not hidden_before.get("rollback_version_correct"):
            return PENALTY_VALUES["hard_rerun_bad_version"]
        if target in ("all", "customer_master"):
            return PENALTY_VALUES["hard_rerun_all_tables"]
        if target in _HARD_SLA_ORDER:
            current_list = hidden_before.get("t3_tables_rerun", [])
            idx = len(current_list)
            if idx >= len(_HARD_SLA_ORDER) or target != _HARD_SLA_ORDER[idx]:
                return PENALTY_VALUES["hard_rerun_wrong_order"]
        elif target not in _HARD_SLA_ORDER:
            return PENALTY_VALUES["hard_rerun_unknown_target"]
    if action_type == "skip_task":
        sla_tables = hidden_before.get("sla_critical_tables", [])
        if target in sla_tables:
            return PENALTY_VALUES["hard_skip_sla"]
    return 0.0


# ------------------------------------------------------------------ #
# Private helpers — Task 4 (Extreme)
# ------------------------------------------------------------------ #

def _extreme_remediation(
    action_type: str,
    params: Dict[str, Any],
    hidden_before: Dict[str, Any],
) -> float:
    if action_type == "profile_data":
        if hidden_before.get("rerun_triggered") and hidden_before.get("rollback_applied"):
            return INVESTIGATION_REWARDS["silent_data_corruption"]["profile_data_postfix"]
        return INVESTIGATION_REWARDS["silent_data_corruption"]["profile_data_prefx"]
    if action_type == "rollback_deployment":
        if params.get("version") == "4.1.5":
            return REMEDIATION_REWARDS["extreme_rollback_415"]
    if action_type == "trigger_rerun":
        if hidden_before.get("rollback_applied"):
            return REMEDIATION_REWARDS["extreme_rerun_success"]
    if action_type == "notify_stakeholder":
        team = _normalize_team(params.get("team", ""))
        notified = hidden_before.get("t4_notified_teams", set())
        if team in ("revenue", "crm") and team not in notified:
            return REMEDIATION_REWARDS["extreme_notify_team"]
    return 0.0


def _extreme_penalty(
    action_type: str,
    params: Dict[str, Any],
    hidden_before: Dict[str, Any],
) -> float:
    if action_type == "trigger_rerun" and not hidden_before.get("rollback_applied"):
        return PENALTY_VALUES["extreme_premature_rerun"]
    if action_type == "rollback_deployment":
        if params.get("version") != "4.1.5":
            return PENALTY_VALUES["extreme_rollback_unknown"]
        return 0.0  # correct version — reward handled in remediation
    if action_type == "alter_table":
        return PENALTY_VALUES["extreme_alter"]
    if action_type == "scale_up_executor":
        return PENALTY_VALUES["extreme_scale_up"]
    if action_type == "check_schema":
        return PENALTY_VALUES["extreme_check_schema"]
    if action_type == "check_dependencies":
        return PENALTY_VALUES["extreme_check_deps"]
    if action_type == "check_resource_utilization":
        return PENALTY_VALUES["extreme_check_resource"]
    if action_type == "fix_pipeline_config":
        return PENALTY_VALUES["extreme_fix_config"]
    if action_type == "skip_task":
        return PENALTY_VALUES["extreme_skip"]
    return 0.0
