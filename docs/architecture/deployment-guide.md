# Deployment Guide - Weaver AI

**Version:** 1.1.0
**Last Updated:** 2025-10-05

## Table of Contents

1. [Deployment Overview](#deployment-overview)
2. [Environment Configurations](#environment-configurations)
3. [Docker Deployment](#docker-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Infrastructure Requirements](#infrastructure-requirements)
6. [Monitoring & Observability](#monitoring--observability)
7. [Scaling Strategies](#scaling-strategies)
8. [Disaster Recovery](#disaster-recovery)
9. [Operational Runbooks](#operational-runbooks)

## Deployment Overview

### Deployment Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Load Balancer (SSL Termination)                        │
└─────────────────────────────────────────────────────────┘
                        │
                        ↓ HTTPS
┌─────────────────────────────────────────────────────────┐
│  API Gateway Tier (3+ replicas)                         │
│  - FastAPI application                                  │
│  - Stateless (can scale horizontally)                   │
│  - Health checks on /health                             │
└─────────────────────────────────────────────────────────┘
                        │
                        ↓ Internal network
┌─────────────────────────────────────────────────────────┐
│  Redis Cluster (Master + 2 Replicas)                    │
│  - Event mesh for agent communication                   │
│  - Session storage and caching                          │
│  - High availability with Sentinel                      │
└─────────────────────────────────────────────────────────┘
                        │
                        ↓ External network
┌─────────────────────────────────────────────────────────┐
│  External Services                                       │
│  - LLM Providers (OpenAI, Anthropic)                    │
│  - MCP Tool Servers                                     │
│  - OpenTelemetry Collector                              │
└─────────────────────────────────────────────────────────┘
```

### Deployment Patterns

| Pattern | Use Case | Complexity | Cost |
|---------|----------|------------|------|
| **Single Container** | Development, demos | Low | Minimal |
| **Docker Compose** | Small production, staging | Low | Low |
| **Kubernetes** | Enterprise production | High | Medium-High |
| **Serverless** | Event-driven workloads | Medium | Variable |

## Environment Configurations

### Development Environment

**Characteristics**:
- Single process, all components in one container
- Stub model provider (no API calls)
- Relaxed security (API key auth)
- Verbose logging

**Configuration** (`.env.dev`):
```bash
# Model
WEAVER_MODEL_PROVIDER=stub
WEAVER_MODEL_NAME=stub-model

# Security
WEAVER_AUTH_MODE=api_key
WEAVER_ALLOWED_API_KEYS=dev-key-123

# Rate limiting (permissive)
WEAVER_RATELIMIT_RPS=100
WEAVER_RATELIMIT_BURST=200

# Logging
LOG_LEVEL=DEBUG

# Redis (local)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# Telemetry (disabled)
WEAVER_TELEMETRY_ENABLED=false

# Signed telemetry (disabled in dev)
WEAVER_TELEMETRY_SIGNING_ENABLED=false
```

**Start Command**:
```bash
docker-compose up dev
```

### Staging Environment

**Characteristics**:
- Production-like setup, smaller scale
- Real LLM providers with test keys
- JWT authentication
- Moderate security
- Integration testing

**Configuration** (`.env.staging`):
```bash
# Model
WEAVER_MODEL_PROVIDER=openai
WEAVER_MODEL_NAME=gpt-3.5-turbo
WEAVER_MODEL_API_KEY=${OPENAI_API_KEY_STAGING}

# Security
WEAVER_AUTH_MODE=jwt
WEAVER_JWT_PUBLIC_KEY=${JWT_PUBLIC_KEY_STAGING}
WEAVER_PII_REDACT=true

# Rate limiting
WEAVER_RATELIMIT_RPS=10
WEAVER_RATELIMIT_BURST=20

# Redis (managed)
REDIS_HOST=redis-staging.example.com
REDIS_PORT=6379
REDIS_PASSWORD=${REDIS_PASSWORD_STAGING}

# Telemetry
WEAVER_TELEMETRY_ENABLED=true
WEAVER_TELEMETRY_ENDPOINT=https://otel-staging.example.com

# Signed telemetry (enabled for testing)
WEAVER_TELEMETRY_SIGNING_ENABLED=true
WEAVER_TELEMETRY_SIGNING_KEY=${TELEMETRY_SIGNING_KEY_STAGING}
WEAVER_TELEMETRY_VERIFICATION_KEY=${TELEMETRY_VERIFICATION_KEY_STAGING}
```

### Production Environment

**Characteristics**:
- High availability (3+ replicas)
- Enterprise LLM providers
- Strict security controls
- Comprehensive monitoring
- Audit logging enabled

**Configuration** (`.env.production`):
```bash
# Model
WEAVER_MODEL_PROVIDER=openai
WEAVER_MODEL_NAME=gpt-4
WEAVER_MODEL_API_KEY=${OPENAI_API_KEY_PROD}

# Security
WEAVER_AUTH_MODE=jwt
WEAVER_JWT_PUBLIC_KEY=${JWT_PUBLIC_KEY_PROD}
WEAVER_PII_REDACT=true
WEAVER_AUDIT_PATH=/var/log/weaver/audit.log

# Rate limiting (strict)
WEAVER_RATELIMIT_RPS=5
WEAVER_RATELIMIT_BURST=10

# Request limits
WEAVER_REQUEST_MAX_TOKENS=4096
WEAVER_REQUEST_TIMEOUT_MS=25000

# Redis (cluster)
REDIS_HOST=redis-prod-cluster.example.com
REDIS_PORT=6379
REDIS_PASSWORD=${REDIS_PASSWORD_PROD}
REDIS_DB=0

# Telemetry
WEAVER_TELEMETRY_ENABLED=true
WEAVER_TELEMETRY_ENDPOINT=https://otel-prod.example.com

# Signed telemetry (REQUIRED for production compliance)
WEAVER_TELEMETRY_SIGNING_ENABLED=true
WEAVER_TELEMETRY_SIGNING_KEY=${TELEMETRY_SIGNING_KEY_PROD}
WEAVER_TELEMETRY_VERIFICATION_KEY=${TELEMETRY_VERIFICATION_KEY_PROD}

# Monitoring
OTEL_SERVICE_NAME=weaver-ai-prod
OTEL_SERVICE_VERSION=1.0.0
```

## Docker Deployment

### Single Container (Development)

**Dockerfile**:
```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install -e .

# Copy application
COPY weaver_ai/ weaver_ai/

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://localhost:8000/health')"

# Run application
CMD ["uvicorn", "weaver_ai.gateway:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Build and Run**:
```bash
# Build image
docker build -t weaver-ai:latest .

# Run with environment file
docker run -d \
  --name weaver-ai \
  --env-file .env.dev \
  -p 8000:8000 \
  weaver-ai:latest

# Check health
curl http://localhost:8000/health
```

### Docker Compose (Staging/Small Production)

**docker-compose.yml**:
```yaml
version: '3.8'

services:
  # API Gateway
  weaver-api:
    image: weaver-ai:${VERSION:-latest}
    deploy:
      replicas: 3
      restart_policy:
        condition: on-failure
        max_attempts: 3
    ports:
      - "8000:8000"
    env_file:
      - .env.${ENVIRONMENT:-production}
    environment:
      - REDIS_HOST=redis
      - WEAVER_TELEMETRY_ENABLED=true
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
    depends_on:
      redis:
        condition: service_healthy
    networks:
      - weaver-network
    volumes:
      - audit-logs:/var/log/weaver

  # Redis (High Availability)
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
    volumes:
      - redis-data:/data
    networks:
      - weaver-network

  # Redis Replica 1
  redis-replica-1:
    image: redis:7-alpine
    command: redis-server --replicaof redis 6379 --requirepass ${REDIS_PASSWORD}
    depends_on:
      - redis
    networks:
      - weaver-network

  # OpenTelemetry Collector
  otel-collector:
    image: otel/opentelemetry-collector:latest
    command: ["--config=/etc/otel-config.yaml"]
    ports:
      - "4317:4317"  # OTLP gRPC
      - "4318:4318"  # OTLP HTTP
    volumes:
      - ./otel-config.yaml:/etc/otel-config.yaml
    networks:
      - weaver-network

networks:
  weaver-network:
    driver: bridge

volumes:
  redis-data:
  audit-logs:
```

**Deploy with Docker Compose**:
```bash
# Set environment
export ENVIRONMENT=production
export VERSION=1.0.0

# Pull latest images
docker-compose pull

# Start services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f weaver-api

# Scale API tier
docker-compose up -d --scale weaver-api=5
```

## Kubernetes Deployment

### Prerequisites

- Kubernetes cluster (1.28+)
- kubectl configured
- Helm 3.x (optional, for Redis)
- Secrets management (Sealed Secrets, External Secrets, or Vault)

### Namespace Setup

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: weaver-ai
  labels:
    name: weaver-ai
    environment: production
```

### ConfigMap

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: weaver-config
  namespace: weaver-ai
data:
  WEAVER_MODEL_PROVIDER: "openai"
  WEAVER_MODEL_NAME: "gpt-4"
  WEAVER_AUTH_MODE: "jwt"
  WEAVER_PII_REDACT: "true"
  WEAVER_RATELIMIT_RPS: "5"
  WEAVER_RATELIMIT_BURST: "10"
  WEAVER_TELEMETRY_ENABLED: "true"
  REDIS_HOST: "redis-master.weaver-ai.svc.cluster.local"
  REDIS_PORT: "6379"
  LOG_LEVEL: "INFO"
```

### Secrets

```yaml
# secret.yaml (use Sealed Secrets or External Secrets in production)
apiVersion: v1
kind: Secret
metadata:
  name: weaver-secrets
  namespace: weaver-ai
type: Opaque
stringData:
  WEAVER_MODEL_API_KEY: "sk-proj-xxx"
  WEAVER_JWT_PUBLIC_KEY: |
    -----BEGIN PUBLIC KEY-----
    MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
    -----END PUBLIC KEY-----
  REDIS_PASSWORD: "<your-redis-password>"
```

### Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: weaver-api
  namespace: weaver-ai
  labels:
    app: weaver-api
    version: v1.0.0
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: weaver-api
  template:
    metadata:
      labels:
        app: weaver-api
        version: v1.0.0
    spec:
      containers:
      - name: weaver-api
        image: your-registry.com/weaver-ai:1.0.0
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8000
          name: http
          protocol: TCP
        env:
        - name: ENVIRONMENT
          value: "production"
        envFrom:
        - configMapRef:
            name: weaver-config
        - secretRef:
            name: weaver-secrets
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 2
        volumeMounts:
        - name: audit-logs
          mountPath: /var/log/weaver
      volumes:
      - name: audit-logs
        persistentVolumeClaim:
          claimName: audit-logs-pvc
```

### Service

```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: weaver-api
  namespace: weaver-ai
  labels:
    app: weaver-api
spec:
  type: ClusterIP
  ports:
  - port: 80
    targetPort: 8000
    protocol: TCP
    name: http
  selector:
    app: weaver-api
```

### Ingress

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: weaver-api
  namespace: weaver-ai
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/rate-limit: "10"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - api.weaver-ai.example.com
    secretName: weaver-tls
  rules:
  - host: api.weaver-ai.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: weaver-api
            port:
              number: 80
```

### Horizontal Pod Autoscaler

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: weaver-api
  namespace: weaver-ai
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: weaver-api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 60
```

### Redis StatefulSet

```yaml
# redis-statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis
  namespace: weaver-ai
spec:
  serviceName: redis
  replicas: 3
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        command:
        - redis-server
        - --appendonly
        - "yes"
        - --requirepass
        - $(REDIS_PASSWORD)
        env:
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: weaver-secrets
              key: REDIS_PASSWORD
        ports:
        - containerPort: 6379
          name: redis
        volumeMounts:
        - name: redis-data
          mountPath: /data
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
  volumeClaimTemplates:
  - metadata:
      name: redis-data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 10Gi
```

### Deploy to Kubernetes

```bash
# Apply all manifests
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secret.yaml
kubectl apply -f redis-statefulset.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f ingress.yaml
kubectl apply -f hpa.yaml

# Check deployment
kubectl get pods -n weaver-ai
kubectl get svc -n weaver-ai
kubectl get ingress -n weaver-ai

# View logs
kubectl logs -f deployment/weaver-api -n weaver-ai

# Scale manually
kubectl scale deployment weaver-api --replicas=5 -n weaver-ai

# Rolling update
kubectl set image deployment/weaver-api weaver-api=your-registry.com/weaver-ai:1.1.0 -n weaver-ai
kubectl rollout status deployment/weaver-api -n weaver-ai

# Rollback if needed
kubectl rollout undo deployment/weaver-api -n weaver-ai
```

## Infrastructure Requirements

### Compute Resources

| Environment | API Pods | CPU per Pod | Memory per Pod | Redis | Total CPU | Total Memory |
|-------------|----------|-------------|----------------|-------|-----------|--------------|
| **Dev** | 1 | 500m | 512Mi | 1 (256m/512Mi) | 0.75 cores | 1Gi |
| **Staging** | 2 | 1000m | 1Gi | 1 (500m/1Gi) | 2.5 cores | 3Gi |
| **Production** | 3+ | 2000m | 2Gi | 3 (1000m/2Gi) | 9+ cores | 12Gi+ |

### Storage

| Data Type | Size Estimate | Growth Rate | Backup Frequency |
|-----------|---------------|-------------|------------------|
| Redis data | 1-10GB | ~500MB/month | Daily snapshot |
| Audit logs | 100MB-1GB/month | Linear | Weekly archive |
| Docker images | 500MB per image | Per release | N/A (registry) |

### Network

- **Ingress**: 443 (HTTPS) from internet
- **API Gateway**: 8000 (internal)
- **Redis**: 6379 (internal only)
- **Telemetry**: 4317/4318 (OTLP)

### External Dependencies

| Service | SLA | Failover Strategy |
|---------|-----|-------------------|
| OpenAI API | 99.9% | Retry with exponential backoff, fallback to Anthropic |
| Anthropic API | 99.9% | Secondary LLM provider |
| Redis | 99.95% | Redis Sentinel for auto-failover |
| OpenTelemetry | 99% | Queue metrics, send when available |

## Security: RSA Key Management for Signed Telemetry

### Overview

Weaver AI supports cryptographically signed audit trails using RSA-256 signatures. This provides tamper-evident logging for compliance with GDPR, SOX, HIPAA, and PCI DSS requirements.

### Key Generation

**Generate RSA Key Pair** (2048-bit minimum, 4096-bit recommended for production):

```bash
# Generate private key for signing
openssl genrsa -out telemetry_signing_key.pem 2048

# Generate public key for verification
openssl rsa -in telemetry_signing_key.pem -pubout -out telemetry_verification_key.pem

# Verify key generation
openssl rsa -in telemetry_signing_key.pem -check -noout
# Output: RSA key ok
```

**For Production (4096-bit)**:
```bash
# Higher security for production environments
openssl genrsa -out telemetry_signing_key_prod.pem 4096
openssl rsa -in telemetry_signing_key_prod.pem -pubout -out telemetry_verification_key_prod.pem
```

### Key Storage

#### Development Environment

```bash
# Store in .env file (gitignored)
echo "WEAVER_TELEMETRY_SIGNING_KEY=$(cat telemetry_signing_key.pem)" >> .env.dev
echo "WEAVER_TELEMETRY_VERIFICATION_KEY=$(cat telemetry_verification_key.pem)" >> .env.dev
```

#### Production Environment (Kubernetes Secrets)

```bash
# Create Kubernetes secret from key files
kubectl create secret generic telemetry-signing-keys \
  --from-file=signing-key=telemetry_signing_key_prod.pem \
  --from-file=verification-key=telemetry_verification_key_prod.pem \
  --namespace=weaver-ai

# Verify secret creation
kubectl get secret telemetry-signing-keys -n weaver-ai -o yaml
```

**Secret Manifest** (alternative approach):

```yaml
# k8s/secrets-telemetry.yaml
apiVersion: v1
kind: Secret
metadata:
  name: telemetry-signing-keys
  namespace: weaver-ai
type: Opaque
stringData:
  signing-key: |
    <your-rsa-private-key-pem-content>
  verification-key: |
    <your-rsa-public-key-pem-content>
```

**Mount in Deployment**:

```yaml
# deployment.yaml (add to existing deployment)
spec:
  template:
    spec:
      containers:
      - name: weaver-api
        env:
        - name: WEAVER_TELEMETRY_SIGNING_KEY
          valueFrom:
            secretKeyRef:
              name: telemetry-signing-keys
              key: signing-key
        - name: WEAVER_TELEMETRY_VERIFICATION_KEY
          valueFrom:
            secretKeyRef:
              name: telemetry-signing-keys
              key: verification-key
```

#### Cloud Secret Managers

**AWS Secrets Manager**:

```bash
# Store private key
aws secretsmanager create-secret \
  --name weaver/telemetry/signing-key \
  --secret-string file://telemetry_signing_key_prod.pem \
  --region us-east-1

# Store public key
aws secretsmanager create-secret \
  --name weaver/telemetry/verification-key \
  --secret-string file://telemetry_verification_key_prod.pem \
  --region us-east-1

# Retrieve in application
aws secretsmanager get-secret-value \
  --secret-id weaver/telemetry/signing-key \
  --query SecretString \
  --output text
```

**HashiCorp Vault**:

```bash
# Enable KV secrets engine
vault secrets enable -path=weaver kv-v2

# Store keys
vault kv put weaver/telemetry/signing-key \
  value=@telemetry_signing_key_prod.pem

vault kv put weaver/telemetry/verification-key \
  value=@telemetry_verification_key_prod.pem

# Retrieve in application
vault kv get -field=value weaver/telemetry/signing-key
```

### Key Rotation

**Recommended Schedule**: Rotate keys quarterly (every 90 days)

**Rotation Procedure**:

```bash
# Step 1: Generate new key pair
openssl genrsa -out telemetry_signing_key_new.pem 4096
openssl rsa -in telemetry_signing_key_new.pem -pubout -out telemetry_verification_key_new.pem

# Step 2: Update production secret (with grace period)
kubectl create secret generic telemetry-signing-keys-new \
  --from-file=signing-key=telemetry_signing_key_new.pem \
  --from-file=verification-key=telemetry_verification_key_new.pem \
  --namespace=weaver-ai

# Step 3: Archive old public key for historical verification
kubectl get secret telemetry-signing-keys -n weaver-ai -o yaml > \
  backups/telemetry-keys-$(date +%Y%m%d).yaml

# Step 4: Update deployment to use new secret
kubectl patch deployment weaver-api -n weaver-ai \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"weaver-api","env":[{"name":"WEAVER_TELEMETRY_SIGNING_KEY","valueFrom":{"secretKeyRef":{"name":"telemetry-signing-keys-new","key":"signing-key"}}}]}]}}}}'

# Step 5: Monitor for 24 hours, then delete old secret
kubectl delete secret telemetry-signing-keys -n weaver-ai
kubectl get secret telemetry-signing-keys-new -n weaver-ai \
  -o yaml | sed 's/telemetry-signing-keys-new/telemetry-signing-keys/' | \
  kubectl apply -f -
```

### Key Verification

**Test Signing and Verification**:

```python
# test_signing.py
from weaver_ai.telemetry import _sign_event, verify_event_signature

# Load keys
with open('telemetry_signing_key.pem') as f:
    private_key = f.read()

with open('telemetry_verification_key.pem') as f:
    public_key = f.read()

# Create signed event
event = _sign_event(
    event_type="test_event",
    event_data={"user_id": "test@example.com", "action": "test"},
    signing_key=private_key
)

# Verify signature
is_valid = verify_event_signature(event, public_key)
print(f"Signature valid: {is_valid}")  # Should print: True

# Test tamper detection
event.data["user_id"] = "attacker@example.com"
is_valid = verify_event_signature(event, public_key)
print(f"Tampered signature valid: {is_valid}")  # Should print: False
```

### Security Best Practices

1. **Key Storage**
   - ✅ Store private keys in secure vault (AWS Secrets Manager, HashiCorp Vault, K8s Secrets)
   - ✅ Never commit keys to version control (.gitignore them)
   - ✅ Use different keys per environment (dev/staging/prod)
   - ❌ Never log or print private keys
   - ❌ Never transmit private keys over insecure channels

2. **Key Permissions**
   - Private key file permissions: `chmod 600 telemetry_signing_key.pem` (owner read/write only)
   - Public key file permissions: `chmod 644 telemetry_verification_key.pem` (world-readable)
   - Kubernetes secret RBAC: Only allow `weaver-api` service account to read

3. **Key Rotation**
   - Rotate keys quarterly (every 90 days)
   - Maintain 30-day grace period where both old and new public keys are valid for verification
   - Archive old public keys for historical event verification
   - Document rotation in change log

4. **Backup and Recovery**
   - Backup private keys in encrypted offline storage
   - Store public keys for ALL historical versions (for verification)
   - Test key recovery procedure quarterly
   - Maintain key provenance and audit trail

5. **Monitoring**
   - Alert on signature verification failures
   - Monitor signing latency (should be <100ms)
   - Track key age and alert before expiry
   - Log all key rotation events

### Compliance Checklist

Before production deployment:

- [ ] RSA keys generated with 4096-bit strength
- [ ] Private keys stored in secure vault (not in code or env files)
- [ ] Kubernetes secrets configured with proper RBAC
- [ ] Key rotation schedule documented
- [ ] Backup procedure tested
- [ ] Verification script tested successfully
- [ ] Monitoring alerts configured for signature failures
- [ ] Documentation updated with key management procedures

## Monitoring & Observability

See detailed documentation in [monitoring-guide.md](./monitoring-guide.md).

### Key Metrics

**Application**:
- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request latency (p50, p95, p99)
- `agent_execution_duration_seconds` - Agent processing time
- `llm_api_calls_total` - LLM API usage
- `tool_executions_total` - Tool usage by name

**Infrastructure**:
- `redis_connected_clients` - Redis connection count
- `redis_memory_used_bytes` - Redis memory usage
- `pod_cpu_usage` - CPU utilization per pod
- `pod_memory_usage` - Memory utilization per pod

### Alerting Rules

```yaml
# alerts.yaml
groups:
- name: weaver-ai
  interval: 30s
  rules:
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
    for: 5m
    annotations:
      summary: "High error rate detected"

  - alert: SlowRequests
    expr: histogram_quantile(0.95, http_request_duration_seconds) > 2
    for: 10m
    annotations:
      summary: "95th percentile latency > 2s"

  - alert: RedisDown
    expr: up{job="redis"} == 0
    for: 1m
    annotations:
      summary: "Redis is down"
```

## Disaster Recovery

### Backup Strategy

**Redis Data**:
```bash
# Daily snapshot
redis-cli --rdb /backup/redis-$(date +%Y%m%d).rdb

# Retention: 7 daily, 4 weekly, 12 monthly
```

**Audit Logs**:
```bash
# Weekly archive to S3
aws s3 sync /var/log/weaver/ s3://weaver-audit-logs/$(date +%Y/%m/%d)/
```

### Recovery Procedures

**API Gateway Failure**:
1. Check pod status: `kubectl get pods -n weaver-ai`
2. View logs: `kubectl logs deployment/weaver-api -n weaver-ai`
3. If crash loop: Check recent deployments, roll back if needed
4. If resource exhaustion: Scale up HPA limits

**Redis Failure**:
1. Check Redis Sentinel status
2. If master down: Sentinel auto-promotes replica
3. If cluster down: Restore from latest RDB snapshot
4. Restart API pods to reconnect

**Complete Outage**:
1. Restore Redis from backup
2. Redeploy API from latest known-good image
3. Verify health checks pass
4. Gradually restore traffic via load balancer

## Operational Runbooks

### Common Operations

**Deploy New Version**:
```bash
# 1. Build and push image
docker build -t your-registry.com/weaver-ai:$VERSION .
docker push your-registry.com/weaver-ai:$VERSION

# 2. Update K8s deployment
kubectl set image deployment/weaver-api weaver-api=your-registry.com/weaver-ai:$VERSION -n weaver-ai

# 3. Monitor rollout
kubectl rollout status deployment/weaver-api -n weaver-ai

# 4. Verify health
kubectl get pods -n weaver-ai
curl https://api.weaver-ai.example.com/health
```

**Scale for Traffic Spike**:
```bash
# Manual scale
kubectl scale deployment weaver-api --replicas=10 -n weaver-ai

# Or update HPA
kubectl patch hpa weaver-api -n weaver-ai -p '{"spec":{"maxReplicas":20}}'
```

**Rotate Secrets**:
```bash
# 1. Generate new secret
NEW_KEY=$(openssl rand -hex 32)

# 2. Update secret
kubectl patch secret weaver-secrets -n weaver-ai -p "{\"stringData\":{\"WEAVER_ALLOWED_API_KEYS\":\"$NEW_KEY\"}}"

# 3. Rolling restart to pick up new secret
kubectl rollout restart deployment/weaver-api -n weaver-ai
```

**Debug Performance Issue**:
```bash
# 1. Check metrics
kubectl top pods -n weaver-ai

# 2. View logs
kubectl logs -f deployment/weaver-api -n weaver-ai --tail=100

# 3. Profile a pod
kubectl exec -it weaver-api-xxx -n weaver-ai -- python -m cProfile app.py

# 4. Check Redis
kubectl exec -it redis-0 -n weaver-ai -- redis-cli INFO
```

## References

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Docker Documentation](https://docs.docker.com/)
- [Redis High Availability](https://redis.io/docs/management/sentinel/)
- Internal: `docs/monitoring-guide.md`
- Internal: `docs/security-architecture.md`
