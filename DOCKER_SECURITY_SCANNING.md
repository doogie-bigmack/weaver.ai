# Docker Security Scanning with Docker Scout

## Overview

This guide explains how to implement Docker's built-in security scanning capabilities using **Docker Scout** for the Weaver.ai project.

## What is Docker Scout?

Docker Scout is Docker's official vulnerability scanning tool that:
- Analyzes Docker images for known CVEs
- Generates Software Bill of Materials (SBOM)
- Provides real-time security updates
- Integrates seamlessly with CI/CD pipelines
- Offers remediation suggestions

## Quick Start - Local Scanning

### 1. Install Docker Scout CLI

Docker Scout is included with Docker Desktop 4.17+ or can be installed separately:

```bash
# For Docker Desktop users - already included!

# For CLI-only users
curl -sSfL https://raw.githubusercontent.com/docker/scout-cli/main/install.sh | sh -s --

# Verify installation
docker scout version
```

### 2. Scan Your Images

```bash
# Scan the production image
docker build -t weaver:latest .
docker scout cves weaver:latest

# Scan the test image
docker build -f Dockerfile.test -t weaver-test:latest .
docker scout cves weaver-test:latest

# Filter by critical and high severity only
docker scout cves --only-severity critical,high weaver:latest

# Export results to SARIF format for GitHub Security
docker scout cves --format sarif --output weaver-scout-report.sarif weaver:latest
```

### 3. Understand the Output

Docker Scout provides:
- **Package Inventory**: All packages in your image
- **CVE Details**: Specific vulnerabilities found
- **Severity Levels**: Critical, High, Medium, Low
- **Fix Recommendations**: Upgrade paths to patched versions
- **EPSS Scores**: Exploit prediction probability

Example output:
```
✓ Image stored for indexing
✓ Indexed 152 packages
✓ No vulnerable packages detected

  Target   │  weaver:latest       │    0C     0H     0M     0L
    digest │  abc123...           │
```

## CI/CD Integration

### Option 1: GitHub Actions (Recommended)

Add this to `.github/workflows/docker-security.yml`:

```yaml
name: Docker Security Scan

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]
  schedule:
    # Run weekly on Mondays at 9 AM UTC
    - cron: '0 9 * * 1'

permissions:
  contents: read
  security-events: write  # For uploading SARIF results
  pull-requests: write     # For PR comments

jobs:
  docker-scout:
    name: Docker Scout Vulnerability Scan
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Docker Hub (optional, for Scout features)
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}

      - name: Build production image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./Dockerfile
          tags: weaver:${{ github.sha }}
          load: true
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Build test image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./Dockerfile.test
          tags: weaver-test:${{ github.sha }}
          load: true
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Docker Scout scan - Production Image
        uses: docker/scout-action@v1
        with:
          command: cves
          image: weaver:${{ github.sha }}
          only-severities: critical,high
          sarif-file: weaver-scout-production.sarif
          exit-code: true  # Fail if vulnerabilities found

      - name: Docker Scout scan - Test Image
        uses: docker/scout-action@v1
        with:
          command: cves
          image: weaver-test:${{ github.sha }}
          only-severities: critical,high
          sarif-file: weaver-scout-test.sarif
          exit-code: false  # Don't fail on test image vulnerabilities

      - name: Upload SARIF results to GitHub Security
        uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: weaver-scout-production.sarif
          category: docker-scout-production

      - name: Upload test SARIF results
        uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: weaver-scout-test.sarif
          category: docker-scout-test

      - name: Comment PR with scan results
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const sarif = JSON.parse(fs.readFileSync('weaver-scout-production.sarif', 'utf8'));
            const results = sarif.runs[0].results || [];

            const critical = results.filter(r => r.level === 'error').length;
            const high = results.filter(r => r.level === 'warning').length;
            const medium = results.filter(r => r.level === 'note').length;

            const comment = `## 🔒 Docker Security Scan Results

            **Production Image**: \`weaver:${{ github.sha }}\`

            | Severity | Count |
            |----------|-------|
            | 🔴 Critical | ${critical} |
            | 🟠 High | ${high} |
            | 🟡 Medium | ${medium} |

            ${critical + high > 0 ? '⚠️ **Action Required**: Critical or High severity vulnerabilities detected!' : '✅ **All Clear**: No critical or high severity vulnerabilities found!'}

            [View detailed results in Security tab](https://github.com/${{ github.repository }}/security/code-scanning)
            `;

            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: comment
            });
