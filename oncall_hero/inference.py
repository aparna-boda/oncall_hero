# inference.py
# OnCall Hero — Baseline Inference Script
# !! DO NOT MOVE THIS FILE — must stay at repo root !!

import asyncio
import json
import os
import textwrap
from typing import List, Optional

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv() # Load variables from .env!

from oncall_hero.client import OnCallHeroEnv
from oncall_hero.models import OnCallAction

LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")
API_KEY = os.getenv("HF_TOKEN") or os.getenv("OPENAI_API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"
MODEL_NAME = os.getenv("MODEL_NAME") or "Qwen/Qwen2.5-72B-Instruct"
BENCHMARK = os.getenv("ONCALL_HERO_BENCHMARK", "oncall_hero")

TASKS = ["missing_source_file", "schema_drift_bigquery", "cascade_collapse", "silent_data_corruption"]
MAX_STEPS = 20
SUCCESS_SCORE_THRESHOLD = 0.5
MAX_TOTAL_REWARD = 1.0

SYSTEM_PROMPT = textwrap.dedent("""
    You are an AI data engineer acting as an on-call responder for data pipeline incidents.
    Your task is to resolve pipeline incidents using a specific set of tools.
    You must output a raw JSON action exactly matching the following schema. No markdown wrappers.

    {
        "action_type": "<action_type>",
        "target": "<target_pipeline_or_table>",
        "parameters": {},
        "justification": "<your reasoning>"
    }

    Valid action_types and their parameters:
    - inspect_logs          parameters: {}
    - check_schema          parameters: {}
    - check_dependencies    parameters: {}
    - check_resource_utilization  parameters: {}
    - profile_data          parameters: {}
    - alter_table           parameters: {"column": "<col_name>", "type": "<data_type>"}
                            Example: {"column": "quantity", "type": "BIGINT"}
    - scale_up_executor     parameters: {}
    - rollback_deployment   parameters: {"version": "<version_string>"}
                            Example: {"version": "3.1.0"}
    - fix_pipeline_config   parameters: {}
    - trigger_rerun         parameters: {}
    - notify_stakeholder    parameters: {"team": "<team_name>"}
                            Example: {"team": "sla_team"}
    - skip_task             parameters: {}

    Strategy guidelines:
    - Always inspect_logs FIRST before any other action.
    - For missing file / config errors: inspect_logs → fix_pipeline_config → trigger_rerun.
    - For schema mismatch errors: inspect_logs → check_schema → alter_table (once per mismatched column) → trigger_rerun.
    - For cascading pipeline failures with SLA breaches:
        1. inspect_logs (read deployment history carefully)
        2. check_dependencies (to identify SLA-critical tables and blast radius)
        3. rollback_deployment with the LAST KNOWN GOOD version from deployment history (NOT the most recent — it may have bugs)
        4. trigger_rerun once per SLA-critical table, using the exact table name as target, in the order listed in the dependency map
        5. notify_stakeholder with team="sla"
    - For silent data corruption (pipeline shows SUCCESS but SLA is breached with no error): inspect_logs → profile_data (will reveal NULL rates) → rollback_deployment to last known good version → trigger_rerun → profile_data again to verify fix → notify_stakeholder with team="revenue_team" → notify_stakeholder with team="crm_team".
    - NEVER use check_schema or alter_table for deployment/cascading failures — they are irrelevant.
    - NEVER use scale_up_executor — resource issues are always red herrings.
    - NEVER rollback_deployment without reading the deployment history in logs first.
    - NEVER trigger_rerun before fixing the root cause — it will fail again and waste steps.
    - skip_task gives a large penalty — never use it.
""").strip()


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}", flush=True)


def format_observation(obs) -> str:
    obs_dict = {k: v for k, v in obs.model_dump().items() if v}
    return json.dumps(obs_dict, indent=2)


async def run_task(task_id: str, client: OpenAI, env: OnCallHeroEnv) -> None:
    log_start(task=task_id, env=BENCHMARK, model=MODEL_NAME)

    rewards: List[float] = []
    steps_taken = 0
    score = 0.01  # default strictly > 0 in case of early exception
    success = False

    try:
        result = await env.reset(task_id=task_id)
        obs = result.observation

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"New incident alert!\nObservation:\n{format_observation(obs)}"},
        ]

        for step in range(1, MAX_STEPS + 1):
            if result.done:
                break

            steps_taken = step
            error_msg = None

            try:
                import time
                import openai
                
                max_retries = 5
                for attempt in range(max_retries):
                    try:
                        completion = client.chat.completions.create(
                            model=MODEL_NAME,
                            messages=messages,
                            temperature=0.0,
                            max_tokens=500,
                            stream=False,
                        )
                        break
                    except openai.RateLimitError as rle:
                        if attempt < max_retries - 1:
                            sleep_time = (attempt + 1) * 5
                            print(f"\\n[DEBUG] Rate limit hit! Waiting {sleep_time}s before retrying...", flush=True)
                            time.sleep(sleep_time)
                        else:
                            raise rle
                raw_response = completion.choices[0].message.content
                action_json = raw_response.replace("```json", "").replace("```", "").strip()
                action_dict = json.loads(action_json)
                action = OnCallAction(
                    action_type=action_dict["action_type"],
                    target=action_dict["target"],
                    parameters=action_dict.get("parameters", {}),
                    justification=action_dict.get("justification", ""),
                )
            except Exception as e:
                error_msg = str(e).replace("\n", " ")
                raw_response = ""
                action = OnCallAction(
                    action_type="skip_task",
                    target="unknown",
                    justification=f"Failed to parse model output: {e}",
                )

            result = await env.step(action)
            obs = result.observation
            reward = result.reward if result.reward is not None else 0.01
            reward = max(0.01, min(0.99, reward))  # strictly in (0.01, 0.99) for all steps
            done = result.done
            rewards.append(reward)

            log_step(step=step, action=action.action_type, reward=reward, done=done, error=error_msg)

            if not error_msg:
                messages.append({"role": "assistant", "content": raw_response})
                messages.append({"role": "user", "content": f"Action result & observation:\n{format_observation(obs)}"})

        if result.done:
            score = rewards[-1] if rewards else 0.01  # final grader score from environment
        else:
            score = max(rewards) if rewards else 0.01
        score = min(max(score, 0.01), 0.99)
        success = score >= SUCCESS_SCORE_THRESHOLD

    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)


async def _make_env() -> OnCallHeroEnv:
    """
    Connect to the environment.
    - If LOCAL_IMAGE_NAME is set: spin up a local Docker container.
    - Otherwise: connect directly via API_BASE_URL (HF Space or local server).
    """
    if LOCAL_IMAGE_NAME:
        return await OnCallHeroEnv.from_docker_image(LOCAL_IMAGE_NAME)
    base_url = os.getenv("ENV_BASE_URL") or "http://localhost:8000"
    return OnCallHeroEnv(base_url=base_url)


async def main() -> None:
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    for task in TASKS:
        env = await _make_env()
        try:
            await run_task(task, client, env)
        except Exception as e:
            print(f"[DEBUG] Error running task {task}: {e}", flush=True)
        finally:
            try:
                await env.close()
            except Exception as e:
                print(f"[DEBUG] env.close() error: {e}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
