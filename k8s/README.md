# Weaver.ai Kubernetes Deployment Guide

## Overview

This directory contains production-ready Kubernetes manifests for deploying Weaver.ai across multiple cloud providers (AWS, GCP, Azure) and environments (development, staging, production).

**Architecture Highlights:**
- ✅ Multi-cloud compatible (AWS, GCP, Azure)
- ✅ Horizontal Pod Autoscaling (3-50 replicas)
- ✅ Redis StatefulSet with Sentinel for HA
- ✅ Logfire telemetry integration
- ✅ Zero-downtime rolling updates
- ✅ Security hardening (non-root, read-only filesystem)

## Directory Structure

```
k8s/
├── base/                              # Cloud-agnostic base manifests
│   ├── namespace.yaml
│   ├── gateway/                       # Weaver AI FastAPI service
│   │   ├── deployment.yaml           # Main application deployment
│   │   ├── service.yaml              # ClusterIP service
│   │   ├── hpa.yaml                  # Horizontal Pod Autoscaler
│   │   ├── configmap.yaml            # Configuration
│   │   └── pdb.yaml                  # Pod Disruption Budget
│   ├── redis/                         # Redis event mesh
│   │   ├── statefulset.yaml          # Redis StatefulSet
│   │   ├── service.yaml              # Headless service
│   │   ├── configmap.yaml            # Redis config
│   │   └── sentinel-deployment.yaml  # Sentinel for HA
│   └── ingress/
│       └── ingress.yaml               # Ingress for external access
│
├── cloud-providers/                   # Cloud-specific configurations
│   ├── aws/                           # AWS EKS setup
│   │   ├── storageclass.yaml         # EBS CSI StorageClass
│   │   ├── ingress-patch.yaml        # ALB Ingress annotations
│   │   └── kustomization.yaml
│   ├── gcp/                           # GCP GKE setup
│   │   ├── storageclass.yaml         # GCE PD StorageClass
│   │   ├── ingress-patch.yaml        # GCE Ingress annotations
│   │   └── kustomization.yaml
│   └── azure/                         # Azure AKS setup
│       ├── storageclass.yaml         # Azure Disk StorageClass
│       ├── ingress-patch.yaml        # App Gateway annotations
│       └── kustomization.yaml
│
├── environments/                      # Environment-specific configs
│   ├── development/                   # Dev environment (1 replica, stub model)
│   ├── staging/                       # Staging environment
│   └── production/                    # Production environment (5-50 replicas)
│
├── clients/                           # Per-client deployments
│   └── example-client-aws/           # Example: ACME Corp on AWS
│       └── kustomization.yaml        # Client-specific config
│
└── README.md                          # This file
```

## Prerequisites

### Required Tools

```bash
# kubectl (Kubernetes CLI)
kubectl version --client

# kustomize (built into kubectl >= 1.14)
kubectl kustomize --help

# Optional: kubens for namespace switching
brew install kubectx  # macOS
```

### Cloud Provider Setup

#### AWS EKS
```bash
# Install AWS CLI and configure
aws configure

# Install eksctl
brew install eksctl  # macOS

# Create EKS cluster
eksctl create cluster --name weaver-ai --region us-east-1 --nodes 3 --node-type t3.xlarge

# Install AWS Load Balancer Controller
kubectl apply -k "github.com/aws/eks-charts/stable/aws-load-balancer-controller//crds?ref=master"
```

#### GCP GKE
```bash
# Install gcloud CLI
curl https://sdk.cloud.google.com | bash

# Create GKE cluster
gcloud container clusters create weaver-ai \
  --zone us-central1-a \
  --num-nodes 3 \
  --machine-type n1-standard-4
```

#### Azure AKS
```bash
# Install Azure CLI
brew install azure-cli  # macOS

# Create AKS cluster
az aks create \
  --resource-group weaver-ai-rg \
  --name weaver-ai \
  --node-count 3 \
  --node-vm-size Standard_D4s_v3
```

## Quick Start

### 1. Build Docker Image

