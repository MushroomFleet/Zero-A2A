"""
Security middleware for Zero-A2A Protocol server
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import time
import structlog
from collections import defaultdict
from typing import Dict, List
import asyncio

from src.core.config import settings

logger = structlog.get_logger()


class SecurityMiddleware(BaseHTTPMiddleware):
    """Comprehensive security middleware with rate limiting and security headers"""
    
    def __init__(self, app):
        super().__init__(app)
        self.rate_limit_rpm = settings.rate_limit_rpm
        self.rate_limit_burst = settings.rate_limit_burst
        self.ip_requests: Dict[str, List[float]] = defaultdict(list)
        self.logger = logger.bind(component="security_middleware")
        
        self.logger.info(
            "Security middleware initialized",
            rate_limit_rpm=self.rate_limit_rpm,
            rate_limit_burst=self.rate_limit_burst
        )
    
    async def dispatch(self, request: Request, call_next):
        """Apply security checks to all requests"""
        start_time = time.time()
        client_ip = self._get_client_ip(request)
        
        try:
            # Rate limiting check
            if not await self._check_rate_limit(client_ip):
                self.logger.warning("Rate limit exceeded", client_ip=client_ip)
                return Response(
                    content="Rate limit exceeded. Please try again later.",
                    status_code=429,
                    headers={
                        "Retry-After": "60",
                        "X-RateLimit-Limit": str(self.rate_limit_rpm),
                        "X-RateLimit-Remaining": "0"
                    }
                )
            
            # Request size check
            if not self._check_request_size(request):
                self.logger.warning("Request too large", client_ip=client_ip)
                return Response(
                    content="Request entity too large",
                    status_code=413
                )
            
            # Process request
            response = await call_next(request)
            
            # Add security headers
            response = self._add_security_headers(response)
            
            # Log request
            duration = time.time() - start_time
            self.logger.info(
                "Request processed",
                client_ip=client_ip,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration=duration
            )
            
            return response
            
        except Exception as e:
            self.logger.error(
                "Security middleware error",
                client_ip=client_ip,
                error=str(e),
                error_type=type(e).__name__
            )
            return Response(
                content="Internal server error",
                status_code=500
            )
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        # Check for forwarded headers first (for load balancers/proxies)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        return request.client.host if request.client else "unknown"
    
    async def _check_rate_limit(self, ip: str) -> bool:
        """Check if IP has exceeded rate limit"""
        current_time = time.time()
        window_start = current_time - 60  # 1-minute window
        
        # Clean old requests
        self.ip_requests[ip] = [
            req_time for req_time in self.ip_requests[ip]
            if req_time > window_start
        ]
        
        # Check burst limit first
        recent_requests = [
            req_time for req_time in self.ip_requests[ip]
            if req_time > current_time - 10  # Last 10 seconds
        ]
        
        if len(recent_requests) >= self.rate_limit_burst:
            return False
        
        # Check per-minute limit
        if len(self.ip_requests[ip]) >= self.rate_limit_rpm:
            return False
        
        # Add current request
        self.ip_requests[ip].append(current_time)
        return True
    
    def _check_request_size(self, request: Request) -> bool:
        """Check if request size is within limits"""
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                return size <= settings.max_request_size
            except ValueError:
                return False
        return True
    
    def _add_security_headers(self, response: Response) -> Response:
        """Add security headers to response"""
        if settings.enable_security_headers:
            security_headers = {
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "X-XSS-Protection": "1; mode=block",
                "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
                "Referrer-Policy": "strict-origin-when-cross-origin",
                "Content-Security-Policy": "default-src 'self'",
                "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
            }
            
            for header, value in security_headers.items():
                response.headers[header] = value
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.rate_limit_rpm)
        
        return response


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """Optional IP whitelist middleware for admin endpoints"""
    
    def __init__(self, app, whitelist: List[str] = None, protected_paths: List[str] = None):
        super().__init__(app)
        self.whitelist = set(whitelist or [])
        self.protected_paths = protected_paths or ["/debug", "/admin"]
        self.logger = logger.bind(component="ip_whitelist_middleware")
    
    async def dispatch(self, request: Request, call_next):
        """Check IP whitelist for protected paths"""
        path = request.url.path
        
        # Check if path is protected
        is_protected = any(path.startswith(protected) for protected in self.protected_paths)
        
        if is_protected and self.whitelist:
            client_ip = self._get_client_ip(request)
            
            if client_ip not in self.whitelist:
                self.logger.warning(
                    "Access denied to protected path",
                    client_ip=client_ip,
                    path=path
                )
                return Response(
                    content="Access denied",
                    status_code=403
                )
        
        return await call_next(request)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Middleware for validating requests and preventing common attacks"""
    
    def __init__(self, app):
        super().__init__(app)
        self.logger = logger.bind(component="request_validation_middleware")
        
        # Suspicious patterns to detect
        self.suspicious_patterns = [
            "script>", "<iframe", "javascript:", "vbscript:",
            "onload=", "onerror=", "onclick=", "../../../",
            "passwd", "/etc/", "cmd.exe", "powershell"
        ]
    
    async def dispatch(self, request: Request, call_next):
        """Validate request for security threats"""
        
        # Check URL for suspicious patterns
        if self._contains_suspicious_content(str(request.url)):
            self.logger.warning(
                "Suspicious URL detected",
                url=str(request.url),
                client_ip=request.client.host if request.client else "unknown"
            )
            return Response(
                content="Bad request",
                status_code=400
            )
        
        # Check headers for suspicious content
        for header_name, header_value in request.headers.items():
            if self._contains_suspicious_content(header_value):
                self.logger.warning(
                    "Suspicious header detected",
                    header=header_name,
                    client_ip=request.client.host if request.client else "unknown"
                )
                return Response(
                    content="Bad request",
                    status_code=400
                )
        
        return await call_next(request)
    
    def _contains_suspicious_content(self, content: str) -> bool:
        """Check if content contains suspicious patterns"""
        content_lower = content.lower()
        return any(pattern in content_lower for pattern in self.suspicious_patterns)


# Background task to clean up rate limit data
async def cleanup_rate_limit_data(security_middleware: SecurityMiddleware):
    """Periodically clean up old rate limit data"""
    while True:
        try:
            current_time = time.time()
            cutoff_time = current_time - 3600  # Keep data for 1 hour
            
            # Clean up old entries
            for ip in list(security_middleware.ip_requests.keys()):
                security_middleware.ip_requests[ip] = [
                    req_time for req_time in security_middleware.ip_requests[ip]
                    if req_time > cutoff_time
                ]
                
                # Remove empty entries
                if not security_middleware.ip_requests[ip]:
                    del security_middleware.ip_requests[ip]
            
            logger.debug(
                "Rate limit data cleaned up",
                active_ips=len(security_middleware.ip_requests)
            )
            
        except Exception as e:
            logger.error("Rate limit cleanup error", error=str(e))
        
        # Wait 5 minutes before next cleanup
        await asyncio.sleep(300)