```

### Option 2: Add to Existing CI Pipeline

Update `.github/workflows/ci.yml` to add Docker Scout scanning:

```yaml
  docker-security:
    name: Docker Security Scan
    runs-on: ubuntu-latest
    needs: [docker-build]

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build image for scanning
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./Dockerfile
          tags: weaver:scan
          load: true

      - name: Scan with Docker Scout
        run: |
          docker scout cves \
            --format sarif \
            --output docker-scout.sarif \
            --only-severity critical,high \
            --exit-code \
            weaver:scan

      - name: Upload SARIF to GitHub Security
        uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: docker-scout.sarif
```

### Option 3: Simple CLI Integration

Add to your existing docker-build job:

```yaml
      - name: Scan Docker image
        run: |
          docker scout cves weaver:ci --exit-code --only-severity critical,high
```

## Local Development Workflow

### Pre-Push Security Check

Create a script `scripts/docker-security-check.sh`:

```bash
#!/bin/bash
set -e

echo "🔍 Building images..."
docker build -t weaver:local .
docker build -f Dockerfile.test -t weaver-test:local .

echo ""
echo "🔒 Scanning production image..."
docker scout cves weaver:local --only-severity critical,high

echo ""
echo "🔒 Scanning test image..."
docker scout cves weaver-test:local --only-severity critical,high

echo ""
echo "✅ Security scan complete!"
```

Make it executable:
```bash
chmod +x scripts/docker-security-check.sh
```

Run before pushing:
```bash
./scripts/docker-security-check.sh
```

### Add to Pre-Commit Hook

Add to `.git/hooks/pre-push`:

```bash
#!/bin/bash

echo "Running Docker security scan..."
./scripts/docker-security-check.sh

if [ $? -ne 0 ]; then
    echo "❌ Docker security scan failed. Push aborted."
    exit 1
fi

echo "✅ Docker security scan passed."
```

## Advanced Features

### 1. Compare Images

Compare vulnerabilities between base image and your image:

```bash
docker scout compare --to python:3.12-slim weaver:latest
```

### 2. Generate SBOM

Create a Software Bill of Materials:

```bash
docker scout sbom weaver:latest --format spdx > weaver-sbom.json
```

### 3. Policy Evaluation

Define custom policies in `docker-scout.yml`:

```yaml
policies:
  - name: Vulnerability Threshold
    description: Fail if critical vulnerabilities exist
    rules:
      - max_critical_vulns: 0
      - max_high_vulns: 5

  - name: Base Image Compliance
    description: Ensure base image is up to date
    rules:
      - base_image_updated_within: 30d

  - name: Security Hardening
    description: Container security best practices
    rules:
      - run_as_non_root: true
      - no_new_privileges: true
```

Evaluate policy:
```bash
docker scout policy evaluate weaver:latest
```

### 4. Continuous Monitoring

Enable Docker Scout in Docker Hub for continuous monitoring:

```bash
# Enroll your organization
docker scout enroll YOUR_ORG_NAME

# Enable for repository
docker scout repo enable --org YOUR_ORG_NAME YOUR_ORG_NAME/weaver
```

Benefits:
- Real-time vulnerability updates
- Automatic rescanning when new CVEs are discovered
- Dashboard view of all images
- Email notifications for new vulnerabilities

## Best Practices

### 1. Scan Frequency

- **Every build**: Scan in CI/CD pipeline
- **Weekly scheduled scans**: Catch newly disclosed CVEs
- **Before deployment**: Final gate before production
- **After base image updates**: Verify improvements

### 2. Severity Thresholds

Recommended thresholds:

| Environment | Block on | Warn on |
|-------------|----------|---------|
| Development | None | High+ |
| Staging | Critical | High |
| Production | Critical, High | Medium |

### 3. Remediation Workflow

1. **Identify**: Docker Scout finds vulnerability
2. **Assess**: Check EPSS score and exploitability
3. **Prioritize**: Critical → High → Medium → Low
4. **Fix**: Update packages or base image
5. **Verify**: Rescan to confirm fix
6. **Document**: Record remediation in SBOM

### 4. Integration with Other Tools

Docker Scout complements existing security tools:

```yaml
# Combine with Trivy for comparison
- name: Trivy scan
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: weaver:latest

