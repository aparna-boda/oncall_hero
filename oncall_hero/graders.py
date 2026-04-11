# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Graders for OnCall Hero tasks.

Each grader evaluates a completed episode across five dimensions:
    investigation_score, root_cause_score, remediation_score,
    efficiency_score, sla_score

Penalties are applied for wrong actions, premature reruns, and skips.
Final score is clamped to [0.01, 0.99].
"""

from typing import Dict, List

# Actions that are irrelevant for Task 1 (file naming issue)
_TASK_EASY_IRRELEVANT_ACTIONS = {
    "check_schema",
    "check_dependencies",
    "check_resource_utilization",
    "profile_data",
    "scale_up_executor",
    "rollback_deployment",
    "alter_table",
}

def grade_task_medium(actions_taken: List[str], hidden: Dict) -> float:
    """Grade a completed Task 2 (schema_drift_bigquery) episode."""
    score = 0.0
    penalties = 0.0
    
    if "inspect_logs" in actions_taken:
        score += 0.10
        
    check_schema_idx = next((i for i, a in enumerate(actions_taken) if a == "check_schema"), -1)
    alter_idx = next((i for i, a in enumerate(actions_taken) if a == "alter_table"), -1)
    
    if check_schema_idx != -1 and (alter_idx == -1 or check_schema_idx < alter_idx):
        score += 0.10
        
    if "rollback_deployment" not in actions_taken:
        score += 0.10
    else:
        penalties += 0.40
        
    if hidden.get("t2_discount_added"):
        score += 0.25 # 0.15 (identified) + 0.10 (correct alter)
        
    if hidden.get("t2_quantity_fixed"):
        score += 0.25 # 0.15 (identified) + 0.10 (correct alter)
        
    if hidden.get("schema_fixed") and hidden.get("rerun_triggered"):
        # restored
        score += 0.20
        
    for a in actions_taken:
        if a in ["scale_up_executor"]:
            penalties += 0.10
            
    return max(0.01, min(0.99, score - penalties))

def grade_task_hard(actions_taken: List[str], hidden: Dict) -> float:
    """Grade a completed Task 3 (cascade_collapse) episode."""
    score = 0.0

    # Investigation: read deployment history + map blast radius (0.16)
    score += 0.08 if "inspect_logs" in actions_taken else 0.0
    score += 0.08 if "check_dependencies" in actions_taken else 0.0

    # Avoided red-herring actions (0.10)
    if "scale_up_executor" not in actions_taken:
        score += 0.05
    if "alter_table" not in actions_taken:
        score += 0.05

    # Correct rollback version (0.12)
    if hidden.get("t3_rollback_target") == "3.1.0":
        score += 0.12

    # SLA reruns in correct order — only correctly ordered entries land in t3_tables_rerun (0.54)
    tables_rerun = hidden.get("t3_tables_rerun", [])
    if len(tables_rerun) > 0 and tables_rerun[0] == "revenue_daily":
        score += 0.18
    if len(tables_rerun) > 1 and tables_rerun[1] == "customer_summary":
        score += 0.18
    if len(tables_rerun) > 2 and tables_rerun[2] == "marketing_segments":
        score += 0.18

    # Stakeholder notifications (0.10 + 0.05 bonus)
    notified = hidden.get("t3_notified_teams", set())
    if "sla" in notified:
        score += 0.10
    if "ads" in notified:
        score += 0.05  # bonus: acknowledged the separate OOM incident

    # Max optimal (all above, with ads bonus): 1.05 → clamped to 0.99
    # Max optimal (without ads bonus):         1.00 → clamped to 0.99

    penalties = 0.0
    if hidden.get("t3_rollback_target") == "3.1.1":
        penalties += 0.40
    if "scale_up_executor" in actions_taken:
        penalties += 0.20
    # Fires when agent did wrong-order reruns without completing the correct sequence
    if hidden.get("rerun_order_correct") is False:
        penalties += 0.30
    if "trigger_rerun" in actions_taken and not hidden.get("rollback_applied"):
        penalties += 0.30
    if "skip_task" in actions_taken:
        penalties += 0.30

    return max(0.01, min(0.99, score - penalties))




def grade_task_easy(actions_taken: List[str], hidden: Dict) -> float:
    """
    Grade a completed Task 1 (missing_source_file) episode.

    Scoring breakdown:
        investigation_score  max 0.20
        root_cause_score     max 0.30
        remediation_score    max 0.30
        efficiency_score     max 0.10
        sla_score            max 0.10

    Args:
        actions_taken: Ordered list of action_type strings taken in the episode.
        hidden: Final hidden state dict from the environment.

    Returns:
        Float in [0.01, 0.99].
    """
    # ------------------------------------------------------------------ #
    # Investigation score (max 0.20)
    # ------------------------------------------------------------------ #
    investigation = 0.0
    if "inspect_logs" in actions_taken:
        investigation += 0.15
    # +0.05 bonus if agent did NOT chase the slow-query distractor
    chased_distractor = any(
        a in actions_taken for a in ["check_resource_utilization", "scale_up_executor"]
    )
    if not chased_distractor:
        investigation += 0.05

    # ------------------------------------------------------------------ #
    # Root cause score (max 0.30)
    # ------------------------------------------------------------------ #
    root_cause = 0.0
    if hidden.get("inspect_logs_called"):
        root_cause += 0.20  # naming mismatch identified
    if "fix_pipeline_config" in actions_taken:
        root_cause += 0.10  # agent understood what to fix

    # ------------------------------------------------------------------ #
    # Remediation score (max 0.30)
    # ------------------------------------------------------------------ #
    remediation = 0.0
    if "fix_pipeline_config" in actions_taken:
        remediation += 0.15

    # +0.15 only if trigger_rerun came AFTER fix_pipeline_config
    if "fix_pipeline_config" in actions_taken and "trigger_rerun" in actions_taken:
        fix_idx = next(
            (i for i, a in enumerate(actions_taken) if a == "fix_pipeline_config"), -1
        )
        rerun_idx = next(
            (i for i, a in enumerate(actions_taken) if a == "trigger_rerun"), -1
        )
        if fix_idx < rerun_idx:
            remediation += 0.15

    # ------------------------------------------------------------------ #
    # Efficiency score (max 0.10)
    # ------------------------------------------------------------------ #
    efficiency = 0.0
    num_steps = len(actions_taken)
    if num_steps <= 3:
        efficiency = 0.10
    elif num_steps == 4:
        efficiency = 0.05

    # ------------------------------------------------------------------ #
    # SLA score (max 0.10) — always full for Task 1 (no SLA constraint)
    # ------------------------------------------------------------------ #
    sla = 0.10

    # ------------------------------------------------------------------ #
    # Penalties
    # ------------------------------------------------------------------ #
    penalties = 0.0

    # -0.30 if trigger_rerun was called before fix_pipeline_config
    if "trigger_rerun" in actions_taken:
        if "fix_pipeline_config" not in actions_taken:
            penalties += 0.30
        else:
            fix_idx = next(
                (i for i, a in enumerate(actions_taken) if a == "fix_pipeline_config"), -1
            )
            rerun_idx = next(
                (i for i, a in enumerate(actions_taken) if a == "trigger_rerun"), -1
            )
            if rerun_idx < fix_idx:
                penalties += 0.30

    # -0.10 per irrelevant action
    for a in actions_taken:
        if a in _TASK_EASY_IRRELEVANT_ACTIONS:
            penalties += 0.10

    # -0.50 if agent gave up
    if "skip_task" in actions_taken:
        penalties += 0.50

    total = investigation + root_cause + remediation + efficiency + sla - penalties
    return max(0.01, min(0.99, total))


def grade_task_extreme(actions_taken: List[str], hidden: Dict) -> float:
    """Grade a completed Task 4 (silent_data_corruption) episode."""
    score = 0.0

    if "inspect_logs" in actions_taken:
        score += 0.10
    if "profile_data" in actions_taken:
        score += 0.15
    # Proactive investigation bonus: profiling a pipeline that reported SUCCESS
    if "inspect_logs" in actions_taken and "profile_data" in actions_taken:
        score += 0.05
        
    # Since we can't perfectly track "finding price vs customer_id" via actions string alone,
    # we reward if they profiled and rolled back correctly.
    if hidden.get("t4_rollback_target") == "4.1.5":
        score += 0.15
        # we will assume they identified price correctly if they roll back. Let's add the +0.10 for price and +0.05 for customer_id via the profile call
        score += 0.15
        
    if hidden.get("rerun_triggered"):
        score += 0.10
        
    if hidden.get("verification_done"):
        score += 0.10
        
    teams = hidden.get("t4_notified_teams", set())
    if "revenue" in teams:
        score += 0.10
    if "crm" in teams:
        score += 0.10
        
    # Penalty
    penalties = 0.0
    if "inspect_logs" in actions_taken and "profile_data" not in actions_taken and hidden.get("is_done"):
        # Stop at SUCCESS
        penalties += 0.80
        
    if "trigger_rerun" in actions_taken and not hidden.get("rollback_applied"):
        penalties += 0.30
        
    if hidden.get("is_done") and not ("crm" in teams):
        penalties += 0.20
        
    if hidden.get("is_done") and not hidden.get("verification_done"):
        penalties += 0.20
        
    return max(0.01, min(0.99, score - penalties))

def grade(task_id: str, actions_taken: List[str], hidden: Dict) -> float:
    """
    Unified grading entry point.

    Args:
        task_id: The task identifier.
        actions_taken: Ordered list of action_type strings.
        hidden: Final hidden state dict from the environment.

    Returns:
        Float in [0.01, 0.99].
    """
    if task_id == "missing_source_file":
        return grade_task_easy(actions_taken, hidden)
    elif task_id == "schema_drift_bigquery":
        return grade_task_medium(actions_taken, hidden)
    elif task_id == "cascade_collapse":
        return grade_task_hard(actions_taken, hidden)
    elif task_id == "silent_data_corruption":
        return grade_task_extreme(actions_taken, hidden)
    return 0.01

