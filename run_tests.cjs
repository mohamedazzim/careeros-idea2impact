const { execSync } = require('child_process');
try {
  console.log(execSync('python3 -m venv .venv', {encoding: 'utf8'}));
  console.log(execSync('.venv/bin/pip install pytest pytest-asyncio pydantic pydantic-settings fastapi pyjwt opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi prometheus-client langgraph langchain-anthropic mcp', {encoding: 'utf8'}));
  console.log(execSync('cd backend && ../.venv/bin/python -m pytest tests/observability/test_observability.py -s -v', {encoding: 'utf8'}));
} catch (e) {
  console.log(e.stdout);
  console.log(e.stderr);
}