```bash
# Build image
docker build -t weaver-ai:latest .

# Tag for your registry (replace with your registry)
docker tag weaver-ai:latest your-registry/weaver-ai:v1.0.0

# Push to registry
docker push your-registry/weaver-ai:v1.0.0
```

### 2. Create Secrets

Before deploying, create a secrets file with your credentials:

```bash
# Create secrets file (DO NOT commit this!)
cat > k8s/clients/your-client/secrets.env <<EOF
model-api-key=sk-your-openai-key
logfire-token=pylf_v1_us_your-logfire-token
allowed-api-keys=your-api-key-1,your-api-key-2
EOF
```

### 3. Deploy to Kubernetes

#### Development Deployment (Local Testing)

```bash
# Apply base + development environment
kubectl apply -k k8s/environments/development/

# Check status
kubectl get pods -n weaver-ai-dev

# Follow logs
kubectl logs -f -n weaver-ai-dev deployment/weaver-ai-gateway-dev
```

#### Production Deployment (Client-Specific)

```bash
# Deploy to AWS for ACME Corp
kubectl apply -k k8s/clients/example-client-aws/

# Check deployment status
kubectl get all -n weaver-ai-acme

# Check ingress
kubectl get ingress -n weaver-ai-acme

# Follow logs
kubectl logs -f -n weaver-ai-acme deployment/weaver-ai-gateway-acme-prod
```

## Configuration

### Environment Variables

All configuration is managed via ConfigMaps and Secrets. Key settings:

**ConfigMap (k8s/base/gateway/configmap.yaml):**
```yaml
WEAVER_MODEL_PROVIDER: "openai"           # Model provider
WEAVER_MODEL_NAME: "gpt-4o"               # Model name
WEAVER_TELEMETRY_SERVICE_NAME: "weaver-ai" # Service name for traces
WEAVER_TELEMETRY_ENVIRONMENT: "production" # Environment
WEAVER_LOGFIRE_SEND_TO_CLOUD: "true"      # Send traces to Logfire
WEAVER_AUTH_MODE: "api_key"               # Authentication mode
WEAVER_RATELIMIT_RPS: "10"                # Requests per second
WEAVER_RATELIMIT_BURST: "20"              # Burst limit
WEAVER_PII_REDACT: "true"                 # Enable PII redaction
```

**Secrets (created per client):**
```yaml
model-api-key: <OpenAI/Anthropic API key>
logfire-token: <Pydantic Logfire token>
allowed-api-keys: <comma-separated list of allowed API keys>
jwt-public-key: <RSA public key for JWT validation>
```

### Scaling Configuration

**Horizontal Pod Autoscaler (HPA):**
```yaml
spec:
  minReplicas: 3              # Minimum pods (development: 1, production: 5)
  maxReplicas: 20             # Maximum pods (production: 50)
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        averageUtilization: 70    # Scale up at 70% CPU
  - type: Resource
    resource:
      name: memory
      target:
        averageUtilization: 80    # Scale up at 80% memory
```

**Resource Requests/Limits:**
```yaml
# Development
resources:
  requests:
    cpu: 500m
    memory: 1Gi
  limits:
    cpu: 2000m
    memory: 4Gi

# Production (higher limits)
resources:
  requests:
    cpu: 1000m
    memory: 2Gi
  limits:
    cpu: 4000m
    memory: 8Gi
```

## Redis Configuration

### StatefulSet Architecture

```
redis-0 (master)  ← Primary write node
redis-1 (replica) ← Read replica
redis-2 (replica) ← Read replica

3 Sentinel pods monitor for failures
Automatic failover if master dies
```

### Redis Configuration Tuning

Key settings in `k8s/base/redis/configmap.yaml`:

```conf
maxmemory 3gb                      # 3GB limit (4GB pod - 1GB for OS)
maxmemory-policy allkeys-lru       # Evict least recently used keys
appendonly yes                     # Persistence enabled
appendfsync everysec               # Fsync every second (balanced)
client-output-buffer-limit pubsub 32mb 8mb 60  # Prevent slow subscribers from blocking
```

### When to Migrate to Managed Redis

