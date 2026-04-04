# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Task 4 — "The Silent Killer" (Extreme)

Scenario:
    Pipeline:     reporting_pipeline
    Failed task:  None
    Root cause:   Upstream CRM export started sending NULL for price.
    Symptoms:     Pipeline shows SUCCESS status. Revenue drops by 52%. SLA breached for dashboard.
    Crux:         Agent must proactively investigate with NO error signals initially.
    Traps:        customer_id has 3% NULLs (pre-existing noise). MUST verify post-fix.
"""

from typing import Dict, Tuple

from oncall_hero.models import OnCallAction

def get_initial_observation() -> dict:
    return {
        "incident_id": "INC-20240401-004",
        "task_id": "silent_data_corruption",
        "pipeline_name": "reporting_pipeline",
        "failed_task": "None",
        "error_message": "",
        "dag_task_statuses": {
            "extract_crm": "success",
            "transform_metrics": "success",
            "load_reporting": "success",
        },
        "sla_breach": True,
        "sla_time_remaining_seconds": 1800,
        "active_incidents": [
            {"pipeline": "reporting_pipeline", "severity": "CRITICAL", "sla_breach": True}
        ],
        "source_schema": [],
        "target_schema": [],
        "dependency_map": {},
        "row_counts": {},
        "log_details": "",
        "resource_metrics": {},
        "data_profile": {},
        "deployment_history": [],
        "incident_history": ["2024-03-20: Missing CRM data cascade — NULL values propagated"],
        "steps_remaining": 18,
        "last_action_result": "",
        "actions_taken": [],
    }

def handle_action(action: OnCallAction, hidden: dict) -> tuple[dict, float, bool]:
    action_type = action.action_type
    params = action.parameters
    updates: dict = {}
    reward = 0.0
    done = False
    
    # Initialize task-specific hidden fields
    if "t4_rollback_target" not in hidden:
        hidden["t4_rollback_target"] = None
        hidden["t4_notified_teams"] = set()
        hidden["t4_post_fix_profile_called"] = False
        
    if action_type == "inspect_logs":
        reward = 0.10
        hidden["inspect_logs_called"] = True
        updates["deployment_history"] = [
            {"version": "4.2.0", "deployed_at": "Today 02:00 AM", "known_issues": "Optimized extract phase. DQ checks bypassed for speed."},
            {"version": "4.1.5", "deployed_at": "1 week ago", "known_issues": "Stable. Includes strict DQ filters on price column."}
        ]
        updates["log_details"] = (
            "[INFO] Pipeline executed successfully.\n"
            "[INFO] extract_crm: 0 rows dropped.\n"
            "[INFO] No errors found in local logs for reporting_pipeline.\n"
            "Status is SUCCESS."
        )
        updates["last_action_result"] = "Logs retrieved. The pipeline executed successfully with zero runtime errors."

    elif action_type == "profile_data":
        if hidden.get("rerun_triggered") and hidden.get("rollback_applied"):
            # Post-fix
            reward = 0.10
            hidden["t4_post_fix_profile_called"] = True
            hidden["verification_done"] = True
            updates["data_profile"] = {
                "price": "NULL rate = 0%",
                "customer_id": "NULL rate = 3% (pre-existing threshold tolerance)",
                "quantity": "NULL rate = 0%"
            }
            updates["last_action_result"] = "Post-fix data profile shows 0% NULLs in price. Fix verified."
        else:
            reward = 0.15
            updates["data_profile"] = {
                "price": "NULL rate = 52%",
                "customer_id": "NULL rate = 3%",
                "quantity": "NULL rate = 0%"
            }
            updates["last_action_result"] = "Data profiled. Anomalous 52% NULLs detected in price column."

    elif action_type == "rollback_deployment":
        version = params.get("version", "")
        if version == "4.1.5":
            reward = 0.15
            hidden["rollback_applied"] = True
            hidden["t4_rollback_target"] = "4.1.5"
            updates["last_action_result"] = "Rolled back to 4.1.5. Strict DQ checks re-enabled."
        else:
            reward = -0.10
            updates["last_action_result"] = "Rollback to unknown or unstated version."

    elif action_type == "trigger_rerun":
        if not hidden.get("rollback_applied"):
            reward = -0.30
            updates["last_action_result"] = "Pipeline triggered but reloaded the same corrupt data. NULL issue persists."
        else:
            reward = 0.10
            hidden["rerun_triggered"] = True
            hidden["pipeline_health"] = "partially_fixed"
            updates["last_action_result"] = "Pipeline rerun successful under 4.1.5 rules. Missing values likely filtered/filled."

    elif action_type == "notify_stakeholder":
        team = params.get("team", "").lower()
        if "revenue" in team or "dashboard" in team:
            if "revenue" not in hidden["t4_notified_teams"]:
                reward = 0.10
                hidden["t4_notified_teams"].add("revenue")
                updates["last_action_result"] = "Notified revenue team of the data quality dashboard issue."
            else:
                updates["last_action_result"] = "Already notified revenue team."
        elif "crm" in team or "upstream" in team:
            if "crm" not in hidden["t4_notified_teams"]:
                reward = 0.10
                hidden["t4_notified_teams"].add("crm")
                updates["last_action_result"] = "Notified upstream CRM team of their source system export error."
            else:
                updates["last_action_result"] = "Already notified CRM team."
        else:
            reward = 0.0
            updates["last_action_result"] = f"Notified {team}."

    elif action_type == "check_schema":
        reward = -0.05
        updates["last_action_result"] = "Schema comparison returned identical."

    elif action_type == "check_dependencies":
        reward = -0.05
        updates["last_action_result"] = "No downstream dependency cascading issues. This is the terminal pipeline."

    elif action_type == "check_resource_utilization":
        reward = -0.05
        updates["last_action_result"] = "Cluster and DB utilization perfectly normal."

    elif action_type == "alter_table":
        reward = -0.20
        updates["last_action_result"] = "Altering the table schema won't fix corrupt data natively inserted."
        
    elif action_type == "skip_task":
        reward = -0.50
        done = True
        updates["last_action_result"] = "Task skipped. Data left corrupt perpetually."

    elif action_type == "scale_up_executor":
        reward = -0.10
        updates["last_action_result"] = "Scaling executors does not solve data quality nulls."

    elif action_type == "fix_pipeline_config":
        reward = -0.05
        updates["last_action_result"] = "Not a pipeline configuration issue like filename paths."

    else:
        reward = 0.0
        updates["last_action_result"] = f"Unknown or invalid action: {action_type}."

    # Done logical checks for T4
    if hidden.get("verification_done") and "revenue" in hidden["t4_notified_teams"] and "crm" in hidden["t4_notified_teams"]:
        hidden["pipeline_health"] = "restored"
        done = True
        updates["last_action_result"] = updates.get("last_action_result", "") + " All issues restored and stakeholders updated. Fixing complete."

    return updates, reward, done
