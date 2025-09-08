# Weaver AI Load Testing & Performance Baseline

This directory contains load testing tools and scripts to establish performance baselines and validate optimizations for Weaver AI.

## Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# Start all services and run baseline tests automatically
docker-compose -f docker-compose.baseline.yml --profile run-baseline up

# Or start services and access Locust web UI
docker-compose -f docker-compose.baseline.yml up

# Then navigate to http://localhost:8089 for interactive testing
```

### Option 2: Local Testing

```bash
# 1. Install dependencies
pip install -e ".[load-test]"

# 2. Start Weaver AI server
python -m weaver_ai.main --host 0.0.0.0 --port 8000

# 3. Run baseline tests
./load_tests/run_baseline.sh

# Or run specific test
locust -f load_tests/locustfile.py --host http://localhost:8000 \
       --users 50 --spawn-rate 5 --run-time 60s --headless
```

## Test Scenarios

The load tests include multiple user behavior patterns:

### 1. **Simple Query User** (60% of load)
- Asks basic questions requiring minimal processing
- Tests fundamental request/response performance
- Validates rate limiting and authentication

### 2. **Workflow User** (30% of load)
- Triggers multi-agent workflows
- Tests agent coordination and event mesh
- Validates complex processing pipelines

### 3. **Burst User** (10% of load)
- Sends rapid bursts of requests
- Tests rate limiting effectiveness
- Validates system stability under spikes

### 4. **Authentication User** (5% of load)
- Tests authentication endpoints
- Validates error handling for invalid auth
- Monitors auth performance

### 5. **Stress Test User** (5% of load)
- Sends computationally intensive queries
- Tests system limits and timeout handling
- Validates resource management

## Baseline Test Configurations

The baseline suite runs progressively increasing load tests:

| Test Name | Users | Duration | Purpose |
|-----------|-------|----------|---------|
| single_user | 1 | 30s | Single user baseline |
| light_load | 5 | 60s | Light concurrent usage |
| moderate_load | 10 | 60s | Typical usage |
| normal_load | 25 | 120s | Expected production load |
| heavy_load | 50 | 120s | Peak load handling |
| stress_test | 100 | 180s | System breaking point |

## Performance Metrics

Key metrics collected during tests:

- **Response Times**: P50, P95, P99 percentiles
- **Throughput**: Requests per second (RPS)
- **Error Rates**: Failure percentage
- **Scalability**: How RPS scales with users
- **Breaking Point**: When system degrades

## Current Performance Targets

Based on initial implementation:

| Metric | Target | Acceptable | Critical |
|--------|--------|------------|----------|
| P50 Response Time | <200ms | <500ms | >1000ms |
| P95 Response Time | <1000ms | <2000ms | >5000ms |
| P99 Response Time | <2000ms | <5000ms | >10000ms |
| Error Rate | <1% | <5% | >10% |
| Min RPS | >10 | >5 | <5 |

## Running Custom Tests

### Interactive Web UI

```bash
# Start Locust with web interface
locust -f load_tests/locustfile.py --host http://localhost:8000

# Navigate to http://localhost:8089
# Configure test parameters in the UI
```

### Command Line

```bash
# Custom test with specific parameters
locust -f load_tests/locustfile.py \
       --host http://localhost:8000 \
       --users 25 \
       --spawn-rate 5 \
       --run-time 120s \
       --headless \
       --csv results/custom_test \
       --html results/custom_test.html
```

### Distributed Testing

For testing at scale, use distributed mode:

```bash
# Start master
locust -f load_tests/locustfile.py --master

# Start workers (on same or different machines)
locust -f load_tests/locustfile.py --worker --master-host=localhost
```

## Analyzing Results

### Generated Reports

After running tests, find results in `load_tests/results/`:

- `baseline_TIMESTAMP.json` - Raw test data
- `baseline_report_TIMESTAMP.txt` - Summary report
- `TEST_NAME.html` - Interactive HTML report
- `TEST_NAME_stats.csv` - Detailed statistics

### Key Metrics to Review

1. **Latency Distribution**: Check if P95/P99 meet targets
2. **Error Patterns**: Look for specific failure types
3. **Throughput Plateau**: Identify where RPS stops scaling
4. **Resource Utilization**: Monitor CPU, memory, connections

### Interpreting Results

#### Good Performance Indicators:
- Linear RPS scaling with users
- Consistent response times under load
- Low error rates (<1%)
- Quick recovery from bursts

#### Performance Issues:
- RPS plateaus early
- Exponential latency growth
- High error rates
- Memory leaks (increasing memory over time)

## Optimization Workflow

1. **Establish Baseline**: Run full baseline suite
2. **Identify Bottlenecks**: Analyze metrics and logs
3. **Implement Fix**: Apply targeted optimization
4. **Validate**: Run tests to confirm improvement
5. **Document**: Record changes and impact

## Troubleshooting

### Common Issues

**High latency from start:**
- Check if using stub model vs real LLM
- Verify Redis connection
- Check rate limiting settings

**Errors at low load:**
- Verify authentication setup
- Check for missing dependencies
- Review error logs

**RPS not scaling:**
- Check for synchronous code blocking
- Verify connection pooling
- Monitor database/Redis performance

**Memory issues:**
- Check for memory leaks
- Verify garbage collection
- Monitor agent memory usage

## Next Steps

After establishing baseline:

1. **Connection Pooling**: Implement HTTP connection reuse
2. **Caching Layer**: Add Redis caching for responses
3. **Batch Processing**: Group similar requests
4. **Horizontal Scaling**: Test with multiple instances
5. **Kubernetes Deploy**: Test in container orchestration

## Contributing

When adding new test scenarios:

1. Add new user class in `locustfile.py`
2. Update test configurations in `run_baseline.py`
3. Document expected behavior
4. Add to CI/CD pipeline

## References

- [Locust Documentation](https://docs.locust.io/)
- [Performance Testing Best Practices](https://www.locust.io/best-practices)
- [Weaver AI Architecture](../DEVELOPMENT_PLAN.md)
