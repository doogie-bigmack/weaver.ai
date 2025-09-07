#!/usr/bin/env python3
"""Test GitHub Actions workflows are valid."""

import os
import sys

# Change to /tmp to avoid local yaml module
os.chdir('/tmp')
sys.path = [p for p in sys.path if 'CI-CD' not in p]

import yaml  # noqa: E402

workflow_dir = '/Users/damon.mcdougald/conductor/weaver.ai/.conductor/CI-CD/.github/workflows'
workflows = ['ci.yml', 'security.yml', 'release.yml', 'pre-commit.yml']

print("Testing GitHub Actions workflows...")
print("=" * 50)

all_valid = True
for workflow_file in workflows:
    path = f"{workflow_dir}/{workflow_file}"
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
        
        if data and isinstance(data, dict):
            if 'name' in data and 'on' in data and 'jobs' in data:
                print(f"✅ {workflow_file}: Valid - {data['name']}")
            else:
                print(f"❌ {workflow_file}: Missing required fields")
                all_valid = False
        else:
            print(f"❌ {workflow_file}: Invalid YAML structure")
            all_valid = False
    except Exception as e:
        print(f"❌ {workflow_file}: Error - {e}")
        all_valid = False

print("=" * 50)
if all_valid:
    print("✅ All workflows are valid and ready to use!")
else:
    print("❌ Some workflows have issues")
    sys.exit(1)