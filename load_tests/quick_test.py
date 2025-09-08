#!/usr/bin/env python3
"""Quick test to verify API is working."""

import requests

# Test with different auth approaches
host = "http://localhost:8005"

print("Testing Weaver AI endpoints...")
print("=" * 50)

# Test 1: Health check (no auth)
print("\n1. Health check:")
r = requests.get(f"{host}/health")
print(f"   Status: {r.status_code}")
print(f"   Response: {r.text}")

# Test 2: Ask with x-api-key
print("\n2. Ask with x-api-key:")
r = requests.post(
    f"{host}/ask",
    json={"query": "What is 2+2?", "user_id": "test"},
    headers={
        "Content-Type": "application/json",
        "x-api-key": "test-key",
        "x-user-id": "test-user",
    },
)
print(f"   Status: {r.status_code}")
if r.status_code == 200:
    print(f"   Response: {r.json()}")
else:
    print(f"   Error: {r.text}")

# Test 3: Ask without auth (should fail)
print("\n3. Ask without auth:")
r = requests.post(
    f"{host}/ask",
    json={"query": "What is 2+2?", "user_id": "test"},
    headers={"Content-Type": "application/json"},
)
print(f"   Status: {r.status_code}")
print(f"   Response: {r.text}")

# Test 4: Check what auth mode is configured
print("\n4. Checking container environment:")
import subprocess

result = subprocess.run(
    ["docker", "exec", "weaver-ai-simple", "env"], capture_output=True, text=True
)
for line in result.stdout.split("\n"):
    if "WEAVER" in line:
        print(f"   {line}")

print("\n" + "=" * 50)
