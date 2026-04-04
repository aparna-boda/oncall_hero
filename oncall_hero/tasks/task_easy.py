# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Task 1 — "The Missing File" (Easy)

Scenario:
    Pipeline:     sales_etl_pipeline
    Failed task:  extract_s3_sales
    Root cause:   Filename naming convention changed
      Expected:   s3://prod-bucket/sales/sales_2024-04-01.csv
      Actual:     s3://prod-bucket/sales/SALES_20240401.csv
    Red herring:  Slow query warning on orders_summary (47s, threshold 30s)

Correct path: inspect_logs → fix_pipeline_config → trigger_rerun
"""

from oncall_hero.models import OnCallAction


def get_initial_observation() -> dict:
    """Return the initial observation dict for Task 1."""
    return {
        "incident_id": "INC-20240401-001",
        "task_id": "missing_source_file",
        "pipeline_name": "sales_etl_pipeline",
        "failed_task": "extract_s3_sales",
        "error_message": (
            "FileNotFoundError: s3://prod-bucket/sales/sales_2024-04-01.csv not found.\n"
            "WARNING: Slow query on orders_summary (47s, threshold: 30s) — "
            "may indicate performance degradation."
        ),
        "dag_task_statuses": {
            "extract_s3_sales": "failed",
            "transform_sales": "pending",
            "load_bigquery": "pending",
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
        "incident_history": [
            "2024-03-10: FileNotFoundError on sales/sales_2024-03-10.csv"
        ],
        "steps_remaining": 6,
        "last_action_result": "",
        "actions_taken": [],
    }


def handle_action(action: OnCallAction, hidden: dict) -> tuple[dict, float, bool]:
    """
    Handle one agent action for Task 1.

    Returns:
        (observation_updates, reward, done)
    """
    action_type = action.action_type
    updates: dict = {}
    reward = 0.0
    done = False

    if action_type == "inspect_logs":
        reward = 0.05
        hidden["inspect_logs_called"] = True
        updates["log_details"] = (
            "[ERROR] 2024-04-01 02:14:33 - Task: extract_s3_sales - Status: FAILED\n"
            "  FileNotFoundError: s3://prod-bucket/sales/sales_2024-04-01.csv\n"
            "\n"
            "  S3 bucket listing: s3://prod-bucket/sales/\n"
            "    SALES_20240401.csv  (3.2 MB, modified 2024-04-01 01:55:12)\n"
            "    SALES_20240331.csv  (3.1 MB, modified 2024-03-31 01:52:44)\n"
            "    SALES_20240330.csv  (3.0 MB, modified 2024-03-30 01:50:11)\n"
            "\n"
            "  ROOT CAUSE HINT: Naming convention changed as of 2024-04-01.\n"
            "  Pipeline expects: sales_YYYY-MM-DD.csv  (lowercase, hyphens)\n"
            "  Actual files:     SALES_YYYYMMDD.csv    (uppercase, no hyphens)\n"
            "\n"
            "[WARNING] 2024-04-01 02:10:05 - Task: orders_summary_refresh\n"
            "  Slow query detected: duration=47s (threshold: 30s)\n"
            "  Query: SELECT * FROM orders JOIN products ON orders.product_id = products.id\n"
            "  This warning is UNRELATED to the sales_etl_pipeline failure.\n"
        )
        updates["last_action_result"] = (
            "Logs retrieved. FileNotFoundError confirmed on sales_2024-04-01.csv. "
            "S3 bucket shows SALES_20240401.csv — naming convention changed to UPPERCASE "
            "with no hyphens. Slow query on orders_summary is a separate, unrelated warning."
        )

    elif action_type == "fix_pipeline_config":
        if hidden.get("inspect_logs_called"):
            reward = 0.25
            hidden["config_fixed"] = True
            updates["last_action_result"] = (
                "Pipeline config updated successfully. "
                "Filename pattern changed from 'sales_{YYYY-MM-DD}.csv' to 'SALES_{YYYYMMDD}.csv'. "
                "Config saved and validated."
            )
        else:
            reward = -0.05
            updates["last_action_result"] = (
                "Error: Cannot apply fix without diagnosing the root cause first. "
                "Inspect logs to identify what needs to be fixed."
            )

    elif action_type == "trigger_rerun":
        if hidden.get("config_fixed"):
            reward = 0.65
            done = True
            hidden["rerun_triggered"] = True
            hidden["pipeline_health"] = "restored"
            updates["last_action_result"] = (
                "Pipeline rerun triggered. "
                "extract_s3_sales: SUCCESS (loaded SALES_20240401.csv, 142,384 rows). "
                "transform_sales: SUCCESS. "
                "load_bigquery: SUCCESS. "
                "Pipeline RESTORED — SLA maintained."
            )
            updates["dag_task_statuses"] = {
                "extract_s3_sales": "success",
                "transform_sales": "success",
                "load_bigquery": "success",
            }
        else:
            reward = -0.30
            updates["last_action_result"] = (
                "Pipeline failed again. "
                "FileNotFoundError: s3://prod-bucket/sales/sales_2024-04-01.csv not found. "
                "The config was not fixed — rerun cannot succeed until the filename pattern is corrected."
            )

    elif action_type == "check_schema":
        reward = -0.05
        updates["source_schema"] = [
            {"column": "sale_id", "type": "INT64", "nullable": False},
            {"column": "product_id", "type": "INT64", "nullable": False},
            {"column": "amount", "type": "FLOAT64", "nullable": True},
            {"column": "sale_date", "type": "DATE", "nullable": False},
        ]
        updates["target_schema"] = [
            {"column": "sale_id", "type": "INT64", "nullable": False},
            {"column": "product_id", "type": "INT64", "nullable": False},
            {"column": "amount", "type": "FLOAT64", "nullable": True},
            {"column": "sale_date", "type": "DATE", "nullable": False},
        ]
        updates["last_action_result"] = (
            "Schema check complete. Source and target schemas match exactly. "
            "No schema mismatch found — this is not a schema issue."
        )

    elif action_type == "check_dependencies":
        reward = -0.05
        updates["dependency_map"] = {
            "extract_s3_sales": {
                "upstream": [],
                "downstream": ["transform_sales"],
                "status": "failed",
            },
            "transform_sales": {
                "upstream": ["extract_s3_sales"],
                "downstream": ["load_bigquery"],
                "status": "pending",
            },
            "load_bigquery": {
                "upstream": ["transform_sales"],
                "downstream": [],
                "status": "pending",
            },
        }
        updates["last_action_result"] = (
            "Dependency map retrieved. No upstream pipeline issues found. "
            "All dependencies are healthy. Root cause is within extract_s3_sales itself."
        )

    elif action_type == "check_resource_utilization":
        reward = -0.05
        updates["resource_metrics"] = {
            "cpu_usage_pct": 22.4,
            "memory_usage_pct": 41.1,
            "disk_io_mbps": 12.3,
            "network_io_mbps": 5.1,
            "executor_pool_free": 8,
            "executor_pool_total": 10,
        }
        updates["last_action_result"] = (
            "Resource utilization is normal. CPU: 22.4%, Memory: 41.1%, "
            "Disk I/O: 12.3 MB/s. No resource constraints detected."
        )

    elif action_type == "profile_data":
        reward = -0.05
        updates["last_action_result"] = (
            "Cannot profile data — pipeline failed before any data was loaded. "
            "No data available to profile."
        )

    elif action_type == "scale_up_executor":
        reward = -0.10
        updates["last_action_result"] = (
            "Executor pool scaled up from 10 to 15 nodes. "
            "However, this did not resolve the failure. "
            "Root cause is not resource-related — the source file is simply missing."
        )

    elif action_type == "rollback_deployment":
        reward = -0.10
        updates["last_action_result"] = (
            "No recent deployment found for sales_etl_pipeline (last deploy: 2024-03-15). "
            "Rollback is not applicable — this is not a deployment issue."
        )

    elif action_type == "alter_table":
        reward = -0.10
        updates["last_action_result"] = (
            "Table alteration attempted but no schema change is needed. "
            "Source and target schemas are compatible — this action was not required."
        )

    elif action_type == "notify_stakeholder":
        reward = 0.0
        updates["last_action_result"] = (
            "Stakeholders notified of the sales_etl_pipeline incident. "
            "Ticket INC-20240401-001 updated. Awaiting resolution."
        )

    elif action_type == "skip_task":
        reward = -0.30
        done = True
        updates["last_action_result"] = (
            "Task skipped. Pipeline left in failed state. "
            "SLA breached — downstream reports are missing today's sales data. "
            "This is a catastrophic outcome."
        )

    else:
        reward = 0.0
        updates["last_action_result"] = f"Unknown action type: '{action_type}'"

    return updates, reward, done
