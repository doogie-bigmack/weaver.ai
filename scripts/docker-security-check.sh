#!/bin/bash
# Docker Security Scanner using Docker Scout
# Usage: ./scripts/docker-security-check.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         Weaver.ai Docker Security Scanner                 ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if Docker Scout is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Error: Docker is not installed${NC}"
    exit 1
fi

# Check if Docker Scout CLI is available
if ! docker scout version &> /dev/null; then
    echo -e "${YELLOW}⚠️  Docker Scout CLI not found. Installing...${NC}"
    echo ""
    echo "Run this command to install Docker Scout:"
    echo "curl -sSfL https://raw.githubusercontent.com/docker/scout-cli/main/install.sh | sh -s --"
    echo ""
    echo "Or use Docker Desktop 4.17+ which includes Scout."
    exit 1
fi

# Build images
echo -e "${BLUE}🔨 Building Docker images...${NC}"
echo ""

echo "Building production image..."
docker build -t weaver:local . > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Production image built successfully${NC}"
else
    echo -e "${RED}❌ Failed to build production image${NC}"
    exit 1
fi

echo "Building test image..."
docker build -f Dockerfile.test -t weaver-test:local . > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Test image built successfully${NC}"
else
    echo -e "${RED}❌ Failed to build test image${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}🔍 Scanning Production Image${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Scan production image
docker scout cves weaver:local --only-severity critical,high
PROD_EXIT_CODE=$?

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}🔍 Scanning Test Image${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Scan test image
docker scout cves weaver-test:local --only-severity critical,high
TEST_EXIT_CODE=$?

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}📊 Summary${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

if [ $PROD_EXIT_CODE -eq 0 ] && [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ All scans passed - No critical or high vulnerabilities found!${NC}"
    echo ""
    echo "🎉 Your Docker images are secure!"
    exit 0
else
    if [ $PROD_EXIT_CODE -ne 0 ]; then
        echo -e "${RED}❌ Production image has critical or high vulnerabilities${NC}"
    fi
    if [ $TEST_EXIT_CODE -ne 0 ]; then
        echo -e "${YELLOW}⚠️  Test image has critical or high vulnerabilities${NC}"
    fi
    echo ""
    echo "📝 Next steps:"
    echo "  1. Review the vulnerabilities listed above"
    echo "  2. Update packages in Dockerfile"
    echo "  3. Consider updating base image (python:3.12-slim)"
    echo "  4. Re-run this script to verify fixes"
    echo ""
    echo "For detailed recommendations, run:"
    echo "  docker scout recommendations weaver:local"
    echo ""
    exit 1
fi
