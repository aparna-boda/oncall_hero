#!/usr/bin/env bash
chmod +x validate-submission.sh
source .venv/bin/activate
cd oncall_hero
uv run server &
SERVER_PID=$!
sleep 4
cd ..
./validate-submission.sh http://localhost:8000 ./oncall_hero
kill $SERVER_PID
