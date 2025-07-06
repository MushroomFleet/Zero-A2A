# Docker Deployment Plan for Zero-A2A

This document outlines the comprehensive containerization and deployment strategy for Zero-A2A, covering development, testing, and production environments.

## 1. Docker Architecture Overview

### Multi-Stage Build Strategy
- **Builder Stage**: Install dependencies and compile
- **Runtime Stage**: Minimal production image
- **Development Stage**: Full toolchain for local development

### Container Security
- Non-root user execution
- Minimal base images (Python slim)
- Security scanning integration
- Read-only root filesystem where possible

## 2. Development Dockerfile

```dockerfile
# Development Dockerfile (Dockerfile.dev)
FROM python:3.12-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create non-root user
RUN useradd --create-home --shell /bin/bash app

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip
RUN pip install -e ".[dev]"

# Copy source code
COPY . .
RUN chown -R app:app /app

USER app

# Development server with auto-reload
CMD ["python", "-m", "uvicorn", "src.server.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

## 3. Production Dockerfile

```dockerfile
# Production Dockerfile
FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir .

# Production stage
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ ./src/
COPY main.py ./

# Set ownership
RUN chown -R app:app /app

# Switch to non-root user
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Production command
CMD ["python", "main.py"]
```

## 4. Docker Compose for Development

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  zero-a2a:
    build:
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    environment:
      - DEBUG=true
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/zero_a2a
      - REDIS_URL=redis://redis:6379/0
      - JWT_SECRET_KEY=dev-secret-key
    volumes:
      - .:/app
      - /app/.venv  # Exclude venv from mount
    depends_on:
      - postgres
      - redis
    networks:
      - zero-a2a-net

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=zero_a2a
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - zero-a2a-net

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - zero-a2a-net

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
    networks:
      - zero-a2a-net

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
    networks:
      - zero-a2a-net

volumes:
  postgres_data:
  redis_data:
  grafana_data:

networks:
  zero-a2a-net:
    driver: bridge
```

## 5. Docker Compose for Production

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  zero-a2a:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DEBUG=false
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - WEATHER_API_KEY=${WEATHER_API_KEY}
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - zero-a2a-net
    depends_on:
      - postgres
      - redis

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
    depends_on:
      - zero-a2a
    networks:
      - zero-a2a-net

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=${POSTGRES_DB}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - zero-a2a-net

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    networks:
      - zero-a2a-net

volumes:
  postgres_data:
  redis_data:

networks:
  zero-a2a-net:
    external: true
```

## 6. Kubernetes Deployment

### Namespace
```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: zero-a2a
```

### ConfigMap
```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: zero-a2a-config
  namespace: zero-a2a
data:
  DEBUG: "false"
  HOST: "0.0.0.0"
  PORT: "8000"
  LOG_LEVEL: "INFO"
  ENABLE_METRICS: "true"
  ENABLE_STREAMING: "true"
```

### Secret
```yaml
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: zero-a2a-secrets
  namespace: zero-a2a
type: Opaque
data:
  JWT_SECRET_KEY: <base64-encoded-key>
  DATABASE_URL: <base64-encoded-url>
  REDIS_URL: <base64-encoded-url>
  WEATHER_API_KEY: <base64-encoded-key>
```

### Deployment
```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: zero-a2a
  namespace: zero-a2a
  labels:
    app: zero-a2a
spec:
  replicas: 3
  selector:
    matchLabels:
      app: zero-a2a
  template:
    metadata:
      labels:
        app: zero-a2a
    spec:
      containers:
      - name: zero-a2a
        image: zero-a2a:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: zero-a2a-config
        - secretRef:
            name: zero-a2a-secrets
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        securityContext:
          allowPrivilegeEscalation: false
          runAsNonRoot: true
          runAsUser: 1000
          readOnlyRootFilesystem: false  # FastAPI needs write access
          capabilities:
            drop:
            - ALL
```

### Service
```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: zero-a2a-service
  namespace: zero-a2a
spec:
  selector:
    app: zero-a2a
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

### Ingress
```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: zero-a2a-ingress
  namespace: zero-a2a
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - api.zero-a2a.com
    secretName: zero-a2a-tls
  rules:
  - host: api.zero-a2a.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: zero-a2a-service
            port:
              number: 80
```

