# ADR-002: Redis Event Mesh for Agent Communication

**Status**: Accepted
**Date**: 2024-09-05
**Decision Makers**: Architecture Team
**Technical Story**: Multi-agent orchestration design

## Context

Weaver AI needs to support distributed multi-agent systems where agents can run in separate processes, containers, or even different machines. We needed to choose a communication mechanism that enables:

1. **Asynchronous messaging** between agents
2. **Capability-based routing** (agents subscribe to capabilities they can handle)
3. **Horizontal scaling** (add more agent instances)
4. **Low latency** for agent coordination
5. **Simplicity** for developers

### Forces at Play

1. **Performance**: Agent communication should be <10ms overhead
2. **Scalability**: Support hundreds of agents across multiple processes
3. **Reliability**: Message delivery guarantees for critical workflows
4. **Complexity**: Developers shouldn't need to be distributed systems experts
5. **Cost**: Infrastructure costs for messaging layer
6. **Operational Overhead**: Monitoring, debugging, and troubleshooting

### Requirements

- Pub/sub pattern for capability-based routing
- Work queue pattern for task distribution
- Agent discovery and heartbeat mechanism
- Support for both fire-and-forget and request-reply patterns
- Simple local development (no complex setup)

## Decision

**We will use Redis as the event mesh backbone for agent communication.**

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Redis Event Mesh (weaver_ai/redis/)                    │
├─────────────────────────────────────────────────────────┤
│  1. mesh.py - Pub/Sub channels for capability routing   │
│  2. queue.py - Work queues for task distribution        │
│  3. registry.py - Agent discovery and heartbeat         │
└─────────────────────────────────────────────────────────┘
```

### Implementation Patterns

**1. Capability-Based Pub/Sub** (`redis/mesh.py`):
```python
# Agent subscribes to capabilities
await mesh.subscribe(["capability:data_processing", "capability:analysis"])

# Agent publishes result with next capability
await mesh.publish(
    channel="capability:analysis",
    event=Event(data=result, next_capabilities=["reporting"])
)
```

**2. Work Queue** (`redis/queue.py`):
```python
# Producer pushes task
await queue.push(Task(id="123", capability="processing", data={...}))

# Consumer pulls task (blocking)
task = await queue.pull(capabilities=["processing"], timeout=30)
await queue.ack(task.id)
```

**3. Agent Registry** (`redis/registry.py`):
```python
# Agent registers itself
await registry.register(AgentInfo(
    agent_id="agent-001",
    capabilities=["data_processing"],
    status="active"
))

# Heartbeat every 10 seconds
await registry.heartbeat(agent_id="agent-001")

# Discover agents by capability
agents = await registry.discover(capability="data_processing")
```

### Redis Data Structures Used

| Pattern | Redis Structure | Key Format | TTL |
|---------|-----------------|------------|-----|
| Pub/Sub | PUBSUB | `capability:{name}` | N/A (ephemeral) |
| Work Queue | LIST | `queue:{capability}` | None |
| Agent Registry | HASH | `agent:{agent_id}` | 60s (heartbeat) |
| Memory | STRING | `memory:{agent_id}:{session}` | 1 hour |
| Cache | STRING | `cache:{key}` | Configurable |

## Consequences

### Positive

1. **Simple Setup**: Redis runs in single Docker container for dev
2. **High Performance**: Sub-millisecond pub/sub latency
3. **Battle-Tested**: Redis is proven at scale (millions of ops/sec)
4. **Low Latency**: In-memory operations, <1ms for most ops
5. **Rich Ecosystem**: Monitoring tools (RedisInsight), managed services (AWS ElastiCache)
6. **Atomic Operations**: INCR, LPUSH, etc. prevent race conditions
7. **Persistence Options**: AOF/RDB for durability if needed
8. **Horizontal Scaling**: Redis Cluster for multi-node setups

### Negative

1. **Single Point of Failure**: Redis outage stops agent communication
   - **Mitigation**: Redis Sentinel for high availability
2. **Message Loss**: Pub/sub doesn't persist messages
   - **Mitigation**: Use work queues (LIST) for critical tasks
3. **Memory Constraints**: All data in RAM
   - **Mitigation**: Set TTLs, use eviction policies
4. **Ordering Guarantees**: Pub/sub order not guaranteed across subscribers
   - **Mitigation**: Use timestamps in events
5. **Operational Overhead**: Need to monitor Redis health
   - **Mitigation**: Use managed Redis service in production

### Neutral

1. **Learning Curve**: Developers need basic Redis knowledge
2. **Infrastructure Cost**: Redis instance required (but minimal)
3. **Network Dependency**: Agents need Redis connectivity

## Alternatives Considered

### Alternative 1: RabbitMQ / Kafka

**Description**: Use a dedicated message broker

**Pros**:
- Guaranteed delivery with acks
- Complex routing patterns
- Message persistence built-in
- Industry standard for messaging

**Cons**:
- Heavy infrastructure (JVM, ZooKeeper)
- Higher operational complexity
- Slower than Redis for simple pub/sub
- Overkill for most Weaver AI use cases

**Why not chosen**: Too complex for the benefit, slower latency

### Alternative 2: gRPC Streaming

**Description**: Agents connect via gRPC bidirectional streams

**Pros**:
- Direct agent-to-agent communication
- Type-safe with Protobuf
- Built-in load balancing

**Cons**:
- Requires service discovery
- More code than pub/sub
- Harder to debug
- No built-in persistence

**Why not chosen**: Too much boilerplate, harder to debug

### Alternative 3: HTTP Webhooks

**Description**: Agents call each other via HTTP POST

**Pros**:
- Simple to understand
- Works with existing HTTP infrastructure
- Easy to test with curl

**Cons**:
- Requires agents to expose HTTP endpoints
- No built-in routing
- Higher latency than pub/sub
- Firewall/NAT issues

**Why not chosen**: Too much overhead, latency too high

### Alternative 4: In-Process Event Bus

**Description**: Python `asyncio.Queue` for single-process agents

**Pros**:
- No external dependencies
- Lowest latency
- No network overhead

**Cons**:
- Can't scale across processes
- No persistence
- Single point of failure (process crash)

**Why not chosen**: Doesn't support distributed agents

## Implementation Notes

### Redis Connection Pooling

```python
# weaver_ai/redis/mesh.py:20-30
class RedisEventMesh:
    def __init__(self, redis_url: str, pool_size: int = 10):
        self.pool = redis.ConnectionPool.from_url(
            redis_url,
            max_connections=pool_size,
            decode_responses=True
        )
        self.client = redis.Redis(connection_pool=self.pool)
        self.pubsub = self.client.pubsub()
