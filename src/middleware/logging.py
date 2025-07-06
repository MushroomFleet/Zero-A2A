"""
Logging middleware and configuration for Zero-A2A
"""

import structlog
import logging
import sys
from pythonjsonlogger import jsonlogger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import time
import uuid
from typing import Dict, Any, Optional

from src.core.config import settings

# Global logger instance
logger = structlog.get_logger()


def setup_logging():
    """Configure structured logging for the application"""
    
    # Configure standard logging
    log_handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        fmt='%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d'
    )
    log_handler.setFormatter(formatter)
    
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()  # Clear existing handlers
    root_logger.addHandler(log_handler)
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    
    # Configure specific loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if settings.debug else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    logger.info(
        "Logging configured",
        log_level=settings.log_level,
        debug_mode=settings.debug
    )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses"""
    
    def __init__(self, app):
        super().__init__(app)
        self.logger = structlog.get_logger("request_logger")
    
    async def dispatch(self, request: Request, call_next):
        """Log incoming requests and outgoing responses"""
        
        # Generate request ID
        request_id = str(uuid.uuid4())
        
        # Extract client info
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "unknown")
        
        # Start timing
        start_time = time.time()
        
        # Log incoming request
        self.logger.info(
            "Request started",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query_params=str(request.query_params) if request.query_params else None,
            client_ip=client_ip,
            user_agent=user_agent,
            content_type=request.headers.get("content-type"),
            content_length=request.headers.get("content-length")
        )
        
        # Add request ID to request state
        request.state.request_id = request_id
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log response
            self.logger.info(
                "Request completed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration * 1000, 2),
                response_size=response.headers.get("content-length")
            )
            
            # Add request ID to response headers (for debugging)
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            # Calculate duration for failed requests
            duration = time.time() - start_time
            
            # Log error
            self.logger.error(
                "Request failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration * 1000, 2),
                error=str(e),
                error_type=type(e).__name__
            )
            
            # Re-raise the exception
            raise
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        # Check forwarded headers (for load balancers/proxies)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        return request.client.host if request.client else "unknown"


class TaskLoggingMiddleware:
    """Middleware for logging A2A task processing"""
    
    def __init__(self):
        self.logger = structlog.get_logger("task_logger")
    
    async def log_task_start(
        self, 
        task_id: str, 
        agent_id: str, 
        message: Dict[str, Any],
        context_id: Optional[str] = None
    ):
        """Log task start"""
        self.logger.info(
            "Task started",
            task_id=task_id,
            agent_id=agent_id,
            context_id=context_id,
            message_type=message.get("role"),
            message_parts_count=len(message.get("parts", [])) if message.get("parts") else 0
        )
    
    async def log_task_progress(
        self, 
        task_id: str, 
        agent_id: str, 
        status: str,
        message: Optional[str] = None
    ):
        """Log task progress"""
        self.logger.info(
            "Task progress",
            task_id=task_id,
            agent_id=agent_id,
            status=status,
            message=message
        )
    
    async def log_task_completion(
        self, 
        task_id: str, 
        agent_id: str, 
        duration_ms: float,
        success: bool,
        error: Optional[str] = None
    ):
        """Log task completion"""
        if success:
            self.logger.info(
                "Task completed successfully",
                task_id=task_id,
                agent_id=agent_id,
                duration_ms=round(duration_ms, 2)
            )
        else:
            self.logger.error(
                "Task failed",
                task_id=task_id,
                agent_id=agent_id,
                duration_ms=round(duration_ms, 2),
                error=error
            )
    
    async def log_streaming_event(
        self, 
        task_id: str, 
        agent_id: str, 
        event_type: str,
        event_data: Optional[Dict[str, Any]] = None
    ):
        """Log streaming events"""
        self.logger.debug(
            "Streaming event",
            task_id=task_id,
            agent_id=agent_id,
            event_type=event_type,
            event_data=event_data
        )


class ErrorLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive error logging"""
    
    def __init__(self, app):
        super().__init__(app)
        self.logger = structlog.get_logger("error_logger")
    
    async def dispatch(self, request: Request, call_next):
        """Catch and log unhandled exceptions"""
        try:
            return await call_next(request)
        except Exception as e:
            # Get request ID if available
            request_id = getattr(request.state, 'request_id', 'unknown')
            
            # Log comprehensive error information
            self.logger.error(
                "Unhandled exception",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                error=str(e),
                error_type=type(e).__name__,
                client_ip=self._get_client_ip(request)
            )
            
            # Re-raise for proper error handling
            raise
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"


class PerformanceLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging performance metrics"""
    
    def __init__(self, app, slow_request_threshold: float = 1.0):
        super().__init__(app)
        self.slow_request_threshold = slow_request_threshold
        self.logger = structlog.get_logger("performance_logger")
    
    async def dispatch(self, request: Request, call_next):
        """Log slow requests and performance metrics"""
        start_time = time.time()
        
        try:
            response = await call_next(request)
            duration = time.time() - start_time
            
            # Log slow requests
            if duration > self.slow_request_threshold:
                self.logger.warning(
                    "Slow request detected",
                    method=request.method,
                    path=request.url.path,
                    duration_seconds=round(duration, 3),
                    threshold_seconds=self.slow_request_threshold,
                    client_ip=self._get_client_ip(request)
                )
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            
            self.logger.error(
                "Request failed with exception",
                method=request.method,
                path=request.url.path,
                duration_seconds=round(duration, 3),
                error=str(e)
            )
            
            raise
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        return request.client.host if request.client else "unknown"


# Global task logger instance
task_logger = TaskLoggingMiddleware()


def get_logger(name: str = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance"""
    if name:
        return structlog.get_logger(name)
    return structlog.get_logger()


def log_agent_activity(agent_id: str, activity: str, **kwargs):
    """Log agent-specific activity"""
    agent_logger = get_logger("agent_activity")
    agent_logger.info(
        activity,
        agent_id=agent_id,
        **kwargs
    )


def log_security_event(event_type: str, client_ip: str, **kwargs):
    """Log security-related events"""
    security_logger = get_logger("security_events")
    security_logger.warning(
        event_type,
        client_ip=client_ip,
        **kwargs
    )


def log_performance_metric(metric_name: str, value: float, **kwargs):
    """Log performance metrics"""
    perf_logger = get_logger("performance_metrics")
    perf_logger.info(
        "Performance metric",
        metric_name=metric_name,
        value=value,
        **kwargs
    )
