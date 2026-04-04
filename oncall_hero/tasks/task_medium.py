# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Task 2 — "The Double Drift" (Medium)

Scenario:
    Pipeline:     inventory_load_pipeline
    Failed task:  load_bigquery_inventory
    Root cause:   Schema drift on upstream CSV
    Changes:      discount_pct added (FLOAT), quantity changed INT -> BIGINT
    Red herring:  Deployment 2.3.1 applied at 07:45 AM
"""

from oncall_hero.models import OnCallAction


def get_initial_observation() -> dict:
    """Return the initial observation dict for Task 2."""
    return {
        "incident_id": "INC-20240401-002",
        "task_id": "schema_drift_bigquery",
        "pipeline_name": "inventory_load_pipeline",
        "failed_task": "load_bigquery_inventory",
        "error_message": (
            "BigQuery Error: Schema mismatch during load job.\n"
            "Failed at 08:35 AM.\n"
            "[INFO] Deployment 2.3.1 applied to pipeline successfully at 07:45 AM."
        ),
        "dag_task_statuses": {
            "extract_inventory": "success",
            "transform_inventory": "success",
            "load_bigquery_inventory": "failed",
        },
        "sla_breach": False,
        "sla_time_remaining_seconds": -1,
        "active_incidents": [],
        "source_schema": [],
        "target_schema": [],
        "dependency_map": {},
        "row_counts": {},
        "log_details": "",
        "resource_metrics": {},
        "data_profile": {},
        "deployment_history": [],
        "incident_history": [],
        "steps_remaining": 10,
        "last_action_result": "",
        "actions_taken": [],
    }


def handle_action(action: OnCallAction, hidden: dict) -> tuple[dict, float, bool]:
    """
    Handle one agent action for Task 2.

    Returns:
        (observation_updates, reward, done)
    """
    action_type = action.action_type
    params = action.parameters
    updates: dict = {}
    reward = 0.0
    done = False

    # Initialize task-specific hidden fields if not present
    if "t2_discount_added" not in hidden:
        hidden["t2_discount_added"] = False
        hidden["t2_quantity_fixed"] = False

    if action_type == "inspect_logs":
        reward = 0.10
        hidden["inspect_logs_called"] = True
        updates["log_details"] = (
            "[ERROR] 2024-04-01 08:35:12 - load_bigquery_inventory - FAILED\n"
            "  google.api_core.exceptions.BadRequest: 400 Provided Schema does not match Table.\n"
            "  Cannot add fields (field discount_pct is missing in destination table).\n"
            "  Cannot change field type (field quantity INT64 cannot be populated with BIGINT).\n"
            "\n"
            "[INFO] 2024-04-01 07:45:00 - Deployment 2.3.1 status: SUCCESS.\n"
            "[INFO] Pipeline executed normally from 07:45 AM until 08:30 AM CSV append.\n"
        )
        updates["last_action_result"] = (
            "Logs retrieved. Clear schema mismatch errors reported by BigQuery. "
            "Pipeline was stable after 07:45 deployment; failure began at 08:30 during load phase."
        )

    elif action_type == "check_schema":
        reward = 0.10
        hidden["check_schema_called"] = True
        updates["source_schema"] = [
            {"column": "product_id", "type": "STRING", "nullable": False},
            {"column": "quantity", "type": "BIGINT", "nullable": False},
            {"column": "discount_pct", "type": "FLOAT", "nullable": True},
        ]
        updates["target_schema"] = [
            {"column": "product_id", "type": "STRING", "nullable": False},
        ]
        
        # Build current target schema dynamically based on alterations
        if hidden["t2_quantity_fixed"]:
            updates["target_schema"].append({"column": "quantity", "type": "BIGINT", "nullable": False})
        else:
            updates["target_schema"].append({"column": "quantity", "type": "INT", "nullable": False})
            
        if hidden["t2_discount_added"]:
            updates["target_schema"].append({"column": "discount_pct", "type": "FLOAT", "nullable": True})
            
        updates["last_action_result"] = (
            "Schema comparison complete. "
            "Difference identified between source (CSV) and target (BigQuery)."
        )

    elif action_type == "alter_table":
        if not hidden.get("check_schema_called"):
            reward = -0.10
            updates["last_action_result"] = "Error: You must call check_schema before altering the table."
            return updates, reward, done

        col = params.get("column", "").lower()
        typ = params.get("type", "").upper()

        if col == "discount_pct":
            if typ == "FLOAT" or typ == "FLOAT64":
                if not hidden["t2_discount_added"]:
                    reward = 0.15
                    hidden["t2_discount_added"] = True
                    updates["last_action_result"] = "Table altered: discount_pct added as FLOAT."
                else:
                    updates["last_action_result"] = "Column discount_pct already added."
            else:
                reward = -0.10
                updates["last_action_result"] = f"Table alter failed: Incorrect type {typ} for discount_pct."
                
        elif col == "quantity":
            if typ == "BIGINT" or typ == "INT64":
                if not hidden["t2_quantity_fixed"]:
                    reward = 0.15
                    hidden["t2_quantity_fixed"] = True
                    updates["last_action_result"] = "Table altered: quantity type changed to BIGINT."
                else:
                    updates["last_action_result"] = "Column quantity is already BIGINT."
            elif typ in ["INT", "INTEGER", "INT32"]:
                reward = -0.30
                updates["last_action_result"] = "Table alter failed: Cannot change type to INT. It needs to fit the new larger capacity."
            else:
                reward = -0.10
                updates["last_action_result"] = f"Table alter failed: Incorrect type {typ} for quantity."
        else:
            reward = -0.10
            updates["last_action_result"] = f"Table alter failed: Unknown column {col}."

    elif action_type == "rollback_deployment":
        reward = -0.40  # Massive penalty for falling for the red herring
        updates["last_action_result"] = (
            "Deployment rolled back to 2.3.0. "
            "WARNING: This reverted critical unrelated hotfixes. "
            "Also, it did NOT fix the schema drift issue — the failure persists."
        )

    elif action_type == "trigger_rerun":
        if hidden["t2_discount_added"] and hidden["t2_quantity_fixed"]:
            reward = 0.55
            done = True
            hidden["pipeline_health"] = "restored"
            hidden["schema_fixed"] = True
            hidden["rerun_triggered"] = True
            updates["dag_task_statuses"] = {
                "extract_inventory": "success",
                "transform_inventory": "success",
                "load_bigquery_inventory": "success",
            }
            updates["last_action_result"] = (
                "Pipeline rerun triggered. "
                "load_bigquery_inventory: SUCCESS. "
                "Both schema drift issues successfully mitigated. Pipeline is heavily restored."
            )
        else:
            reward = -0.20
            updates["last_action_result"] = (
                "Pipeline failed again. "
                "BigQuery Error: Schema mismatch during load job. "
                "Not all discrepancies between source and destination tables have been resolved."
            )

    elif action_type == "check_dependencies":
        reward = -0.05
        updates["last_action_result"] = "Dependencies checked. No systemic downstream impact yet."

    elif action_type == "check_resource_utilization":
        reward = -0.05
        updates["last_action_result"] = "Resource utilization is normal."

    elif action_type == "scale_up_executor":
        reward = -0.10
        updates["last_action_result"] = "Scaled up executors. Had no effect on the load schema error."

    elif action_type == "profile_data":
        reward = -0.05
        updates["last_action_result"] = "Cannot profile data; pipeline failed before write."

    elif action_type == "notify_stakeholder":
        reward = 0.0
        updates["last_action_result"] = "Stakeholder notified."

    elif action_type == "skip_task":
        reward = -0.30
        done = True
        updates["last_action_result"] = "Task skipped. Final pipeline state is broken due to missing data."

    else:
        reward = 0.0
        updates["last_action_result"] = f"Unknown or invalid action for this task: {action_type}."

    return updates, reward, done