Consider migrating to managed Redis (ElastiCache/Memorystore/Azure Cache) when:
- Memory usage consistently >75%
- Need >5 Redis replicas
- Client traffic >1000 req/sec sustained
- Ops team spending >5 hours/week on Redis maintenance

**Migration is simple:** Just change `REDIS_URL` environment variable in deployment.yaml.

## Health Checks

### Liveness Probe
Kubernetes restarts pod if this fails 3 times:
```yaml
livenessProbe:
  httpGet:
    path: /health              # Basic health check
  failureThreshold: 3          # Restart after 3 failures
  periodSeconds: 30            # Check every 30 seconds
```

### Readiness Probe
Kubernetes removes pod from service if this fails:
```yaml
readinessProbe:
  httpGet:
    path: /ready               # Checks dependencies (Redis)
  failureThreshold: 2          # Remove from LB after 2 failures
  periodSeconds: 10            # Check every 10 seconds
```

## Monitoring & Observability

### Logfire Integration

Weaver.ai is pre-configured with Pydantic Logfire for observability:

1. **Get Logfire Token:**
   ```bash
   # Already provided: pylf_v1_us_mYgRgPbGDKKCPzhKgZ3lyN6ysyTQm4b6bX1lWzQc9TjQ
   ```

2. **Enable in ConfigMap:**
   ```yaml
   WEAVER_TELEMETRY_ENABLED: "true"
   WEAVER_LOGFIRE_SEND_TO_CLOUD: "true"
   ```

3. **View Traces:**
   Visit https://logfire.pydantic.dev to see:
   - Request traces
   - LLM token usage
   - Agent execution flows
   - Error rates

### Kubernetes Metrics

```bash
# View pod resource usage
kubectl top pods -n weaver-ai-prod

# View node resource usage
kubectl top nodes

# Check HPA status
kubectl get hpa -n weaver-ai-prod

# View events
kubectl get events -n weaver-ai-prod --sort-by='.lastTimestamp'
```

## Common Operations

### View Logs

```bash
# Gateway logs
kubectl logs -f -n weaver-ai-prod deployment/weaver-ai-gateway-prod

# Redis logs
kubectl logs -f -n weaver-ai-prod statefulset/redis-prod

# Sentinel logs
kubectl logs -f -n weaver-ai-prod deployment/redis-sentinel-prod

# All pods with label
kubectl logs -f -n weaver-ai-prod -l app=weaver-ai-gateway
```

### Scale Manually

```bash
# Scale gateway pods
kubectl scale deployment weaver-ai-gateway-prod -n weaver-ai-prod --replicas=10

# Note: HPA will override manual scaling
```

### Rolling Update

```bash
# Update image
kubectl set image deployment/weaver-ai-gateway-prod \
  weaver-ai=your-registry/weaver-ai:v1.1.0 \
  -n weaver-ai-prod

# Check rollout status
kubectl rollout status deployment/weaver-ai-gateway-prod -n weaver-ai-prod

# View rollout history
kubectl rollout history deployment/weaver-ai-gateway-prod -n weaver-ai-prod
```

### Rollback

```bash
# Rollback to previous version
kubectl rollout undo deployment/weaver-ai-gateway-prod -n weaver-ai-prod

# Rollback to specific revision
kubectl rollout undo deployment/weaver-ai-gateway-prod -n weaver-ai-prod --to-revision=2
```

### Debug Pod Issues

```bash
# Get pod details
kubectl describe pod <pod-name> -n weaver-ai-prod

# Execute command in pod
kubectl exec -it <pod-name> -n weaver-ai-prod -- /bin/sh

# Check Redis connection from gateway pod
kubectl exec -it <gateway-pod> -n weaver-ai-prod -- \
  redis-cli -h redis-0.redis ping
```

## Client Deployment Template

To deploy for a new client:

1. **Create client directory:**
   ```bash
   mkdir -p k8s/clients/newclient-aws
   ```