- name: Docker Scout scan
  uses: docker/scout-action@v1
  with:
    image: weaver:latest
```

## Troubleshooting

### Authentication Issues

```bash
# Login to Docker Hub
docker login

# Or use token
echo $DOCKER_TOKEN | docker login -u $DOCKER_USERNAME --password-stdin
```

### Rate Limiting

Docker Scout Free tier limits:
- 3 repositories
- Unlimited scans

Upgrade to Pro for:
- Unlimited repositories
- Advanced policies
- Priority support

### False Positives

Suppress specific CVEs in `.scoutignore`:

```
# Ignore CVE-2024-12345 (false positive - vendor confirmed not exploitable)
CVE-2024-12345

# Ignore npm audit issues in test dependencies
npm:*:dev
```

## Current Status for Weaver.ai

### Baseline Scan Results

Run initial scan to establish baseline:

```bash
docker build -t weaver:baseline .
docker scout cves weaver:baseline > baseline-scan.txt
```

Expected results after our Python 3.12 fixes:
- ✅ Reduced attack surface with non-root user
- ✅ Smaller image = fewer packages = fewer vulnerabilities
- ✅ No test dependencies in production image
- ✅ Python 3.12 base image with latest security patches

### Next Steps

1. **Add GitHub Actions workflow** (recommended: separate file)
2. **Run baseline scan** and document results
3. **Set severity thresholds** based on risk tolerance
4. **Enable scheduled scans** weekly
5. **Configure PR comments** for visibility
6. **Integrate with GitHub Security** tab

## Comparison: Docker Scout vs Trivy

| Feature | Docker Scout | Trivy |
|---------|--------------|-------|
| **Provider** | Docker Official | Aqua Security |
| **SBOM** | ✅ Yes | ✅ Yes |
| **CVE Database** | Docker maintained | Trivy DB |
| **CI/CD** | ✅ GitHub Action | ✅ GitHub Action |
| **Pricing** | Free (3 repos) | Free (unlimited) |
| **Integration** | Deep Docker Hub | Standalone |
| **Real-time Updates** | ✅ Yes | Manual rescan |
| **Policy Engine** | ✅ Yes | Limited |
| **License Scanning** | ✅ Yes | ✅ Yes |

**Recommendation**: Use both!
- Docker Scout for Docker Hub integration and continuous monitoring
- Trivy for comprehensive standalone scanning

## Resources

- [Docker Scout Documentation](https://docs.docker.com/scout/)
- [Docker Scout CLI Reference](https://docs.docker.com/reference/cli/docker/scout/)
- [Docker Scout GitHub Action](https://github.com/docker/scout-action)
- [SARIF Format Specification](https://sarifweb.azurewebsites.net/)
- [CVE Database](https://cve.mitre.org/)

## Example Commands Reference

```bash
# Basic scanning
docker scout cves weaver:latest
docker scout cves --only-severity critical,high weaver:latest
docker scout cves --format json weaver:latest > scan-results.json

# Advanced analysis
docker scout compare --to python:3.12-slim weaver:latest
docker scout recommendations weaver:latest
docker scout sbom weaver:latest

# CI/CD integration
docker scout cves --exit-code --only-severity critical weaver:latest
docker scout cves --format sarif --output report.sarif weaver:latest

# Policy evaluation
docker scout policy evaluate weaver:latest

# Repository management
docker scout repo enable --org myorg myorg/weaver
docker scout repo list
```

---

**Generated**: 2025-01-14
**Last Updated**: Based on Docker Scout 1.4+ capabilities
