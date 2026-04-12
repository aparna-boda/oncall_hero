# OnCall Hero 🦸‍♂️

An OpenEnv environment that simulates production data pipeline incidents. AI agents act as an on-call data engineer — receiving alerts, reading error logs, inspecting table metadata, diagnosing root causes, and applying remediation actions to resolve incidents under pressure.

## Motivation
Every data engineering team operates under fire handling broken pipelines, cascading DAG failures, and silent data quality corruptions. Existing LLM evaluators like SWE-Bench test whether an AI can write code, but very few test if an AI can debug complex production systems, differentiate signals from noise (red herrings), and properly sequence rollbacks and dataset reconstitutions. 

OnCall Hero tackles this gap. It provides dense, step-by-step rewards for logical investigation, punishes AI agents that randomly "guess" fixes without looking at the logs, and trains models to understand deployment branching constraints and downstream Service Level Agreement (SLA) timers.

---

## Task Overview

The environment ships with 4 progressively harder incident tasks. Each task contains programmatic, deterministic graders mapping to a `[0.01, 0.99]` curve.

| Task ID | Diff | Description | Baseline (Llama-3.3-70B) |
|---------|----------|-------------|----------|
| `missing_source_file` | **Easy** | Filename convention mismatch leading to FileNotFoundError. Includes a slow-query distractor warning. Agent must update the pipeline config. | 0.950 |
| `schema_drift_bigquery` | **Medium** | Upstream tables underwent silent column drops and type drifts. Agent must dodge a decoy code deployment to correctly run two `alter_table` commands. | 0.500 |
| `cascade_collapse` | **Hard** | A bad `JOIN` deployed in version `3.1.2` corrupts a master table, cascading into 3 downstream SLA breaches. Agent must rollback selectively to `3.1.0` (avoiding the toxic `3.1.1` NULL bug variant) and orchestrate sequential reruns while ignoring a noisy neighbor OOM crash. | 0.500 |
| `silent_data_corruption` | **Extreme** | The pipeline reports a green `SUCCESS` flag, but upstream APIs dropped `price` variables to 52% NULLs. No literal error occurs. The agent must proactively profile data metrics and apply fixes before verifying. | 0.950 |

---

## Environment Spaces

### Action Space
There are 12 strictly validated logical tools available to the AI via JSON outputs:
*   **Diagnostic:** `inspect_logs`, `check_schema`, `check_dependencies`, `check_resource_utilization`, `profile_data`
*   **Remediation:** `alter_table`, `scale_up_executor`, `rollback_deployment`, `fix_pipeline_config`
*   **Operational:** `trigger_rerun`, `notify_stakeholder`, `skip_task` 

### Observation Space
Data is progressively disclosed! The environment starts natively blank, and variables expand based on the agent's sleuthing:
*   `incident_id`, `pipeline_name`, `error_message`, `dag_task_statuses` (Base)
*   `deployment_history` (Revealed post-log inspect)
*   `source_schema`, `dependency_map`, `resource_metrics`, `data_profile` (Revealed during diagnostic probes)
*   `incident_history` (Historical memory context for the pipeline)

### Reward Function
We utilize a **Dense Reward Logic**. Scores aren't just given at the end. Sub-points are awarded (`+0.05`) for effectively checking logs before guessing. Massive penalties (`-0.40`) apply for blindly forcing reruns on broken codebase branches or taking destructive actions like jumping to the toxic `3.1.1` branch in Task 3. We cap everything cleanly bounded to `[0.01, 0.99]`.

---

## Setup & Usage 

### 1. Local Validation & Inference execution
```bash
# Set your LLM API key (HuggingFace or OpenAI-compatible)
export HF_TOKEN="your-hf-token"
# Or use Groq (fast, generous free tier):
export OPENAI_API_KEY="your-groq-key"
export API_BASE_URL="https://api.groq.com/openai/v1"
export MODEL_NAME="llama-3.3-70b-versatile"

# Validate the environment spec
cd oncall_hero && openenv validate

# Build the Docker image
openenv build -t oncall-hero:latest

# Run the baseline inference
cd .. && LOCAL_IMAGE_NAME=oncall-hero:latest python inference.py
```

### 2. Local server (no Docker)
```bash
cd oncall_hero && uv run server
# Server runs at http://localhost:8000
```

### 3. Hugging Face Spaces Deploy
```bash
cd oncall_hero && openenv push
```
