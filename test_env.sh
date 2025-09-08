#!/bin/bash

# Set environment variables for testing
export WEAVER_MODEL_PROVIDER=stub
export WEAVER_AUTH_MODE=api_key
export WEAVER_ALLOWED_API_KEYS='["test-key"]'
export WEAVER_RATELIMIT_RPS=100
export WEAVER_RATELIMIT_BURST=200

# Start the service
python3 -m weaver_ai.main --host 0.0.0.0 --port 8006