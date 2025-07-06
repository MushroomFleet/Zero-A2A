"""
Custom exceptions for Zero-A2A
"""

from typing import Optional, Dict, Any


class ZeroA2AException(Exception):
    """Base exception for Zero-A2A"""
    
    def __init__(
        self, 
        message: str, 
        code: Optional[int] = None, 
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class ConfigurationError(ZeroA2AException):
    """Configuration related errors"""
    
    def __init__(self, message: str, config_key: Optional[str] = None):
        super().__init__(message, code=1001)
        self.config_key = config_key


class AuthenticationError(ZeroA2AException):
    """Authentication related errors"""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, code=2001)


class AuthorizationError(ZeroA2AException):
    """Authorization related errors"""
    
    def __init__(self, message: str = "Access denied"):
        super().__init__(message, code=2002)


class ValidationError(ZeroA2AException):
    """Input validation errors"""
    
    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(message, code=3001)
        self.field = field


class AgentError(ZeroA2AException):
    """Agent execution errors"""
    
    def __init__(self, message: str, agent_id: Optional[str] = None):
        super().__init__(message, code=4001)
        self.agent_id = agent_id


class TaskError(ZeroA2AException):
    """Task execution errors"""
    
    def __init__(
        self, 
        message: str, 
        task_id: Optional[str] = None, 
        state: Optional[str] = None
    ):
        super().__init__(message, code=4002)
        self.task_id = task_id
        self.state = state


class TimeoutError(ZeroA2AException):
    """Operation timeout errors"""
    
    def __init__(self, message: str = "Operation timed out", timeout_seconds: Optional[int] = None):
        super().__init__(message, code=5001)
        self.timeout_seconds = timeout_seconds


class RateLimitError(ZeroA2AException):
    """Rate limiting errors"""
    
    def __init__(self, message: str = "Rate limit exceeded", retry_after: Optional[int] = None):
        super().__init__(message, code=5002)
        self.retry_after = retry_after


class ExternalServiceError(ZeroA2AException):
    """External service integration errors"""
    
    def __init__(
        self, 
        message: str, 
        service_name: Optional[str] = None, 
        status_code: Optional[int] = None
    ):
        super().__init__(message, code=6001)
        self.service_name = service_name
        self.status_code = status_code


class DatabaseError(ZeroA2AException):
    """Database operation errors"""
    
    def __init__(self, message: str, operation: Optional[str] = None):
        super().__init__(message, code=7001)
        self.operation = operation


class CacheError(ZeroA2AException):
    """Cache operation errors"""
    
    def __init__(self, message: str, cache_key: Optional[str] = None):
        super().__init__(message, code=7002)
        self.cache_key = cache_key


class ProtocolError(ZeroA2AException):
    """A2A protocol related errors"""
    
    def __init__(self, message: str, method: Optional[str] = None):
        super().__init__(message, code=8001)
        self.method = method


class StreamingError(ZeroA2AException):
    """Streaming operation errors"""
    
    def __init__(self, message: str, stream_id: Optional[str] = None):
        super().__init__(message, code=8002)
        self.stream_id = stream_id


# JSON-RPC 2.0 Error Codes
JSONRPC_PARSE_ERROR = -32700
JSONRPC_INVALID_REQUEST = -32600
JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602
JSONRPC_INTERNAL_ERROR = -32603

# Custom A2A Error Codes (application specific)
A2A_AGENT_NOT_FOUND = -32000
A2A_TASK_NOT_FOUND = -32001
A2A_INVALID_TASK_STATE = -32002
A2A_AUTHENTICATION_REQUIRED = -32003
A2A_RATE_LIMIT_EXCEEDED = -32004
A2A_EXTERNAL_SERVICE_ERROR = -32005


def create_jsonrpc_error(code: int, message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a JSON-RPC 2.0 error object"""
    error = {
        "code": code,
        "message": message
    }
    if data:
        error["data"] = data
    return error


def exception_to_jsonrpc_error(exc: Exception) -> Dict[str, Any]:
    """Convert an exception to a JSON-RPC error object"""
    if isinstance(exc, ZeroA2AException):
        return create_jsonrpc_error(
            code=exc.code or JSONRPC_INTERNAL_ERROR,
            message=exc.message,
            data=exc.details
        )
    elif isinstance(exc, ValueError):
        return create_jsonrpc_error(
            code=JSONRPC_INVALID_PARAMS,
            message=str(exc)
        )
    else:
        return create_jsonrpc_error(
            code=JSONRPC_INTERNAL_ERROR,
            message="Internal server error"
        )
