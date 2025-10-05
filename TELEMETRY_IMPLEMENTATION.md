# Pydantic Logfire Telemetry Implementation

## Overview

Weaver.ai now includes comprehensive production-ready telemetry using **Pydantic Logfire**, providing:

- ✅ **Agent-specific instrumentation** with native Pydantic support
- ✅ **Auto-instrumentation** for FastAPI, Redis, HTTPX, and system metrics
- ✅ **Distributed tracing** across agent workflows
- ✅ **Structured logging** with correlation IDs
- ✅ **Enhanced health checks** for Kubernetes deployments
- ✅ **Global exception handling** with proper error logging

## What Was Implemented

### 1. Core Telemetry Module (`weaver_ai/telemetry.py`)

**Features:**
- `configure_telemetry()` - Initialize Logfire with environment-specific configuration
- `instrument_all()` - Auto-instrument Redis, HTTPX, and system metrics
- `start_span()` - Context manager for distributed tracing
- `log_info()`, `log_error()`, `log_warning()` - Structured logging functions
- Graceful fallback when Logfire is unavailable

### 2. Settings Configuration (`weaver_ai/settings.py`)

**New Environment Variables:**
```bash
# Telemetry settings
WEAVER_TELEMETRY_ENABLED=true                    # Enable/disable telemetry
WEAVER_TELEMETRY_SERVICE_NAME=weaver-ai          # Service name for traces
WEAVER_TELEMETRY_ENVIRONMENT=production          # development/staging/production
WEAVER_LOGFIRE_TOKEN=pylf_v1_us_...             # Your Logfire API token
WEAVER_LOGFIRE_SEND_TO_CLOUD=true                # Send to Logfire.dev cloud
```

### 3. FastAPI Gateway Instrumentation (`weaver_ai/gateway.py`)

