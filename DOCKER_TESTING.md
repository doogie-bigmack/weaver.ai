# Docker Testing Setup for Weaver AI

## Overview

All tests should be run in Docker containers to ensure consistent, isolated environments. This prevents "works on my machine" issues and ensures reproducibility.

## Quick Start

### Using Make (Recommended)
```bash
# Run all tests
make test

# Run the demo
make demo

# Open shell in container
make shell

# Clean up containers
make clean
```

### Using Docker Directly
```bash
# Build the test image
docker build -f Dockerfile.test -t weaver-test:latest .

# Run unit tests
docker run --rm weaver-test:latest

# Run the demo
docker run --rm weaver-test:latest python demo_event_mesh.py

# Open interactive shell
docker run --rm -it weaver-test:latest /bin/bash
```

### Using Docker Compose
```bash
# Run unit tests
docker-compose run --rm unit-tests

# Run integration tests
docker-compose run --rm integration-tests

# Run demo
docker-compose run --rm demo

# Start development environment
docker-compose run --rm dev
```

## Files

### Dockerfile.test
Minimal Docker image for testing:
- Python 3.12 slim base
- Only essential dependencies
- Fast build times
- Runs tests by default

### docker-compose.yml
Service definitions for:
- `test`: Basic test runner
- `unit-tests`: Unit test suite
- `integration-tests`: Integration tests
- `demo`: Event mesh demonstration
- `dev`: Interactive development shell
- `redis`: Redis backend (future)

### Makefile
Convenient commands:
- `make build`: Build image
- `make test`: Run tests
- `make demo`: Run demonstration
- `make shell`: Interactive shell
- `make clean`: Cleanup

## Benefits of Docker Testing

1. **Consistency**: Same environment everywhere
2. **Isolation**: No pollution of local system
3. **Reproducibility**: Tests run identically for everyone
4. **Security**: Contained execution environment
5. **CI/CD Ready**: Same containers work in pipelines

## Running Tests in CI/CD

```yaml
# GitHub Actions example
- name: Run Tests
  run: |
    docker build -f Dockerfile.test -t weaver-test .
    docker run --rm weaver-test

# GitLab CI example
test:
  script:
    - docker build -f Dockerfile.test -t weaver-test .
    - docker run --rm weaver-test
```

## Debugging in Docker

```bash
# Run with interactive debugging
docker run --rm -it weaver-test:latest python -m pytest tests/ -v --pdb

# Mount local code for live editing
docker run --rm -it \
  -v $(pwd)/weaver_ai:/app/weaver_ai \
  -v $(pwd)/tests:/app/tests \
  weaver-test:latest /bin/bash

# Check logs
docker logs <container-id>
```

## Performance

Docker adds minimal overhead:
- Build time: ~30 seconds (cached)
- Test execution: +0-2% overhead
- Memory usage: ~100MB container

## Best Practices

1. **Always test in Docker** before claiming code works
2. **Use volumes** for development to avoid rebuilds
3. **Keep images small** with multi-stage builds
4. **Cache dependencies** in separate layers
5. **Run as non-root** user in production

## Troubleshooting

### Build fails
```bash
# Clear Docker cache
docker system prune -a

# Rebuild without cache
docker build --no-cache -f Dockerfile.test -t weaver-test .
```

### Tests hang
```bash
# Add timeout to pytest
docker run --rm weaver-test:latest \
  python -m pytest tests/ --timeout=10
```

### Permission issues
```bash
# Fix ownership
docker run --rm -v $(pwd):/app weaver-test:latest \
  chown -R $(id -u):$(id -g) /app
```

## Summary

✅ **Never run Python directly on command line**
✅ **Always use Docker for testing**
✅ **Tests are reproducible and isolated**
✅ **Ready for CI/CD pipelines**

The Docker setup ensures that if tests pass in the container, they'll pass everywhere - eliminating environment-specific issues and providing confidence in the code.