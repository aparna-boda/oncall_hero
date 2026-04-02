# oncall_hero
An OpenEnv environment that simulates a production data pipeline incident. An AI agent will act as an on-call data engineer — it receives alerts, reads error logs, inspects table metadata, diagnoses the root cause, and takes the correct remediation action.

## Quick Start Commands
Always run these commands from inside the inner `oncall_hero/` package folder!

### 1. Local Development Mode
```bash
cd oncall_hero
uv run server
```
*(Starts the FastAPI server locally on `http://localhost:8000`. You can prefix it with `ENABLE_WEB_INTERFACE=true` to get a visual web testing UI!)*

### 2. Docker Build Mode
```bash
cd oncall_hero
openenv build -t oncall-hero:latest
```
*(Packages your environment into a standalone Docker container locally so you can ensure it works flawlessly before deploying)*

### 3. Deployment Mode
```bash
cd oncall_hero
openenv push
```
*(Deploys your application directly to your Hugging Face space so it becomes live on the internet!)*
