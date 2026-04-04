# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Manual end-to-end test for all 4 OnCall Hero tasks.
No Docker, no LLM, no API keys required.

Tests each task with its optimal action sequence and verifies:
  - Step-level rewards are correct
  - Done flag triggers at the right step
  - Final grader score reaches ~0.95-1.00
"""

from oncall_hero.models import OnCallAction
from oncall_hero.graders import grade
from oncall_hero.tasks import task_easy, task_medium, task_hard, task_extreme


def act(action_type, target="pipeline", **params):
    return OnCallAction(action_type=action_type, target=target, parameters=params)


def run_task(label, module, actions):
    print(f"\n{'=' * 55}")
    print(f"  {label}")
    print("=" * 55)

    obs = module.get_initial_observation()
    hidden = {}
    rewards = []

    for i, a in enumerate(actions, 1):
        updates, reward, done = module.handle_action(a, hidden)
        obs.update(updates)
        rewards.append(reward)

        detail = ""
        if a.action_type == "alter_table":
            detail = f"  col={a.parameters.get('column')} type={a.parameters.get('type')}"
        elif a.action_type == "rollback_deployment":
            detail = f"  version={a.parameters.get('version')}"
        elif a.action_type == "trigger_rerun" and a.target != "pipeline":
            detail = f"  target={a.target}"
        elif a.action_type == "notify_stakeholder":
            detail = f"  team={a.parameters.get('team')}"

        print(f"  [{i:2d}] {a.action_type:<30} reward={reward:+.2f}  done={str(done):<5}{detail}")

        if done:
            break

    task_id = obs.get("task_id", label)
    actions_taken = [a.action_type for a in actions[: len(rewards)]]
    raw = sum(rewards)
    final = grade(task_id, actions_taken, hidden)
    clamped = max(0.0, min(1.0, raw))

    print(f"\n  Raw reward sum : {raw:.2f}  →  clamped: {clamped:.3f}")
    print(f"  Grader score   : {final:.3f}")
    print(f"  Pipeline health: {hidden.get('pipeline_health', 'unknown')}")
    return final


if __name__ == "__main__":
    scores = {}

    # ------------------------------------------------------------------ #
    # Task 1 — Easy: missing_source_file
    # Optimal path: inspect_logs → fix_pipeline_config → trigger_rerun
    # ------------------------------------------------------------------ #
    scores["easy"] = run_task(
        "Task 1 — Easy: missing_source_file",
        task_easy,
        [
            act("inspect_logs"),
            act("fix_pipeline_config"),
            act("trigger_rerun"),
        ],
    )

    # ------------------------------------------------------------------ #
    # Task 2 — Medium: schema_drift_bigquery
    # Optimal path: inspect_logs → check_schema → alter×2 → trigger_rerun
    # ------------------------------------------------------------------ #
    scores["medium"] = run_task(
        "Task 2 — Medium: schema_drift_bigquery",
        task_medium,
        [
            act("inspect_logs"),
            act("check_schema"),
            act("alter_table", column="discount_pct", type="FLOAT"),
            act("alter_table", column="quantity", type="BIGINT"),
            act("trigger_rerun"),
        ],
    )

    # ------------------------------------------------------------------ #
    # Task 3 — Hard: cascade_collapse
    # Optimal path: inspect_logs → check_dependencies → rollback(3.1.0)
    #               → rerun×3 in SLA order → notify sla_team
    # ------------------------------------------------------------------ #
    scores["hard"] = run_task(
        "Task 3 — Hard: cascade_collapse",
        task_hard,
        [
            act("inspect_logs"),
            act("check_dependencies"),
            act("rollback_deployment", version="3.1.0"),
            act("trigger_rerun", target="revenue_daily"),
            act("trigger_rerun", target="customer_summary"),
            act("trigger_rerun", target="marketing_segments"),
            act("notify_stakeholder", team="sla_team"),
        ],
    )

    # ------------------------------------------------------------------ #
    # Task 4 — Extreme: silent_data_corruption
    # Optimal path: inspect_logs → profile_data → rollback(4.1.5)
    #               → trigger_rerun → profile_data (verify) → notify×2
    # ------------------------------------------------------------------ #
    scores["extreme"] = run_task(
        "Task 4 — Extreme: silent_data_corruption",
        task_extreme,
        [
            act("inspect_logs"),
            act("profile_data"),
            act("rollback_deployment", version="4.1.5"),
            act("trigger_rerun"),
            act("profile_data"),
            act("notify_stakeholder", team="revenue_team"),
            act("notify_stakeholder", team="crm_team"),
        ],
    )

    # ================================================================== #
    # NEGATIVE EDGE CASES & TRAP TRAJECTORIES
    # Prove that the grading logic correctly deduces massive penalties.
    # ================================================================== #

    scores["trap_t1_premature"] = run_task(
        "Task 1 — TRAP: Premature Rerun (Penalty)",
        task_easy,
        [
            act("trigger_rerun"),
            act("fix_pipeline_config"),
        ],
    )

    scores["trap_t2_destructive"] = run_task(
        "Task 2 — TRAP: Unnecessary Rollback (Penalty)",
        task_medium,
        [
            act("inspect_logs"),
            act("check_schema"),
            act("rollback_deployment", version="2.3.0"),
        ],
    )

    scores["trap_t3_toxic_branch"] = run_task(
        "Task 3 — TRAP: Chose Toxic Branch 3.1.1 (Penalty)",
        task_hard,
        [
            act("inspect_logs"),
            act("rollback_deployment", version="3.1.1"),
            act("trigger_rerun", target="revenue_daily"),
        ],
    )

    scores["trap_t3_wrong_sla"] = run_task(
        "Task 3 — TRAP: Wrong SLA Rerun Order (Penalty)",
        task_hard,
        [
            act("inspect_logs"),
            act("rollback_deployment", version="3.1.0"),
            act("trigger_rerun", target="marketing_segments"),
            act("trigger_rerun", target="customer_summary"),
            act("trigger_rerun", target="revenue_daily"),
        ],
    )

    scores["trap_t4_gullible"] = run_task(
        "Task 4 — TRAP: Gullible Stop at SUCCESS (Penalty)",
        task_extreme,
        [
            act("inspect_logs"),
            # Agent theoretically stops here because logs say "SUCCESS"
        ],
    )

    # ------------------------------------------------------------------ #
    # Summary
    # ------------------------------------------------------------------ #
    print(f"\n{'=' * 55}")
    print("  SUMMARY")
    print("=" * 55)
    for task, score in scores.items():
        bar = "✓" if score >= 0.90 else ("~" if score >= 0.70 else "✗")
        print(f"  {bar}  {task:<10}  {score:.3f}")
    print()
