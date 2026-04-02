# PRD — OnCall Hero
## Product Requirements Document v3.0
### Meta x PyTorch OpenEnv Hackathon — Round 1 Submission

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| v1.0 | Apr 2, 2026 | Initial PRD |
| v2.0 | Apr 2, 2026 | 4 tasks locked, 13 actions, all graders written, Task 4 added |
| v3.0 | Apr 2, 2026 | OpenEnv technical patterns corrected from official repos. Dockerfile updated. Repo structure fixed. Models pattern corrected (dataclasses + dual import). openenv.yaml format corrected (spec_version: 1). Observation base class notes added. Task 2b removed permanently. |

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Success Criteria](#3-goals--success-criteria)
4. [Environment Specification](#4-environment-specification)
5. [Observation Space](#5-observation-space)
6. [Action Space](#6-action-space)
7. [State Space (Hidden)](#7-state-space-hidden)
8. [Reward Function](#8-reward-function)
9. [Task Definitions](#9-task-definitions)
10. [Grader Design](#10-grader-design)
11. [Episode Logic](#11-episode-logic)
12. [Inference Script Spec](#12-inference-script-spec)
13. [Technical Stack](#13-technical-stack)
14. [Repo Structure](#14-repo-structure)
15. [openenv.yaml Spec](#15-openenvyaml-spec)
16. [Dockerfile Spec](#16-dockerfile-spec)
17. [Delivery Plan](#17-delivery-plan)
18. [Team Ownership](#18-team-ownership)
19. [Disqualification Checklist](#19-disqualification-checklist)
20. [Judging Criteria Alignment](#20-judging-criteria-alignment)

---

## 1. Project Overview

| Field | Value |
|---|---|
| **Environment Name** | OnCall Hero |
| **Tagline** | An RL training ground for AI agents that debug broken data pipelines |
| **Domain** | Data Pipeline Incident Response |
| **Framework** | OpenEnv (openenv-core) |
| **Language** | Python 3.12 |
| **Deployment** | Hugging Face Spaces + Docker |
| **Team Lead** | Aparna (sole submitter) |
| **Submission Deadline** | April 8, 2026 — 11:59 PM IST |
| **PRD Version** | v3.0 — April 2, 2026 |
| **Tasks** | 4 (Easy + Medium + Hard + Extreme) |
| **Actions** | 12 across 3 categories |

---

## 2. Problem Statement

### The Real-World Pain

Every data engineering team has experienced this: a 2 AM alert fires, a critical pipeline is broken, an SLA is about to breach, and an engineer must rapidly diagnose whether the root cause is a missing file, a schema change, a bad deployment, or something entirely different — then apply the right fix in the right order without breaking anything else.

This process requires:
- Reading and interpreting error logs
- Checking schema compatibility between source and target
- Tracing upstream/downstream DAG dependencies
- Distinguishing root causes from symptoms and red herrings
- Taking remediation actions in the correct order
- Sometimes finding issues even when the pipeline reports SUCCESS

Currently, **no RL environment exists** that trains or evaluates AI agents on this workflow. Tools like Datadog and PagerDuty detect pipeline failures — but they do not teach an agent how to reason about and fix them.

### What We Are Building

OnCall Hero simulates production data pipeline incidents. An AI agent acts as an on-call data engineer. It receives alerts, reads error logs, inspects schemas, checks dependencies, profiles data quality, diagnoses the root cause, and applies the correct remediation — all through a structured OpenEnv `step()`/`reset()`/`state()` API.

### Why This Fills a Real Gap

- Models like GPT-4 can describe how to fix a pipeline — but they have never been trained on the reward signal of actually fixing one
- Pipeline failures cost data teams 4–6 engineering hours per incident on average
- At a company running 500 pipelines, that is millions in lost productivity annually
- Silent data quality failures (pipeline succeeds but data is wrong) are the hardest class of incident — no existing tool trains agents to detect them
- This environment provides the first RL training ground for agents that can autonomously resolve data pipeline incidents

### Differentiation Statement (for README)

> "Existing tools like Datadog alert you that a pipeline failed. They do not teach an AI how to reason about why it failed. OnCall Hero provides the reward signal needed to train agents that can autonomously diagnose and fix incidents — not just detect them. No existing OpenEnv environment targets data pipeline incident response. Our Task 4 introduces silent data corruption — a category of incident that no current benchmark evaluates at all."

---

## 3. Goals & Success Criteria

### Hackathon Goals

| Goal | Metric |
|---|---|
| Pass all pre-submission checks | openenv validate passes, HF Space returns 200, Docker builds |
| Minimum 3 tasks submitted | Tasks 1, 2, 3 mandatory — Task 4 is bonus |
| All graders score in 0.0–1.0 | Verified by automated judge scripts |
| Inference script completes | Under 20 minutes on 2 vCPU / 8 GB RAM |
| Baseline scores reproducible | Same scores on every run with same seed |

### Quality Goals

| Criterion | Weight | Target |
|---|---|---|
| Real-world utility | 30% | 30/30 |
| Task & grader quality | 25% | 24/25 |
| Environment design | 20% | 19/20 |
| Code quality & compliance | 15% | 14/15 |
| Creativity & novelty | 10% | 10/10 |
| **Total** | **100%** | **97/100** |

### Submission Priority Rule

```
Task 1 ✅ → Task 2 ✅ → Task 3 ✅ → Safe to submit
                                   → Task 4 if time permits
```

---

## 4. Environment Specification

### Core API

| Method | Description |
|---|---|
| `reset(task_id)` | Loads fresh incident scenario. Clears all history. Returns initial Observation. |
| `step(action)` | Applies one structured action. Mutates hidden state. Returns (Observation, reward, done, info). |
| `state()` | Returns full internal EnvironmentState for debugging and evaluation. |

### Environment Flow

```
reset(task_id)
    │
    ▼
Initial Observation (alert fires, partial error visible)
    │
    ▼
Agent calls step(action) repeatedly
    │
    ├── Each step → new Observation + reward + done flag
    ├── Intermediate rewards fire on every relevant action
    └── Episode ends when:
            - Pipeline restored + correct fix applied
            - Max steps exhausted
            - Catastrophic wrong action taken
            - SLA hard deadline passed (Tasks 3 & 4)
```

### Observation vs State Separation

The agent only sees the **Observation**. The full **State** is hidden — used only by graders and the `state()` endpoint. This prevents tasks from being trivial — the agent must discover root cause through investigation.

### Architecture (from meta-pytorch/OpenEnv)

```
┌─────────────────────────────────────────────────────────┐
│  inference.py                                           │
│  OnCallHeroEnv(EnvClient) ← from client.py             │
└──────────────────────┬──────────────────────────────────┘
                       │ WebSocket (/ws) — default
                       │ reset() / step() / state()
┌──────────────────────▼──────────────────────────────────┐
│  Docker Container (HF Space / local)                   │
│  FastAPI Server — server/app.py                        │
│  OnCallHeroEnvironment(Environment)                     │
└─────────────────────────────────────────────────────────┘
```

---

## 5. Observation Space

### Critical notes from OpenEnv base class

The `Observation` base class already includes `done` and `reward`. Do NOT redefine these in your subclass.

```python
# From openenv rfcs/002-env-spec.md
# Observation base class already has:
done: bool = False
reward: Union[bool, int, float, None] = None
metadata: Dict[str, Any] = field(default_factory=dict)
```

### OnCall Hero Observation

```python
from dataclasses import dataclass, field
from openenv.core.env_server import Observation

@dataclass
class OnCallObservation(Observation):
    # Identity
    incident_id: str = ""
    task_id: str = ""                       # "easy" | "medium" | "hard" | "extreme"
    pipeline_name: str = ""
    failed_task: str = ""

    # Error context (always visible)
    error_message: str = ""                 # Raw error — may contain distractors
    dag_task_statuses: dict = field(default_factory=dict)
    sla_breach: bool = False
    sla_time_remaining_seconds: int = -1    # -1 if no SLA

    # Multi-incident context (Task 3)
    active_incidents: list = field(default_factory=list)
    # e.g. [{"pipeline": "ads_spend", "severity": "HIGH", "sla_breach": False}]

    # Evidence — progressive disclosure (all empty until agent inspects)
    source_schema: list = field(default_factory=list)      # check_schema
    target_schema: list = field(default_factory=list)      # check_schema
    dependency_map: dict = field(default_factory=dict)     # check_dependencies
    row_counts: dict = field(default_factory=dict)         # always visible
    log_details: str = ""                                   # inspect_logs
    resource_metrics: dict = field(default_factory=dict)   # check_resource_utilization
    data_profile: dict = field(default_factory=dict)       # profile_data
    deployment_history: list = field(default_factory=list) # inspect_logs (reveals versions)
    # e.g. [
    #   {"version": "3.1.2", "deployed_at": "08:00", "known_issues": "bad JOIN"},
    #   {"version": "3.1.1", "deployed_at": "yesterday", "known_issues": "NULL bug"},
    #   {"version": "3.1.0", "deployed_at": "3 days ago", "known_issues": "none"}
    # ]

    # Novel mechanic — incident memory
    incident_history: list = field(default_factory=list)
    # e.g. ["2024-03-15: schema drift", "2024-03-28: OOM on spark_etl"]

    # Episode tracking
    steps_remaining: int = 0
    last_action_result: str = ""
    actions_taken: list = field(default_factory=list)
    # done and reward are INHERITED from Observation base class
```

### Design Principles

- **Progressive disclosure:** 7 evidence fields start empty. Populated only when agent calls the corresponding inspection action. Forces real investigation.
- **Incident history:** Agent memory of past failures. Recurring OOM is faster to diagnose. No other OpenEnv environment has this mechanic.
- **Active incidents:** Tasks 3 and 4 present multiple simultaneous alerts. Agent must triage priority.
- **Deployment history:** Revealed only after `inspect_logs`. Shows version history with known issues — critical for Task 3 partial rollback.
- **Distractors:** `error_message` always contains at least one misleading signal alongside the real error.

---

## 6. Action Space

### Action Model

```python
from dataclasses import dataclass
from openenv.core.env_server import Action

@dataclass
class OnCallAction(Action):
    action_type: str      # One of 12 valid types below
    target: str           # Pipeline task or table being acted on
    parameters: dict      # Action-specific parameters (version, column name, etc.)
    justification: str    # Agent's reasoning — used in investigation score
```

### 12 Valid Action Types

#### Category 1 — Diagnostic & Investigation (5 actions)

| Action | Description | When to Use |
|---|---|---|
| `inspect_logs` | Read detailed error logs. Also reveals `deployment_history`. | First or second step |
| `check_schema` | Compare source vs target column names and types | When error suggests schema issue |
| `check_dependencies` | View upstream/downstream DAG relationships | When cause may be upstream |
| `check_resource_utilization` | View CPU/memory/disk graphs for compute clusters | Pre-step before scale_up_executor |
| `profile_data` | View null %, duplicate rates, value distributions | When pipeline succeeds but data looks wrong |

#### Category 2 — Remediation & Fix (4 actions)

| Action | Description | When to Use |
|---|---|---|
| `alter_table` | Modify target table schema — add column or fix type | After check_schema confirms mismatch |
| `scale_up_executor` | Increase Spark executor memory/cores | After check_resource_utilization confirms OOM |
| `rollback_deployment` | Revert pipeline code to previous version | When bad deploy confirmed — must specify version |
| `fix_pipeline_config` | Update pipeline config — filename pattern, watermark | When config mismatch is root cause |

#### Category 3 — Operational & Communication (3 actions)

| Action | Description | When to Use |
|---|---|---|
| `trigger_rerun` | Restart specific failed task or sequence | Only after root cause fully addressed |
| `notify_stakeholder` | Alert data owners or business users | When SLA breach detected or fix underway |
| `skip_task` | Mark task as skipped to allow pipeline to continue | Rarely correct — usually penalized |

### Action Constraints

- `alter_table` requires `check_schema` first — otherwise returns error, no state change
- `scale_up_executor` without `check_resource_utilization` returns warning + penalty
- `trigger_rerun` before root cause fixed returns error + penalty
- `rollback_deployment` must specify target version in `parameters`
- `profile_data` is the ONLY way to detect Task 4 null corruption
- `skip_task` is syntactically valid but penalized in grader for all tasks

### Action → Task Mapping

| Action | Task 1 | Task 2 | Task 3 | Task 4 |
|---|---|---|---|---|
| `inspect_logs` | ✅ Required | ✅ Required | ✅ Required | ✅ Required (shows SUCCESS) |
| `check_schema` | ❌ Not needed | ✅ Required x2 | ❌ Red herring | ❌ Not needed |
| `check_dependencies` | ❌ Not needed | ❌ Not needed | ✅ Required | ❌ Not needed |
| `check_resource_utilization` | ❌ Not needed | ❌ Not needed | ✅ Required | ❌ Not needed |
| `profile_data` | ❌ Not needed | ❌ Not needed | ✅ Required | ✅ ONLY way to find NULLs |
| `alter_table` | ❌ Wrong | ✅ Required x2 | ❌ Red herring | ❌ Not needed |
| `scale_up_executor` | ❌ Wrong | ❌ Wrong | ❌ Red herring | ❌ Not needed |
| `rollback_deployment` | ❌ Wrong | 🔴 Red herring trap | ✅ Required (3.1.0 not 3.1.1) | ✅ Required |
| `fix_pipeline_config` | ✅ Required | ❌ Not needed | ❌ Not needed | ❌ Not needed |
| `trigger_rerun` | ✅ Required | ✅ Required | ✅ Required (order matters) | ✅ Required |
| `notify_stakeholder` | ❌ Optional | ❌ Optional | ✅ Required x2 | ✅ Required |
| `skip_task` | ❌ Penalized | ❌ Penalized | ✅ Required (1 pipeline) | ❌ Penalized |

---

## 7. State Space (Hidden)

Full internal truth — visible only via `state()` endpoint. Never in Observation.

```python
from dataclasses import dataclass, field
from openenv.core.env_server import State

@dataclass
class OnCallState(State):
    # Ground truth (hidden from agent)
    true_root_cause: str = ""
    correct_action_sequence: list = field(default_factory=list)
    red_herring_active: bool = False
    red_herring_description: str = ""

    # Pipeline state
    pipeline_health: str = "broken"         # "broken" | "partially_fixed" | "restored"
    schema_fixed: bool = False              # Task 2
    config_fixed: bool = False              # Task 1
    rollback_applied: bool = False          # Tasks 3 & 4
    rollback_version_correct: bool = False  # Task 3 — 3.1.0 vs 3.1.1
    rerun_triggered: bool = False
    rerun_order_correct: bool = False       # Task 3
    null_data_detected: bool = False        # Task 4
    verification_done: bool = False         # Task 4 post-fix check

    # Task 3 specific
    sla_critical_tables: list = field(default_factory=list)
    noisy_neighbour_acknowledged: bool = False
    deployment_history_checked: bool = False

    # Episode tracking
    task_id: str = ""
    is_done: bool = False
    terminal_reason: str = ""

    # Live grader sub-scores (updated each step)
    investigation_score: float = 0.0       # max 0.20
    root_cause_score: float = 0.0          # max 0.30
    remediation_score: float = 0.0         # max 0.30
    efficiency_score: float = 0.0          # max 0.10
    sla_score: float = 0.0                 # max 0.10
    penalty_total: float = 0.0             # negative values only
    # episode_id and step_count are INHERITED from State base class
```

---

## 8. Reward Function

### Design Philosophy

Rewards fire at every relevant step — not just at episode end. Dense feedback for RL training.

### Per-Step Rewards

```
# Positive — correct investigation
+0.05   inspect_logs called as first or second action
+0.05   check_schema when error suggests schema issue
+0.05   check_dependencies before trigger_rerun (Tasks 3+)
+0.05   check_resource_utilization before scale_up_executor
+0.05   profile_data when pipeline shows SUCCESS (Task 4)
+0.05   notify_stakeholder when SLA breach is active
+0.05   deployment_history consulted before rollback_deployment

# Positive — meaningful progress
+0.10   Agent correctly identifies root cause category
+0.10   Agent ignores red herring and stays on correct path
+0.15   Correct remediation action applied
+0.10   Pipeline health: "broken" → "partially_fixed"
+0.20   Pipeline health: "partially_fixed" → "restored"

# Efficiency bonus
+0.10   Episode solved in ≤ 60% of max step budget

# Penalties
-0.05   Irrelevant action taken
-0.10   trigger_rerun before root cause fixed
-0.15   alter_table with wrong column type
-0.20   scale_up_executor when OOM is not root cause
-0.20   rollback_deployment to wrong version (Task 3 — introduces NULL bug)
-0.30   trigger_rerun in wrong dependency order (Task 3)
-0.30   skip_task on SLA-critical table
-0.40   rollback_deployment when schema drift is root cause (Task 2 trap)
-0.50   Wrong fix that breaks another downstream table
-0.80   Agent fixes symptom only — misses true root cause
```

### Final Score Computation

```python
def compute_final_score(state: OnCallState) -> float:
    raw = (
        state.investigation_score   # max 0.20
        + state.root_cause_score    # max 0.30
        + state.remediation_score   # max 0.30
        + state.efficiency_score    # max 0.10
        + state.sla_score           # max 0.10
        + state.penalty_total       # negative
    )
    return max(0.0, min(1.0, raw))  # always clamp to [0.0, 1.0]
```

---

## 9. Task Definitions

### Task 1 — Easy: "The Missing File"

| Field | Value |
|---|---|
| **ID** | `missing_source_file` |
| **Score Range** | 0.85–1.0 |
| **Step Budget** | 6 |

**Scenario:**
Daily sales ETL fails with `FileNotFoundError`. The file *exists* on S3 but with a different naming convention than the pipeline expects. A slow query warning on a different table appears as a distractor.

```
Pipeline expects:  s3://prod-bucket/sales/sales_2024-04-01.csv
Actual file on S3: s3://prod-bucket/sales/SALES_20240401.csv
                   (uppercase + no hyphens)

Red herring: [WARN] Query on orders_summary took 47s
```

**Correct Path:**
```
inspect_logs → identifies naming mismatch (not just missing file)
fix_pipeline_config → updates expected filename pattern
trigger_rerun → pipeline finds file, succeeds
```

**Traps:**
```
trigger_rerun before fix_pipeline_config → -0.30 (fails again)
investigate slow query warning → -0.10 per wasted step
```

**Grader:**
```
+0.15  inspect_logs called
+0.20  Naming mismatch identified (not just "file missing")
+0.15  Slow query distractor ignored
+0.25  fix_pipeline_config with correct pattern
+0.15  trigger_rerun called AFTER fix
+0.10  Pipeline restores successfully
```

---

### Task 2 — Medium: "The Double Drift"

| Field | Value |
|---|---|
| **ID** | `schema_drift_bigquery` |
| **Score Range** | 0.55–0.85 |
| **Step Budget** | 10 |

**Scenario:**
BigQuery table fails. Same morning: a new pipeline version was deployed AND the upstream CSV had two simultaneous schema changes. Deployment is a red herring.

```
Timeline:
  07:45 AM   Deploy 2.3.1 applied
  08:30 AM   CSV schema changes pushed (2 changes)
  08:35 AM   inventory_load_pipeline fails

Schema changes:
  discount_pct  → missing column (FLOAT)
  quantity      → type changed INT → BIGINT

Red herring: deployment 2.3.1 at 07:45 AM looks suspicious
```

**Correct Path:**
```
inspect_logs → schema errors, not deployment issue
check_schema → reveals both: missing discount_pct FLOAT + quantity INT vs BIGINT
alter_table → adds discount_pct FLOAT (not INT)
alter_table → fixes quantity INT → BIGINT
trigger_rerun → both fixes applied, pipeline succeeds
```

**Traps:**
```
rollback_deployment      → -0.40 (deployment is red herring)
alter_table with INT     → -0.30 (wrong type)
trigger_rerun after 1 fix only → -0.20 (still fails)
```

**Grader:**
```
+0.10  inspect_logs called
+0.10  check_schema called before any alter_table
+0.10  Agent does NOT call rollback_deployment
+0.15  discount_pct FLOAT identified correctly
+0.15  quantity BIGINT identified correctly
+0.10  alter_table for discount_pct correct type
+0.10  alter_table for quantity correct type
+0.10  trigger_rerun only after BOTH fixes
+0.10  Pipeline restored
```

---

### Task 3 — Hard: "The Cascade Collapse"

| Field | Value |
|---|---|
| **ID** | `cascade_collapse` |
| **Score Range** | 0.25–0.65 |
| **Step Budget** | 16 |

**Scenario:**
Deploy 3.1.2 has bad JOIN logic → corrupts customer_master → 12 downstream tables stale → 3 SLA breaches. Simultaneously: ads_spend pipeline is OOMing on same cluster (noisy neighbour). One downstream table has independent schema drift (red herring). Rolling back requires skipping unsafe version 3.1.1.

```
Timeline:
  08:00  Deploy 3.1.2 — bad JOIN logic
  09:15  3 SLA breaches (revenue_daily, customer_summary, marketing_segments)
  09:20  ads_spend OOM fires on same cluster (separate incident)

Deployment history (revealed after inspect_logs):
  3.1.2  current — bad JOIN (ROOT CAUSE)
  3.1.1  deprecated — NULL bug in customer_region (UNSAFE to rollback here)
  3.1.0  stable — last known good (CORRECT rollback target)

SLA-critical tables (must rerun first):
  revenue_daily → 1st
  customer_summary → 2nd
  marketing_segments → 3rd

Red herrings:
  ads_spend OOM → separate issue (different fix needed later)
  orders_archive schema drift → independent issue (do not fix now)
```

**Correct Path:**
```
inspect_logs → cascade + ads OOM + deployment history revealed
check_dependencies → 12 affected tables, 3 SLA-critical identified
profile_data → duplicate customer_ids confirms bad JOIN
check_resource_utilization → DB CPU low → rules out infra
rollback_deployment → to 3.1.0 (skip 3.1.1)
trigger_rerun revenue_daily → 1st (SLA critical)
trigger_rerun customer_summary → 2nd
trigger_rerun marketing_segments → 3rd
notify_stakeholder → SLA team
notify_stakeholder → ads team (separate message)
```

**Traps:**
```
rollback to 3.1.1          → -0.40 (introduces NULL bug)
scale_up_executor          → -0.20 (chasing ads OOM)
alter_table on orders_archive → -0.30 (red herring)
trigger_rerun all 12       → -0.20 (ignores SLA priority)
trigger_rerun before rollback → -0.30 (propagates bad data)
```

**Grader:**
```
+0.08  inspect_logs called — deployment history revealed
+0.08  check_dependencies called — blast radius mapped
+0.08  profile_data called — bad JOIN confirmed
+0.06  check_resource_utilization — DB CPU rules out infra
+0.08  Agent does NOT scale_up_executor (ignores ads OOM)
+0.08  Agent does NOT alter_table on orders_archive (ignores red herring)
+0.10  rollback_deployment to 3.1.0 (skips 3.1.1)
+0.08  trigger_rerun revenue_daily first
+0.08  trigger_rerun customer_summary second
+0.08  trigger_rerun marketing_segments third
+0.10  notify_stakeholder — SLA team
+0.10  notify_stakeholder — ads team (separate)
```

---

### Task 4 — Extreme: "The Silent Killer"

| Field | Value |
|---|---|
| **ID** | `silent_data_corruption` |
| **Score Range** | 0.10–0.45 |
| **Step Budget** | 18 |

**Scenario:**
Pipeline finishes with `status = SUCCESS`. No error thrown. Revenue dashboard shows 50% drop. Upstream source started sending NULL for `price` column. Agent starts completely blind.

```
error_message: ""  (empty — pipeline succeeded)
dag_task_statuses: {"extract": "success", "transform": "success", "load": "success"}
sla_breach: True   (dashboard SLA breached)

What actually happened:
  CRM export started sending NULL for price at 06:00 AM
  Pipeline ran at 07:00 AM — processed NULLs without error
  Revenue calculations all returned NULL or 0

Conflicting signals (after profile_data):
  price:        52% NULL  ← ROOT CAUSE
  customer_id:  3% NULL   ← pre-existing, different team's problem
  quantity:     0% NULL   ← clean
```

**Correct Path:**
```
inspect_logs → returns SUCCESS — no errors found
profile_data → finds 52% NULL in price (not customer_id)
rollback_deployment → version with data quality checks on price
trigger_rerun → reloads with quality checks active
notify_stakeholder → revenue team + upstream CRM team
```

**Verification Trap:**
After trigger_rerun shows SUCCESS — agent must call `profile_data` again to verify 0% NULLs before closing. If 2% duplicates found in customer_id — this is pre-existing, handle separately.

**Traps:**
```
Stop at SUCCESS in inspect_logs       → -0.80 (misses root cause entirely)
Fix customer_id instead of price      → -0.40 (wrong column)
trigger_rerun before rollback         → -0.30 (same NULLs reloaded)
Close without notifying CRM team      → -0.20 (problem recurs next day)
Close without post-fix verification   → -0.20
```

**Grader:**
```
+0.10  inspect_logs called (returns SUCCESS — agent continues)
+0.15  profile_data called despite SUCCESS status
+0.10  price NULL identified as root cause (not customer_id)
+0.05  customer_id NULL recognized as separate pre-existing issue
+0.15  rollback_deployment to version with quality checks
+0.10  trigger_rerun after rollback
+0.10  post-fix profile_data called to verify
+0.10  notify_stakeholder for revenue team
+0.10  notify_stakeholder for CRM team
+0.05  incident_history referenced (prior NULL spike noted)
```

---

## 10. Grader Design

### Unified Grader Architecture

```python
def grade_episode(
    task_id: str,
    actions_taken: list[OnCallAction],
    final_state: OnCallState
) -> GraderResult:

    scores = {
        "investigation": grade_investigation(task_id, actions_taken),       # 0.0–0.20
        "root_cause":    grade_root_cause(task_id, actions_taken, final_state),   # 0.0–0.30
        "remediation":   grade_remediation(task_id, actions_taken, final_state),  # 0.0–0.30
        "efficiency":    grade_efficiency(task_id, actions_taken, final_state),   # 0.0–0.10
        "sla":           grade_sla(task_id, actions_taken, final_state),          # 0.0–0.10
    }

    penalties = compute_penalties(task_id, actions_taken, final_state)

    raw = sum(scores.values()) + penalties
    final_score = max(0.0, min(1.0, raw))   # always clamp

    return GraderResult(
        task_id=task_id,
        final_score=final_score,
        subscores=scores,
        penalties=penalties,
        terminal_reason=final_state.terminal_reason
    )
```

### Grader Properties

| Property | Design |
|---|---|
| **Deterministic** | All rules are boolean checks on action sequences and state fields |
| **Reproducible** | Same actions on same task → same score every run |
| **Partial credit** | Each sub-step scored independently |
| **Clamped** | Final score always in [0.0, 1.0] regardless of penalties |
| **Transparent** | GraderResult exposes all subscores for debugging |

---

## 11. Episode Logic

### Done Conditions

```python
def check_done(state: OnCallState) -> tuple[bool, str]:
    if state.pipeline_health == "restored" and rerun_triggered_correctly(state):
        return True, "pipeline_restored"

    if state.step_count >= state.max_steps:
        return True, "max_steps_exhausted"

    if catastrophic_action_taken(state):
        return True, "catastrophic_action"

    if state.task_id in ["cascade_collapse", "silent_data_corruption"]:
        if sla_hard_deadline_passed(state):
            return True, "sla_deadline_passed"

    return False, ""
```

### Step Budgets

| Task | Max Steps | Rationale |
|---|---|---|
| `missing_source_file` | 6 | 3 correct actions + 3 for exploration |
| `schema_drift_bigquery` | 10 | 5 correct actions + 5 for investigation |
| `cascade_collapse` | 16 | 11 correct actions + 5 for investigation |
| `silent_data_corruption` | 18 | 9 correct actions + 9 for investigation |

### Catastrophic Actions

These end the episode immediately with heavy penalty:

- `rollback_deployment` to 3.1.1 in Task 3 (introduces NULL bug)
- `trigger_rerun` full DAG when only specific tables need rerunning
- `skip_task` on SLA-critical table
- `alter_table` with completely wrong schema that breaks downstream consumers

---

## 12. Inference Script Spec

### File Requirements

| Field | Value |
|---|---|
| **Filename** | `inference.py` — exactly this name |
| **Location** | Root of GitHub repo — never inside any subfolder |
| **Runtime** | Under 20 minutes for all tasks combined |
| **Resources** | 2 vCPU / 8 GB RAM |

### Environment Variables

```python
import os
API_BASE_URL = os.environ["API_BASE_URL"]     # Provided by hackathon dashboard
MODEL_NAME   = os.environ["MODEL_NAME"]       # Provided by hackathon dashboard
HF_TOKEN     = os.environ["HF_TOKEN"]         # Your HF token
API_KEY      = os.environ.get("OPENAI_API_KEY", HF_TOKEN)
```

### LLM Client Pattern

```python
from openai import OpenAI

client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

completion = client.chat.completions.create(
    model=MODEL_NAME,
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": user_prompt},
    ],
    temperature=0.0,      # deterministic for reproducibility
    max_tokens=500,
    stream=False,
)
```

### Mandatory Log Format

**Do NOT deviate. Any change breaks automated scoring.**

```
[START] task=missing_source_file env=oncall_hero model=gpt-4o

[STEP] step=1 action=inspect_logs reward=0.05 done=False error=None
[STEP] step=2 action=fix_pipeline_config reward=0.25 done=False error=None
[STEP] step=3 action=trigger_rerun reward=0.65 done=True error=None

[END] success=True steps=3 score=0.95 rewards=[0.05, 0.25, 0.65]
```

### Score Computation

```python
MAX_TOTAL_REWARD = 1.0
SUCCESS_THRESHOLD = 0.5

score = sum(rewards) / MAX_TOTAL_REWARD
score = min(max(score, 0.0), 1.0)
success = score >= SUCCESS_THRESHOLD
```

### Task Loop

Run all 3 mandatory tasks sequentially. Task 4 is optional. Total runtime under 20 minutes.

---

## 13. Technical Stack

| Component | Choice | Reason |
|---|---|---|
| Language | Python 3.12 | Confirmed working — current installed version |
| Framework | openenv-core | Hackathon requirement |
| Models | dataclasses + openenv base classes | Official pattern from meta-pytorch/OpenEnv |
| LLM client | OpenAI Python SDK | Hackathon requirement |
| Server | FastAPI + create_fastapi_app | OpenEnv official helper |
| Protocol | WebSocket (/ws) | OpenEnv default — lower latency |
| Containerization | Docker | Hackathon requirement |
| Deployment | Hugging Face Spaces | Hackathon requirement |
| Port | 8000 | OpenEnv standard |
| Dep management | pyproject.toml (primary) + server/requirements.txt (Docker) | Official OpenEnv pattern |

### Infrastructure Constraints

- Max 2 vCPU, 8 GB RAM
- Inference under 20 minutes across all tasks
- No external API calls in environment (fully simulated, all state in memory)
- No database required

---

## 14. Repo Structure

```
oncall_hero/                          ← GitHub repo root
│
├── .venv/                            ← gitignored — never commit
├── .gitignore
├── .env                              ← gitignored — API keys
├── .env.example                      ← safe to commit
├── LICENSE
├── README.md
├── inference.py                      ← MUST be here, MUST be named inference.py
│
└── oncall_hero/                      ← generated by openenv init
    ├── __init__.py                   ← exports OnCallHeroEnv, OnCallAction, OnCallObservation
    ├── README.md
    ├── client.py                     ← OnCallHeroEnv(EnvClient)
    ├── models.py                     ← OnCallAction, OnCallObservation, OnCallState
    ├── openenv.yaml                  ← spec_version: 1 format
    ├── pyproject.toml                ← PRIMARY dependency file
    ├── uv.lock                       ← gitignored
    │
    ├── rewards.py                    ← per-step + terminal reward logic
    ├── graders.py                    ← unified grader + task-specific rules
    │
    ├── tasks/
    │   ├── __init__.py
    │   ├── task_easy.py              ← "The Missing File"
    │   ├── task_medium.py            ← "The Double Drift"
    │   ├── task_hard.py              ← "The Cascade Collapse"
    │   └── task_extreme.py           ← "The Silent Killer" (bonus)
    │
    ├── outputs/                      ← gitignored (runtime logs/evals)
    │
    └── server/
        ├── __init__.py
        ├── app.py                    ← create_fastapi_app(CLASS, Action, Obs)
        ├── oncall_hero_environment.py ← OnCallHeroEnvironment(Environment)
        ├── requirements.txt          ← Docker deps only
        └── Dockerfile
```

### Critical Patterns

```python
# 1. Dual import — REQUIRED in ALL server files
try:
    from ..models import OnCallAction, OnCallObservation
except ImportError:
    from models import OnCallAction, OnCallObservation

# 2. Pass CLASS not instance to create_fastapi_app
app = create_fastapi_app(OnCallHeroEnvironment, OnCallAction, OnCallObservation)
# NOT: env = OnCallHeroEnvironment(); create_fastapi_app(env, ...)

# 3. __init__.py exports
from oncall_hero.client import OnCallHeroEnv
from oncall_hero.models import OnCallAction, OnCallObservation, OnCallState
__all__ = ["OnCallHeroEnv", "OnCallAction", "OnCallObservation", "OnCallState"]
```

---

## 15. openenv.yaml Spec

**Critical: use `spec_version: 1` — older format is rejected by validators.**

```yaml
spec_version: 1
name: oncall-hero
type: standard
runtime: docker
app: server/app.py
port: 8000
description: >
  OnCall Hero simulates production data pipeline incidents.
  An AI agent acts as an on-call data engineer — reading logs,
  diagnosing root causes, and applying correct remediation actions.
  Features 4 tasks from easy to extreme, 12 structured actions,
  and novel mechanics: incident_history memory, progressive evidence
  disclosure, deployment version reasoning, multi-incident triage.

tasks:
  - id: missing_source_file
    name: "The Missing File"
    difficulty: easy
    description: "Filename convention mismatch — FileNotFoundError with distractor"
    max_steps: 6
    target_score_range: [0.85, 1.0]

  - id: schema_drift_bigquery
    name: "The Double Drift"
    difficulty: medium
    description: "Two simultaneous schema changes + deployment red herring"
    max_steps: 10
    target_score_range: [0.55, 0.85]

  - id: cascade_collapse
    name: "The Cascade Collapse"
    difficulty: hard
    description: "Bad JOIN cascades to 12 tables — partial rollback + noisy neighbour"
    max_steps: 16
    target_score_range: [0.25, 0.65]

  - id: silent_data_corruption
    name: "The Silent Killer"
    difficulty: extreme
    description: "Pipeline succeeds but data is garbage — NULL detection, no error signal"
    max_steps: 18
    target_score_range: [0.10, 0.45]

observation_space:
  type: object
  fields:
    - incident_id
    - task_id
    - pipeline_name
    - failed_task
    - error_message
    - dag_task_statuses
    - sla_breach
    - sla_time_remaining_seconds
    - active_incidents
    - deployment_history
    - source_schema
    - target_schema
    - dependency_map
    - row_counts
    - log_details
    - resource_metrics
    - data_profile
    - incident_history
    - steps_remaining
    - last_action_result
    - actions_taken

action_space:
  type: enum
  categories:
    diagnostic:
      - inspect_logs
      - check_schema
      - check_dependencies
      - check_resource_utilization
      - profile_data
    remediation:
      - alter_table
      - scale_up_executor
      - rollback_deployment
      - fix_pipeline_config
    operational:
      - trigger_rerun
      - notify_stakeholder
      - skip_task

tags:
  - openenv
  - data-engineering
  - incident-response
  - pipeline-debugging
  - rl-environment
  - data-quality
```

---

## 16. Dockerfile Spec

From official `meta-pytorch/OpenEnv/envs/README.md` — the correct pattern:

```dockerfile
ARG BASE_IMAGE=openenv-base:latest
FROM ${BASE_IMAGE}

# Install dependencies
COPY server/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

# Copy environment code
COPY . /app/env/

# Health check — official pattern
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run server
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### server/requirements.txt (Docker only)

```
openenv-core>=0.1.0
fastapi>=0.110.0
uvicorn>=0.29.0
pydantic>=2.0.0
python-dotenv>=1.0.0
```

### Build Command (MUST run from inside package folder)

```bash
# From inside oncall_hero/ package — NOT from repo root
cd oncall_hero

# Official way
openenv build -t oncall-hero:latest

# OR Docker directly — . gives pyproject.toml access
docker build -t oncall-hero:latest -f server/Dockerfile .
```

---

## 17. Delivery Plan

### Time Estimate by Component

| Component | Hours |
|---|---|
| models.py | 6.5 |
| server/oncall_hero_environment.py | 9.5 |
| task_easy.py | 3.5 |
| task_medium.py | 4.5 |
| task_hard.py | 11.5 |
| task_extreme.py | 8.0 |
| graders.py | 10.5 |
| rewards.py | 4.5 |
| inference.py | 6.0 |
| openenv.yaml + Docker | 3.75 |
| HF Space deployment | 4.0 |
| README.md | 3.0 |
| Testing + validation | 13.0 |
| **Total** | **~88 hrs** |

**3 people × 6 days × ~5 hrs/day = 90 hrs — tight but feasible.**

### 7-Day Sprint

| Date | Tasks | Owner | Done When |
|---|---|---|---|
| **Apr 2** | PRD v3.0 finalized, repo scaffolded, inference.py placeholder created | All | Scaffold running locally |
| **Apr 3** | models.py, server/oncall_hero_environment.py, task_easy.py, Easy grader | Dev | Task 1 runs end-to-end locally |
| **Apr 4** | task_medium.py, task_hard.py, Medium + Hard graders, rewards.py | Dev | Tasks 1–3 graders score in [0.0, 1.0] |
| **Apr 5** | task_extreme.py, Extreme grader, full integration test, openenv validate | Dev | All tasks pass, validate passes |
| **Apr 6** | inference.py full implementation, end-to-end LLM run, verify log format | Dev | Inference under 20 min, correct logs |
| **Apr 7** | openenv push → HF Space live, README, pre-validation script | Aparna | HF Space /health returns 200 |
| **Apr 8** | Buffer for fixes. Submit before 11:59 PM IST | Aparna | Dashboard confirms submission |

### Critical Path

```
models.py → oncall_hero_environment.py → task_easy → task_medium → task_hard
    → graders.py → rewards.py → inference.py → openenv push → Submit
```

**Rule: Never start task_medium before task_easy runs end-to-end.**

### Risk Register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Task 3 takes longer than estimated | 🔴 High | Start Task 3 first thing Apr 4 morning |
| HF Space deployment fails first try | 🔴 High | Deploy Apr 6 evening not Apr 7 |
| inference.py log format wrong | 🟡 Medium | Copy exact format from sample script |
| openenv validate fails | 🟡 Medium | Run Apr 5 not Apr 7 |
| Task 4 too complex | 🟡 Medium | Simplify verification trap if time short |
| 88 hrs is tight for 3 people | 🟡 Medium | Cut Task 4 if needed — only 3 required |

---

## 18. Team Ownership

| Area | Owner | Deliverable | Deadline |
|---|---|---|---|
| Pydantic models | Dev | models.py complete | Apr 3 |
| Environment core | Dev | server/oncall_hero_environment.py reset/step/state | Apr 3 |
| Tasks 1–3 | Dev | task_easy, task_medium, task_hard | Apr 4 |
| Task 4 (bonus) | Dev | task_extreme.py | Apr 5 |
| Graders (all 4) | Dev | graders.py — deterministic, 0.0–1.0 | Apr 5 |
| Rewards | Dev | rewards.py — per-step + terminal | Apr 4 |
| Inference script | Dev | inference.py — root level, correct format | Apr 6 |
| Docker | Aparna | Dockerfile builds and runs cleanly | Apr 7 |
| HF Space | Aparna | Deployed, /health 200, reset() responds | Apr 7 |
| README | Aparna | All 7 required sections | Apr 7 |
| Pre-validation | All | Validation script passes all checks | Apr 7 |
| **Final submission** | **Aparna only** | HF Space URL + GitHub URL | **Apr 8 11:59 PM IST** |

---

## 19. Disqualification Checklist

Run through every item on Apr 7 before declaring ready.

### Automatic Disqualifiers

- [ ] HF Space does not return HTTP 200
- [ ] HF Space does not respond to reset()
- [ ] inference.py not named exactly inference.py
- [ ] inference.py not in root directory
- [ ] Log format deviates from [START]/[STEP]/[END] spec
- [ ] Inference runtime exceeds 20 minutes
- [ ] Any grader returns score outside [0.0, 1.0]
- [ ] Fewer than 3 tasks with graders
- [ ] docker build fails
- [ ] openenv validate fails

### Quality Checks

- [ ] /health endpoint returns {"status": "healthy"}
- [ ] state() returns valid JSON with all fields
- [ ] reset() produces clean state every time — no bleed between episodes
- [ ] All 12 action types handled in step() without crashing
- [ ] alter_table blocked if check_schema not called first
- [ ] trigger_rerun before fix returns error result (not crash)
- [ ] rollback to 3.1.1 in Task 3 triggers -0.40 penalty
- [ ] profile_data returns empty dict until called
- [ ] resource_metrics returns empty dict until check_resource_utilization called
- [ ] Task 4 does NOT end on first trigger_rerun — must verify data first
- [ ] openenv.yaml has spec_version: 1
- [ ] Dual import pattern in all server files
- [ ] create_fastapi_app receives CLASS not instance
- [ ] Baseline scores reproducible — run twice, same scores
- [ ] README has all 7 required sections
- [ ] inference.py uses API_BASE_URL + MODEL_NAME + HF_TOKEN env vars

---

## 20. Judging Criteria Alignment

### How We Score 97/100

| Criterion | Weight | Target | How We Achieve It |
|---|---|---|---|
| **Real-world utility** | 30% | 30/30 | Domain is exact daily work for data engineers. README quantifies pain ($M in lost productivity). Task 4 addresses silent data quality failures — hardest class of real incident that no tool trains agents for. Extensible via Task 2b for future. Explicitly differentiates from Datadog/PagerDuty. |
| **Task & grader quality** | 25% | 24/25 | 4 tasks easy → extreme with genuine difficulty progression. Every task has a unique red herring + at least 2 distinct traps. All graders deterministic with exposed sub-scores. Task 3 requires prioritization judgment. Task 4 requires proactive investigation with zero error signal — genuinely challenges frontier models. |
| **Environment design** | 20% | 19/20 | 7 evidence fields start empty — progressive disclosure. Observation vs hidden state separation. Dense per-step rewards — not just terminal. 4 done conditions. incident_history + deployment_history + active_incidents as novel mechanics. Observation base class used correctly (no redefined done/reward). |
| **Code quality & compliance** | 15% | 14/15 | openenv validate passes. spec_version: 1 in yaml. Dual import pattern throughout. create_fastapi_app with class. Docker builds cleanly. HF Space deployed. Typed models throughout. Clean repo structure matches official OpenEnv pattern. Baseline reproduces. |
| **Creativity & novelty** | 10% | 10/10 | Task 4 Silent Killer — completely unique in RL environments anywhere. incident_history memory mechanic. Progressive evidence disclosure. Deployment version reasoning (skip unsafe 3.1.1). Multi-incident triage under SLA pressure. Post-fix verification before close. |
| **Total** | **100%** | **97/100** | |

### Task Difficulty Progression

```
Task 1 Easy      ████████████████████    0.85–1.0   1 red herring, 1 fix, 6 steps
Task 2 Medium    ████████████            0.55–0.85  1 red herring, 2 fixes, ordering trap
Task 3 Hard      ██████                  0.25–0.65  4 traps, triage, version reasoning
Task 4 Extreme   ███                     0.10–0.45  no error signal, verification step
```

### Novel Mechanics Summary

| Mechanic | Tasks | Why Unique |
|---|---|---|
| incident_history | All | Agent memory of past failures — no other OpenEnv env has this |
| Progressive disclosure | All | 7 evidence fields hidden until inspected |
| Deployment version reasoning | 2, 3 | Skip unsafe version — not just rollback blindly |
| Multi-incident triage | 3 | Noisy neighbour — agent must stay focused on SLA-critical work |
| Inverted signal | 4 | Pipeline shows SUCCESS — agent investigates proactively |
| Post-fix verification | 4 | Incident not closed until data confirmed clean |

### Future Extensibility (mention in README)

- Task 2b: The Locked Vault — IAM 403 vs FileNotFoundError (saved, not built)
- Task 5: The Time Traveler — watermark/late-arriving data
- Task 6: The Phantom Load — data duplication, inverted signal

---

*PRD v3.0 — April 2, 2026*
*All 4 tasks locked. 12 actions finalized. OpenEnv patterns corrected.*
*Task 2b removed permanently.*
*Team Lead: Aparna*
*Submission Deadline: April 8, 2026 — 11:59 PM IST*