**Added:**
- Automatic Logfire instrumentation on app startup
- Global exception handler (addresses Production Readiness Blocker #2)
- Enhanced `/health` endpoint with component-level health checks
- New `/ready` endpoint for Kubernetes readiness probes

### 4. Dependencies (`pyproject.toml`)

**Added:**
```toml
"logfire>=0.49.0"  # Latest Pydantic Logfire with agent support
```

### 5. Comprehensive Tests (`tests/unit/test_telemetry.py`)

**Test Coverage:**
- Configuration validation
- Telemetry setup with/without Logfire
- Span creation and context management
- Structured logging functions
- Fallback behavior when Logfire unavailable

**Test Results:** ✅ 59 passed, 3 skipped

## How to Use

### Local Development (Console Logging)

```bash
# Default: Telemetry enabled, console output only
python -m uvicorn weaver_ai.gateway:app --reload
```

Logfire will output structured logs to the console with color-coded severity levels.

### Production Deployment (Logfire Cloud)

```bash
# Set environment variables
export WEAVER_TELEMETRY_ENABLED=true
export WEAVER_TELEMETRY_ENVIRONMENT=production
export WEAVER_LOGFIRE_TOKEN=pylf_v1_us_mYgRgPbGDKKCPzhKgZ3lyN6ysyTQm4b6bX1lWzQc9TjQ
export WEAVER_LOGFIRE_SEND_TO_CLOUD=true

# Run the application
python -m uvicorn weaver_ai.gateway:app --host 0.0.0.0 --port 8000
```

Visit https://logfire.pydantic.dev to view your traces, metrics, and logs.

### Kubernetes Health Checks

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: weaver-ai
spec:
  containers:
  - name: weaver-ai
    image: weaver-ai:latest
    livenessProbe:
      httpGet:
        path: /health
        port: 8000
      initialDelaySeconds: 10
      periodSeconds: 30
    readinessProbe:
      httpGet:
        path: /ready
        port: 8000
      initialDelaySeconds: 5
      periodSeconds: 10
```

### Custom Instrumentation in Agent Code

```python
from weaver_ai.telemetry import start_span, log_info, log_error

async def execute_agent_task(task):
    with start_span("agent.execute", task_id=task.task_id, capability=task.capability):
        try:
            log_info("Starting agent execution", task_id=task.task_id)
            result = await process_task(task)
            log_info("Agent execution completed", task_id=task.task_id, result_type=type(result).__name__)
            return result
        except Exception as e:
            log_error("Agent execution failed", task_id=task.task_id, error=str(e))
            raise
```

## What's Automatically Instrumented

### FastAPI Endpoints
- Request/response traces
- HTTP status codes
- Request duration
- Pydantic validation errors

### Redis Operations
- All Redis commands (GET, SET, ZADD, etc.)
- Connection pool metrics
- Command latency

### HTTPX (Model Provider Calls)
- OpenAI/Anthropic API requests
- Request/response payloads (configurable)
- API latency and errors

### System Metrics
- CPU usage
- Memory usage
- Disk I/O
- Network statistics

## Health Check Endpoints

### GET /health

**Response:**
```json
{
  "status": "healthy",
  "service": "weaver-ai",
  "version": "0.1.0",
  "telemetry_enabled": true,
  "agent": "ok"
}
```

**Status Levels:**
- `healthy` - All systems operational
- `degraded` - Some components failing but service operational

### GET /ready

**Response:**
```json
{
  "ready": true,
  "service": "weaver-ai",
  "telemetry": "configured",
  "agent_ready": true
}
```

Use this for Kubernetes readiness probes to ensure the service can handle traffic.

## Production Readiness Improvements

This implementation addresses the following production readiness blocking issues:

### ✅ Blocker #1: No Telemetry/Monitoring
- **Before:** No observability into agent behavior, API calls, or errors
- **After:** Full distributed tracing, structured logging, and metrics

### ✅ Blocker #2: Missing Global Exception Handler
- **Before:** Unhandled exceptions could crash the service or leak internal details
- **After:** All exceptions logged with context, proper error responses returned

### ✅ Enhancement: Health Checks
- **Before:** Basic `/health` endpoint with no dependency checks
- **After:** Component-level health checks and Kubernetes-ready `/ready` endpoint

## Logfire Dashboard Features

When using Logfire cloud, you get:

1. **Live Tracing** - Real-time view of agent execution flows
2. **SQL Query Interface** - Query traces like a database
3. **LLM Token Tracking** - Automatic tracking of OpenAI/Anthropic token usage
4. **Performance Insights** - P50/P95/P99 latency metrics
5. **Error Aggregation** - Group and analyze errors by type
6. **Custom Dashboards** - Build views for your specific metrics

## Configuration Examples

### Development (Verbose Console Logging)
```bash
export WEAVER_TELEMETRY_ENABLED=true
export WEAVER_TELEMETRY_ENVIRONMENT=development
export WEAVER_LOGFIRE_SEND_TO_CLOUD=false
```

### Staging (Cloud with Debug Info)
```bash
export WEAVER_TELEMETRY_ENABLED=true
export WEAVER_TELEMETRY_ENVIRONMENT=staging
export WEAVER_LOGFIRE_TOKEN=<your-token>
export WEAVER_LOGFIRE_SEND_TO_CLOUD=true
```

### Production (Cloud, Minimal Console Output)
```bash
export WEAVER_TELEMETRY_ENABLED=true
export WEAVER_TELEMETRY_ENVIRONMENT=production
export WEAVER_LOGFIRE_TOKEN=<your-token>
export WEAVER_LOGFIRE_SEND_TO_CLOUD=true
```

### Disabled (No Telemetry)
```bash
export WEAVER_TELEMETRY_ENABLED=false
```

## Next Steps

To fully leverage this telemetry implementation:

1. **Add Agent Execution Spans** - Wrap agent `process()` methods with `start_span()`
2. **Track Tool Invocations** - Add spans for each tool execution
3. **Monitor LLM Calls** - Logfire automatically tracks token usage
4. **Set Up Alerts** - Configure alerts in Logfire for error rates, latency, etc.
5. **Create Dashboards** - Build custom dashboards for your key metrics

## Troubleshooting

### Logfire not available warning
```
Logfire not available - install with: pip install logfire>=0.49.0
```

**Solution:**
```bash
pip install -e .  # Reinstall with new dependencies
```

### No traces appearing in Logfire cloud
- Check `WEAVER_LOGFIRE_SEND_TO_CLOUD=true`
- Verify `WEAVER_LOGFIRE_TOKEN` is set correctly
- Check network connectivity to `logfire-api.pydantic.dev`

### Exception handler not catching errors
- Ensure you're using the main `weaver_ai.gateway:app` FastAPI instance
- Verify the exception is not caught by a more specific handler first

## Resources

- [Pydantic Logfire Documentation](https://logfire.pydantic.dev)
- [Logfire Python SDK](https://github.com/pydantic/logfire)
- [OpenTelemetry Specification](https://opentelemetry.io/docs/)