2. **Create kustomization.yaml:**
   ```yaml
   apiVersion: kustomize.config.k8s.io/v1beta1
   kind: Kustomization

   namespace: weaver-ai-newclient

   bases:
     - ../../base
     - ../../cloud-providers/aws         # or gcp, azure
     - ../../environments/production     # or staging, development

   nameSuffix: -newclient

   secretGenerator:
     - name: weaver-secrets
       literals:
         - model-api-key=sk-newclient-key
         - logfire-token=pylf_v1_us_newclient-token
         - allowed-api-keys=newclient-key-1,newclient-key-2

   configMapGenerator:
     - name: weaver-config
       behavior: merge
       literals:
         - WEAVER_TELEMETRY_SERVICE_NAME=weaver-ai-newclient
         - WEAVER_RATELIMIT_RPS=30

   patchesJson6902:
   - target:
       kind: Ingress
       name: weaver-ai-ingress
     patch: |-
       - op: replace
         path: /spec/rules/0/host
         value: newclient.weaver-ai.example.com
   ```

3. **Deploy:**
   ```bash
   kubectl apply -k k8s/clients/newclient-aws/
   ```

## Troubleshooting

### Pods not starting

```bash
# Check pod status
kubectl get pods -n weaver-ai-prod

# Check events
kubectl describe pod <pod-name> -n weaver-ai-prod

# Common issues:
# - ImagePullBackOff: Wrong image name or missing registry credentials
# - CrashLoopBackOff: Application error, check logs
# - Pending: Insufficient resources or PVC not bound
```

### Redis connection errors

```bash
# Check Redis pods
kubectl get pods -n weaver-ai-prod -l app=redis

# Test Redis connection
kubectl exec -it redis-0 -n weaver-ai-prod -- redis-cli ping

# Check Sentinel status
kubectl exec -it <sentinel-pod> -n weaver-ai-prod -- \
  redis-cli -p 26379 sentinel masters
```

### HPA not scaling

```bash
# Check metrics server is installed
kubectl get deployment metrics-server -n kube-system

# Check HPA status
kubectl describe hpa weaver-gateway-hpa -n weaver-ai-prod

# If metrics unavailable, install metrics-server:
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

### Ingress not working

```bash
# Check ingress status
kubectl get ingress -n weaver-ai-prod

# Describe ingress
kubectl describe ingress weaver-ai-ingress -n weaver-ai-prod

# Check ingress controller logs (AWS ALB)
kubectl logs -n kube-system deployment/aws-load-balancer-controller
```

## Security Best Practices

1. **Secrets Management:**
   - Never commit secrets to Git
   - Use external secrets operator in production
   - Rotate secrets regularly

2. **Network Policies:**
   - Restrict pod-to-pod communication
   - Only allow gateway → Redis
   - Block external Redis access

3. **RBAC:**
   - Use service accounts with minimal permissions
   - Separate namespaces per client

4. **Image Security:**
   - Scan images for vulnerabilities
   - Use specific image tags (not `latest`)
   - Pull from private registry

## Performance Tuning

### Gateway Optimization

```yaml
# Increase replicas for high traffic
spec:
  minReplicas: 10
  maxReplicas: 100

# Increase resources
resources:
  requests:
    cpu: 2000m
    memory: 4Gi
  limits:
    cpu: 8000m
    memory: 16Gi
```

### Redis Optimization

```yaml
# Increase memory for larger workloads
resources:
  requests:
    memory: 4Gi
  limits:
    memory: 8Gi

# Update redis.conf
maxmemory 7gb
```

## Cost Optimization

1. **Right-size pods:** Start small, scale based on metrics
2. **Use spot instances:** For non-critical environments
3. **Enable cluster autoscaler:** Scale nodes with pods
4. **Set resource limits:** Prevent runaway pods
5. **Use HPA:** Scale down during off-hours

## Support

For issues or questions:
- Check logs: `kubectl logs`
- Check events: `kubectl get events`
- View Logfire dashboard: https://logfire.pydantic.dev
- Review this README

## Next Steps

1. **Deploy to development:** Test in dev environment first
2. **Monitor metrics:** Watch Logfire dashboards
3. **Load test:** Use Locust to validate scaling
4. **Optimize:** Adjust HPA and resource limits based on traffic
5. **Automate:** Set up CI/CD pipeline (GitOps with ArgoCD)
