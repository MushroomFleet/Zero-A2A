"""
Prometheus metrics middleware for Zero-A2A
"""

import time
from typing import Dict, Any
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import structlog

from src.core.config import settings

logger = structlog.get_logger()

# Define Prometheus metrics
REQUEST_COUNT = Counter(
    'zero_a2a_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_DURATION = Histogram(
    'zero_a2a_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

TASK_COUNT = Counter(
    'zero_a2a_tasks_total',
    'Total number of A2A tasks processed',
    ['agent_id', 'status']
)

TASK_DURATION = Histogram(
    'zero_a2a_task_duration_seconds',
    'A2A task processing duration in seconds',
    ['agent_id']
)

ACTIVE_CONNECTIONS = Gauge(
    'zero_a2a_active_connections',
    'Number of active HTTP connections'
)

ACTIVE_TASKS = Gauge(
    'zero_a2a_active_tasks',
    'Number of currently active A2A tasks'
)

AGENT_INFO = Info(
    'zero_a2a_agent_info',
    'Information about the A2A agent'
)

MESSAGE_COUNT = Counter(
    'zero_a2a_messages_total',
    'Total number of A2A messages processed',
    ['agent_id', 'message_type', 'direction']
)

STREAMING_EVENTS = Counter(
    'zero_a2a_streaming_events_total',
    'Total number of streaming events sent',
    ['agent_id', 'event_type']
)

CACHE_OPERATIONS = Counter(
    'zero_a2a_cache_operations_total',
    'Total number of cache operations',
    ['operation', 'status']
)

DATABASE_OPERATIONS = Counter(
    'zero_a2a_database_operations_total',
    'Total number of database operations',
    ['operation', 'status']
)

SECURITY_EVENTS = Counter(
    'zero_a2a_security_events_total',
    'Total number of security events',
    ['event_type', 'status']
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Prometheus metrics collection middleware"""
    
    def __init__(self, app):
        super().__init__(app)
        self.logger = logger.bind(component="metrics_middleware")
        
        # Initialize agent info
        AGENT_INFO.info({
            'name': settings.app_name,
            'version': settings.app_version,
            'protocol_version': '0.2.5'
        })
        
        self.logger.info("Metrics middleware initialized")
    
    async def dispatch(self, request: Request, call_next):
        """Collect metrics for HTTP requests"""
        
        if not settings.enable_metrics:
            return await call_next(request)
        
        # Skip metrics collection for metrics endpoint itself
        if request.url.path == '/metrics':
            return await call_next(request)
        
        # Extract endpoint (normalize path parameters)
        endpoint = self._normalize_endpoint(request.url.path)
        method = request.method
        
        # Start timing and track active connections
        start_time = time.time()
        ACTIVE_CONNECTIONS.inc()
        
        try:
            # Process request
            response = await call_next(request)
            
            # Record metrics
            duration = time.time() - start_time
            status_code = str(response.status_code)
            
            REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code
            ).inc()
            
            REQUEST_DURATION.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
            
            return response
            
        except Exception as e:
            # Record failed request metrics
            duration = time.time() - start_time
            
            REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status_code="500"
            ).inc()
            
            REQUEST_DURATION.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
            
            self.logger.error("Request failed in metrics middleware", error=str(e))
            raise
            
        finally:
            # Always decrement active connections
            ACTIVE_CONNECTIONS.dec()
    
    def _normalize_endpoint(self, path: str) -> str:
        """Normalize endpoint path for metrics (remove dynamic parts)"""
        # Remove query parameters
        if '?' in path:
            path = path.split('?')[0]
        
        # Normalize common patterns
        if path.startswith('/debug/'):
            return '/debug/*'
        elif path.startswith('/api/v'):
            # Handle versioned API paths
            parts = path.split('/')
            if len(parts) >= 3:
                return f"/{parts[1]}/{parts[2]}/*"
        
        return path


class TaskMetrics:
    """Metrics collector for A2A tasks"""
    
    def __init__(self):
        self.logger = logger.bind(component="task_metrics")
    
    def record_task_start(self, agent_id: str, task_id: str):
        """Record task start"""
        ACTIVE_TASKS.inc()
        self.logger.debug("Task metrics: task started", agent_id=agent_id, task_id=task_id)
    
    def record_task_completion(
        self, 
        agent_id: str, 
        task_id: str, 
        duration_seconds: float,
        success: bool,
        error_type: str = None
    ):
        """Record task completion"""
        ACTIVE_TASKS.dec()
        
        status = "success" if success else "error"
        
        TASK_COUNT.labels(
            agent_id=agent_id,
            status=status
        ).inc()
        
        TASK_DURATION.labels(
            agent_id=agent_id
        ).observe(duration_seconds)
        
        self.logger.debug(
            "Task metrics: task completed",
            agent_id=agent_id,
            task_id=task_id,
            duration_seconds=duration_seconds,
            success=success,
            error_type=error_type
        )
    
    def record_message(
        self, 
        agent_id: str, 
        message_type: str, 
        direction: str = "incoming"
    ):
        """Record A2A message processing"""
        MESSAGE_COUNT.labels(
            agent_id=agent_id,
            message_type=message_type,
            direction=direction
        ).inc()
    
    def record_streaming_event(
        self, 
        agent_id: str, 
        event_type: str
    ):
        """Record streaming event"""
        STREAMING_EVENTS.labels(
            agent_id=agent_id,
            event_type=event_type
        ).inc()


class CacheMetrics:
    """Metrics collector for cache operations"""
    
    def __init__(self):
        self.logger = logger.bind(component="cache_metrics")
    
    def record_cache_operation(self, operation: str, success: bool):
        """Record cache operation"""
        status = "success" if success else "error"
        
        CACHE_OPERATIONS.labels(
            operation=operation,
            status=status
        ).inc()
        
        self.logger.debug(
            "Cache metrics: operation recorded",
            operation=operation,
            success=success
        )


class DatabaseMetrics:
    """Metrics collector for database operations"""
    
    def __init__(self):
        self.logger = logger.bind(component="database_metrics")
    
    def record_database_operation(self, operation: str, success: bool):
        """Record database operation"""
        status = "success" if success else "error"
        
        DATABASE_OPERATIONS.labels(
            operation=operation,
            status=status
        ).inc()
        
        self.logger.debug(
            "Database metrics: operation recorded",
            operation=operation,
            success=success
        )


class SecurityMetrics:
    """Metrics collector for security events"""
    
    def __init__(self):
        self.logger = logger.bind(component="security_metrics")
    
    def record_security_event(self, event_type: str, blocked: bool = False):
        """Record security event"""
        status = "blocked" if blocked else "allowed"
        
        SECURITY_EVENTS.labels(
            event_type=event_type,
            status=status
        ).inc()
        
        self.logger.debug(
            "Security metrics: event recorded",
            event_type=event_type,
            blocked=blocked
        )


# Global metrics instances
task_metrics = TaskMetrics()
cache_metrics = CacheMetrics()
database_metrics = DatabaseMetrics()
security_metrics = SecurityMetrics()


async def get_metrics() -> Response:
    """Get Prometheus metrics"""
    try:
        if not settings.enable_metrics:
            return Response(
                content="Metrics disabled",
                status_code=404
            )
        
        # Generate metrics
        metrics_data = generate_latest()
        
        return Response(
            content=metrics_data,
            media_type=CONTENT_TYPE_LATEST,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
        
    except Exception as e:
        logger.error("Error generating metrics", error=str(e))
        return Response(
            content="Error generating metrics",
            status_code=500
        )


def record_startup_metrics():
    """Record metrics at application startup"""
    try:
        # Update agent info
        AGENT_INFO.info({
            'name': settings.app_name,
            'version': settings.app_version,
            'protocol_version': '0.2.5',
            'debug_mode': str(settings.debug),
            'metrics_enabled': str(settings.enable_metrics),
            'streaming_enabled': str(settings.enable_streaming)
        })
        
        logger.info("Startup metrics recorded")
        
    except Exception as e:
        logger.error("Error recording startup metrics", error=str(e))


def get_current_metrics_summary() -> Dict[str, Any]:
    """Get current metrics summary for health checks"""
    try:
        return {
            "active_connections": ACTIVE_CONNECTIONS._value._value,
            "active_tasks": ACTIVE_TASKS._value._value,
            "total_requests": sum(REQUEST_COUNT._metrics.values()),
            "total_tasks": sum(TASK_COUNT._metrics.values()),
            "total_messages": sum(MESSAGE_COUNT._metrics.values()),
        }
    except Exception as e:
        logger.error("Error getting metrics summary", error=str(e))
        return {
            "active_connections": 0,
            "active_tasks": 0,
            "total_requests": 0,
            "total_tasks": 0,
            "total_messages": 0,
        }