## 7. Helm Chart Structure

```
helm/
├── Chart.yaml
├── values.yaml
├── values-dev.yaml
├── values-prod.yaml
└── templates/
    ├── deployment.yaml
    ├── service.yaml
    ├── ingress.yaml
    ├── configmap.yaml
    ├── secret.yaml
    ├── hpa.yaml
    └── _helpers.tpl
```

### Chart.yaml
```yaml
apiVersion: v2
name: zero-a2a
description: Enterprise-grade A2A Protocol implementation
version: 1.0.0
appVersion: "1.0.0"
keywords:
  - a2a
  - agent
  - protocol
  - ai
home: https://github.com/zero-a2a/zero-a2a
sources:
  - https://github.com/zero-a2a/zero-a2a
maintainers:
  - name: Zero-A2A Team
```

## 8. CI/CD Pipeline Integration

### GitHub Actions Workflow
```yaml
# .github/workflows/docker.yml
name: Docker Build and Push

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v2
    
    - name: Login to Container Registry
      uses: docker/login-action@v2
      with:
        registry: ghcr.io
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}
    
    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v4
      with:
        images: ghcr.io/${{ github.repository }}
        tags: |
          type=ref,event=branch
          type=ref,event=pr
          type=sha,prefix={{branch}}-
          type=raw,value=latest,enable={{is_default_branch}}
    
    - name: Build and push
      uses: docker/build-push-action@v4
      with:
        context: .
        push: true
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}
        cache-from: type=gha
        cache-to: type=gha,mode=max
```

## 9. Monitoring and Logging

### Prometheus Configuration
```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'zero-a2a'
    static_configs:
      - targets: ['zero-a2a:8000']
    metrics_path: '/metrics'
    scrape_interval: 5s
```

### Log Aggregation with ELK Stack
```yaml
# docker-compose.logging.yml
version: '3.8'

services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.10.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
    ports:
      - "9200:9200"
    volumes:
      - es_data:/usr/share/elasticsearch/data

  logstash:
    image: docker.elastic.co/logstash/logstash:8.10.0
    volumes:
      - ./logstash/pipeline:/usr/share/logstash/pipeline
    depends_on:
      - elasticsearch

  kibana:
    image: docker.elastic.co/kibana/kibana:8.10.0
    ports:
      - "5601:5601"
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    depends_on:
      - elasticsearch

volumes:
  es_data:
```

## 10. Security Considerations

### Container Security Scanning
```yaml
# .github/workflows/security.yml
name: Security Scan

on:
  push:
    branches: [main]
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Run Trivy vulnerability scanner
      uses: aquasecurity/trivy-action@master
      with:
        image-ref: 'zero-a2a:latest'
        format: 'sarif'
        output: 'trivy-results.sarif'
    
    - name: Upload Trivy scan results
      uses: github/codeql-action/upload-sarif@v2
      with:
        sarif_file: 'trivy-results.sarif'
```

### Secret Management
- Use Kubernetes secrets for sensitive data
- Implement secret rotation policies
- Use external secret management (Vault, AWS Secrets Manager)
- Never expose secrets in environment variables in production

## 11. Deployment Commands

### Development
```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f zero-a2a

# Stop environment
docker-compose -f docker-compose.dev.yml down
```

### Production
```bash
# Deploy to Kubernetes
kubectl apply -f k8s/

# Deploy with Helm
helm install zero-a2a ./helm -f helm/values-prod.yaml

# Update deployment
helm upgrade zero-a2a ./helm -f helm/values-prod.yaml
```

## 12. Maintenance and Operations

### Backup Strategies
- Database backups with pg_dump
- Redis persistence configuration
- Application state backup procedures

### Scaling Guidelines
- Horizontal Pod Autoscaler (HPA) configuration
- Resource limits and requests tuning
- Database connection pool optimization

### Disaster Recovery
- Multi-region deployment strategies
- Backup restoration procedures
- Failover mechanisms

This comprehensive Docker deployment plan provides enterprise-grade containerization and orchestration for Zero-A2A, covering development, testing, and production environments with proper security, monitoring, and operational considerations.
