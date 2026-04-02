---
title: OnCall Hero Simulator
emoji: 🚨
colorFrom: red
colorTo: green
sdk: docker
pinned: false
app_port: 8000
base_path: /web
tags:
  - openenv
  - data-engineering
  - incident-response
---

# OnCall Hero 🦸‍♀️👨‍💻

**An RL training ground for AI agents that debug broken data pipelines.**

Existing tools like Datadog alert you that a pipeline failed. They do not teach an AI how to reason about *why* it failed. OnCall Hero provides the reward signal needed to train agents that can autonomously diagnose and fix incidents — not just detect them. No existing OpenEnv environment targets data pipeline incident response. Our Task 4 introduces silent data corruption — a category of incident that no current benchmark evaluates at all.

## The Scenario

Every data engineering team has experienced this: a 2 AM alert fires, a critical pipeline is broken, an SLA is about to breach, and an engineer must rapidly diagnose whether the root cause is a missing file, a schema change, a bad deployment, or something entirely different — then apply the right fix in the right order without breaking anything else.

This environment simulates production data pipeline incidents. An AI agent acts as an on-call data engineer interacting with failing data pipelines through a structured OpenEnv `step()` / `reset()` / `state()` API.

## Tasks & Challenges

1. **The Missing File (Easy):** Filename convention mismatch — FileNotFoundError with distractor.
2. **The Double Drift (Medium):** Two simultaneous schema changes + deployment red herring.
3. **The Cascade Collapse (Hard):** Bad JOIN cascades to 12 tables — partial rollback required under SLA priority pressure.
4. **The Silent Killer (Extreme):** Pipeline succeeds but data is garbage — NULL detection, no error signal.

## Available Actions

Agents can perform 12 distinct data engineering actions to solve these incidents:
- **Diagnostic:** `inspect_logs`, `check_schema`, `check_dependencies`, `check_resource_utilization`, `profile_data`
- **Remediation:** `alter_table`, `scale_up_executor`, `rollback_deployment`, `fix_pipeline_config`
- **Operational:** `trigger_rerun`, `notify_stakeholder`, `skip_task`

*(Note: The full environment spec and validation tools are tracked separately before final submission.)*
