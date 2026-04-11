# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Task 3 — "The Cascade Collapse" (Hard)

Scenario:
    Pipeline:     analytics_pipeline
    Failed task:  customer_master (bad JOIN propagates downstream)
    Root cause:   Deployment 3.1.2 introduced a bad JOIN logic.
    Cascades:     12 downstream tables. 3 SLA breaches (revenue_daily, customer_summary, marketing_segments).
    Distractor:   ads_spend pipeline is OOMing on same cluster.
    Traps:        Rolling back to 3.1.1 is unsafe (NULL bug). Must rollback to 3.1.0 and trigger 3 SLA reruns in order.
"""

from oncall_hero.models import OnCallAction


def get_initial_observation() -> dict:
    return {
        "incident_id": "INC-20240401-003",
        "task_id": "cascade_collapse",
        "pipeline_name": "analytics_pipeline",
        "failed_task": "customer_master",
        "error_message": (
            "SLA BREACH ALERT: revenue_daily, customer_summary, marketing_segments delayed.\n"
            "[WARN] 09:20 AM - ads_spend pipeline OOM error on cluster 'analytics-primary'.\n"
            "customer_master completed successfully at 08:30 AM but data validation checks downstream are failing."
        ),
        "dag_task_statuses": {
            "customer_master": "success",
            "revenue_daily": "failed",
            "customer_summary": "failed",
            "marketing_segments": "failed",
        },
        "sla_breach": True,
        "sla_time_remaining_seconds": 3600,
        "active_incidents": [
            {"pipeline": "analytics_pipeline", "severity": "HIGH", "sla_breach": True},
            {"pipeline": "ads_spend", "severity": "MEDIUM", "sla_breach": False}
        ],
        "source_schema": [],
        "target_schema": [],
        "dependency_map": {},
        "row_counts": {},
        "log_details": "",
        "resource_metrics": {},
        "data_profile": {},
        "deployment_history": [],
        "incident_history": [],
        "steps_remaining": 16,
        "last_action_result": "",
        "actions_taken": [],
    }


def handle_action(action: OnCallAction, hidden: dict) -> tuple[dict, bool]:
    """
    Handle one agent action for Task 3.

    Mutates hidden state and returns observation updates.
    Reward is computed separately by rewards.compute_step_reward().

    Returns:
        (observation_updates, done)
    """
    action_type = action.action_type
    params = action.parameters
    updates: dict = {}
    done = False

    # Initialize tracking variables
    if "t3_rollback_target" not in hidden:
        hidden["t3_rollback_target"] = None
        hidden["t3_tables_rerun"] = []
        hidden["t3_notified_teams"] = set()

    if action_type == "inspect_logs":
        hidden["inspect_logs_called"] = True
        updates["deployment_history"] = [
            {"version": "3.1.2", "deployed_at": "Today 08:00 AM", "known_issues": "Current - bad JOIN suspected"},
            {"version": "3.1.1", "deployed_at": "Yesterday", "known_issues": "NULL bug in customer_region"},
            {"version": "3.1.0", "deployed_at": "3 days ago", "known_issues": "Stable - last known good"}
        ]
        updates["log_details"] = (
            "[ERROR] Downstream validation: duplicate customer_ids found in customer_master.\n"
            "[WARN] ads_spend pipeline: java.lang.OutOfMemoryError: Java heap space.\n"
            "[INFO] Deployment history retrieved successfully."
        )
        updates["last_action_result"] = "Logs inspected. Deployment history and OOM warning revealed."

    elif action_type == "check_dependencies":
        hidden["check_dependencies_called"] = True
        hidden["sla_critical_tables"] = ["revenue_daily", "customer_summary", "marketing_segments"]
        updates["dependency_map"] = {
            "customer_master": [
                "revenue_daily", "customer_summary", "marketing_segments",
                "orders_archive", "user_logs_1", "user_logs_2", "geo_map_1",
                "geo_map_2", "device_stats", "retention_30d", "churn_risk", "loyalty_points"
            ]
        }
        updates["last_action_result"] = (
            "Dependencies mapped. 12 tables depend on customer_master. "
            "SLA critical tables identified: revenue_daily, customer_summary, marketing_segments."
        )

    elif action_type == "check_resource_utilization":
        updates["resource_metrics"] = {
            "db_cpu": "15%",
            "db_memory": "40%",
            "cluster_memory": "ads_spend at 99%, analytics_pipeline at 20%"
        }
        updates["last_action_result"] = (
            "Resource metrics retrieved. DB usage is low. "
            "ads_spend is OOMing but analytics_pipeline is fine memory-wise."
        )

    elif action_type == "profile_data":
        updates["data_profile"] = {
            "customer_master.customer_id": "duplicate rate = 15.2% (expected 0%)",
            "revenue_daily.amount": "NULL rate = 0%"
        }
        updates["last_action_result"] = "Data profiling confirms bad JOIN causing duplicate customer_ids."

    elif action_type == "check_schema":
        updates["last_action_result"] = "Schema is unchanged."

    elif action_type == "alter_table":
        target = action.target
        if target == "orders_archive":
            updates["last_action_result"] = "Altered orders_archive. This is a red herring and didn't fix the root cause."
        else:
            updates["last_action_result"] = f"Altered {target}. Incorrect approach."

    elif action_type == "scale_up_executor":
        updates["last_action_result"] = (
            "Scaled up executor for ads_spend. "
            "WARNING: This wastes time while SLA breaches worsen. Did not resolve the analytics bad JOIN."
        )

    elif action_type == "rollback_deployment":
        version = params.get("version", "")
        if version == "3.1.0":
            hidden["rollback_applied"] = True
            hidden["rollback_version_correct"] = True
            hidden["t3_rollback_target"] = "3.1.0"
            updates["last_action_result"] = "Rolled back to 3.1.0. Code is now historically stable."
        elif version == "3.1.1":
            hidden["rollback_applied"] = True
            hidden["rollback_version_correct"] = False
            hidden["t3_rollback_target"] = "3.1.1"
            updates["last_action_result"] = (
                "Rolled back to 3.1.1."
                "\nCATASTROPHIC ERROR: Version 3.1.1 contains the known NULL bug. Data is corrupting worse now."
            )
        else:
            updates["last_action_result"] = f"Rollback to unknown or unstated version {version}."

    elif action_type == "trigger_rerun":
        if not hidden.get("rollback_applied"):
            updates["last_action_result"] = "Triggered rerun on bad code. Duplicates propagated further."
            return updates, done

        if not hidden.get("rollback_version_correct"):
            updates["last_action_result"] = "Triggered rerun on version 3.1.1. NULL data cascading down."
            return updates, done

        target = action.target
        if target in ("all", "customer_master"):
            updates["last_action_result"] = (
                "Triggered rerun on all 12 tables. "
                "WARNING: Processing queue overloaded. SLA tables delayed further."
            )
        elif target in ["revenue_daily", "customer_summary", "marketing_segments"]:
            expected_order = ["revenue_daily", "customer_summary", "marketing_segments"]
            current_idx = len(hidden["t3_tables_rerun"])  # next expected slot
            if current_idx >= len(expected_order) or target != expected_order[current_idx]:
                hidden["rerun_order_correct"] = False
                updates["last_action_result"] = f"Rerun {target} out of order. Higher SLA priorities ignored!"
            else:
                hidden["t3_tables_rerun"].append(target)  # only append when correct
                updates["last_action_result"] = f"Rerun {target} successful."
                if hidden["t3_tables_rerun"] == expected_order:
                    hidden["rerun_triggered"] = True
                    hidden["rerun_order_correct"] = True
                    hidden["pipeline_health"] = "restored"
                    updates["dag_task_statuses"] = {
                        "customer_master": "success",
                        "revenue_daily": "success",
                        "customer_summary": "success",
                        "marketing_segments": "success",
                    }
                    updates["last_action_result"] = "All 3 SLA-critical tables rerun successfully in exact order."
        else:
            updates["last_action_result"] = f"Triggered rerun on {target}, but SLA tables are still waiting."

    elif action_type == "notify_stakeholder":
        raw_team = str(params.get("team", "")).strip().lower()

        def normalize_team(t: str) -> str:
            if "sla" in t:
                return "sla"
            if "analytics" in t:
                return "analytics"
            if "business" in t:
                return "business"
            if "ads" in t:
                return "ads"
            return t

        team = normalize_team(raw_team)
        if team in ("sla", "analytics", "business", "ads"):
            if team not in hidden["t3_notified_teams"]:
                hidden["t3_notified_teams"].add(team)
                updates["last_action_result"] = f"Notified {team} team."
            else:
                updates["last_action_result"] = f"Already notified {team} team."
        else:
            updates["last_action_result"] = f"Notified {raw_team}."

    elif action_type == "skip_task":
        if action.target in hidden.get("sla_critical_tables", []):
            updates["last_action_result"] = "FATAL: Skipped an SLA critical table. Irrecoverable data loss for reporting."
        else:
            updates["last_action_result"] = f"Skipped {action.target}."
        done = True

    elif action_type == "fix_pipeline_config":
        updates["last_action_result"] = "Pipeline config wasn't the issue."

    else:
        updates["last_action_result"] = f"Unknown or invalid action: {action_type}."

    # Check for resolution — all conditions must be explicitly satisfied
    if (
        hidden.get("rollback_applied")
        and hidden.get("rollback_version_correct")
        and hidden.get("rerun_triggered")
        and hidden.get("rerun_order_correct")
        and "sla" in hidden.get("t3_notified_teams", set())
    ):
        done = True

    return updates, done
