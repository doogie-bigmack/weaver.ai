#!/usr/bin/env python3
"""Validate GitHub Actions CI/CD configuration."""

import sys
from pathlib import Path

import yaml


def validate_workflow(file_path: Path) -> bool:
    """Validate a single workflow file."""
    try:
        with open(file_path) as f:
            content = f.read()
            workflow = yaml.safe_load(content)
        
        # Check required fields
        if 'name' not in workflow:
            print(f"❌ {file_path.name}: Missing 'name' field")
            return False
        
        if 'on' not in workflow:
            print(f"❌ {file_path.name}: Missing 'on' trigger")
            return False
        
        if 'jobs' not in workflow:
            print(f"❌ {file_path.name}: Missing 'jobs' field")
            return False
        
        # Validate jobs
        for job_name, job in workflow['jobs'].items():
            if 'runs-on' not in job:
                print(f"❌ {file_path.name}: Job '{job_name}' missing 'runs-on'")
                return False
            
            if 'steps' not in job:
                print(f"❌ {file_path.name}: Job '{job_name}' missing 'steps'")
                return False
        
        print(f"✅ {file_path.name}: Valid workflow - {workflow['name']}")
        return True
    
    except yaml.YAMLError as e:
        print(f"❌ {file_path.name}: Invalid YAML - {e}")
        return False
    except Exception as e:
        print(f"❌ {file_path.name}: Error - {e}")
        return False


def main():
    """Validate all GitHub Actions workflows."""
    workflows_dir = Path(".github/workflows")
    
    if not workflows_dir.exists():
        print("❌ No .github/workflows directory found")
        return 1
    
    workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
    
    if not workflow_files:
        print("❌ No workflow files found")
        return 1
    
    print(f"\n🔍 Validating {len(workflow_files)} workflow files...\n")
    
    all_valid = True
    for workflow_file in sorted(workflow_files):
        if not validate_workflow(workflow_file):
            all_valid = False
    
    # Validate Dependabot config
    dependabot_file = Path(".github/dependabot.yml")
    if dependabot_file.exists():
        try:
            with open(dependabot_file) as f:
                dependabot = yaml.safe_load(f)
            if 'version' in dependabot and 'updates' in dependabot:
                print("✅ dependabot.yml: Valid configuration")
            else:
                print("❌ dependabot.yml: Invalid configuration")
                all_valid = False
        except Exception as e:
            print(f"❌ dependabot.yml: Error - {e}")
            all_valid = False
    
    print("\n" + "="*50)
    if all_valid:
        print("✅ All CI/CD configurations are valid!")
        print("\n📋 Next steps:")
        print("1. Push to GitHub: git push origin CI-CD")
        print("2. Create a PR to merge into main")
        print("3. Workflows will automatically run")
        print("4. Check GitHub Actions tab for results")
        return 0
    else:
        print("❌ Some configurations have issues")
        return 1


if __name__ == "__main__":
    sys.exit(main())