```

### Capability Routing Logic

```python
# weaver_ai/redis/mesh.py:50-70
async def subscribe(self, capabilities: list[str]) -> None:
    """Subscribe to capability channels."""
    channels = [f"capability:{cap}" for cap in capabilities]
    await self.pubsub.subscribe(*channels)

    # Listen for messages
    async for message in self.pubsub.listen():
        if message["type"] == "message":
            event = Event.parse_raw(message["data"])
            await self._handle_event(event)
```

### Work Queue with Priority

```python
# weaver_ai/redis/queue.py:40-60
async def push(self, task: Task, priority: int = 0) -> None:
    """Push task to queue with optional priority."""
    key = f"queue:{task.capability}"

    if priority > 0:
        # High priority: left push (front of queue)
        await self.client.lpush(key, task.json())
    else:
        # Normal priority: right push (back of queue)
        await self.client.rpush(key, task.json())
```

### Heartbeat and TTL

```python
# weaver_ai/redis/registry.py:50-70
async def heartbeat(self, agent_id: str) -> None:
    """Send heartbeat to keep agent alive."""
    key = f"agent:{agent_id}"
    await self.client.expire(key, ttl=60)  # 60-second TTL

    # If agent doesn't heartbeat within 60s, it's removed automatically
```

### Local Development

```yaml
# docker-compose.yml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
```

### Production Deployment

**High Availability**:
```yaml
# Redis Sentinel for automatic failover
services:
  redis-master:
    image: redis:7-alpine
  redis-replica-1:
    image: redis:7-alpine
    command: redis-server --replicaof redis-master 6379
  redis-sentinel:
    image: redis:7-alpine
    command: redis-sentinel /etc/sentinel.conf
```

**Kubernetes**:
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis
spec:
  serviceName: redis
  replicas: 3
  template:
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
```

## Monitoring

### Key Metrics

- **Pub/sub latency**: `redis_pubsub_latency_ms` (target: <10ms)
- **Queue depth**: `redis_queue_depth` (alert if >1000)
- **Active agents**: `redis_agents_active` (from registry)
- **Memory usage**: `redis_memory_used_bytes` (alert at 80%)
- **Connection count**: `redis_connected_clients`

### Health Checks

```python
async def health_check() -> bool:
    try:
        await redis.ping()
        return True
    except redis.ConnectionError:
        return False
```

## Migration Path

If we need to migrate away from Redis in the future:

1. Create abstraction interface (`EventMesh`, `WorkQueue`, `Registry`)
2. Implement alternative backends (e.g., `KafkaEventMesh`)
3. Use adapter pattern to maintain backward compatibility
4. Gradual migration with feature flags

## References

- [Redis Pub/Sub Documentation](https://redis.io/docs/interact/pubsub/)
- [Redis Streams](https://redis.io/docs/data-types/streams/) (future consideration)
- [Redis Cluster](https://redis.io/docs/management/scaling/)
- [Redis Sentinel](https://redis.io/docs/management/sentinel/)
- Internal: `weaver_ai/redis/` implementation
