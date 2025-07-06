"""
Enterprise FastAPI application for Zero-A2A Protocol server
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, AsyncGenerator
import structlog
from datetime import datetime
import uuid

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

from src.core.config import settings
from src.core.models import (
    AgentCard, AgentCapabilities, AgentAuthentication,
    TaskRequest, TaskResponse, Message, MessagePart, MessagePartType, MessageRole,
    JSONRPCRequest, JSONRPCResponse, JSONRPCError,
    SendMessageRequest, SendStreamingMessageRequest, MessageSendParams,
    StreamingEvent, TaskStatusUpdateEvent, TaskArtifactUpdateEvent, MessageStreamEvent
)
from src.core.exceptions import (
    AuthenticationError, ValidationError, AgentError, TaskError,
    exception_to_jsonrpc_error, JSONRPC_METHOD_NOT_FOUND, JSONRPC_INVALID_PARAMS
)
from src.core.database import initialize_database, close_database, task_repository
from src.middleware.logging import (
    setup_logging, RequestLoggingMiddleware, ErrorLoggingMiddleware, 
    PerformanceLoggingMiddleware, task_logger
)
from src.middleware.security import SecurityMiddleware, cleanup_rate_limit_data
from src.middleware.metrics import (
    MetricsMiddleware, get_metrics, record_startup_metrics, 
    get_current_metrics_summary, task_metrics
)
from src.auth.jwt_auth import jwt_auth, validate_agent_token
from src.agents.base_agent import BaseAgent, SimpleAgent
from src.agents.weather_agent import WeatherAgent
from src.utils.validators import validate_task_request, is_safe_content

# Setup logging first
setup_logging()
logger = structlog.get_logger()

# Security
security = HTTPBearer(auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Initialize variables at function scope
    cleanup_task = None
    
    # Startup
    logger.info("Zero-A2A server starting up", version=settings.app_version)
    
    try:
        # Initialize database
        try:
            await initialize_database()
            logger.info("Database initialized")
        except Exception as e:
            logger.warning("Database initialization failed, continuing without database", error=str(e))
        
        # Record startup metrics
        record_startup_metrics()
        
        # Start background tasks
        try:
            if hasattr(a2a_server, 'security_middleware'):
                cleanup_task = asyncio.create_task(
                    cleanup_rate_limit_data(a2a_server.security_middleware)
                )
        except Exception as e:
            logger.warning("Failed to start cleanup task", error=str(e))
        
        yield
        
    finally:
        # Shutdown
        logger.info("Zero-A2A server shutting down")
        
        # Cancel background tasks
        if cleanup_task:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close database connections
        try:
            await close_database()
        except Exception as e:
            logger.warning("Error closing database", error=str(e))
        
        # Clean up active tasks
        a2a_server.active_tasks.clear()


# Initialize FastAPI app with lifespan
app = FastAPI(
    title=settings.app_name,
    description="Enterprise-grade Agent-to-Agent Protocol implementation",
    version=settings.app_version,
    openapi_url="/api/v1/openapi.json" if settings.debug else None,
    lifespan=lifespan
)


class ZeroA2AServer:
    """Enterprise A2A Protocol server with Phase 2 enhancements"""
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.active_tasks: Dict[str, Any] = {}
        self.logger = logger.bind(component="a2a_server")
        
        # Initialize with default agents
        self._setup_default_agents()
        
        self.logger.info("Zero-A2A server initialized", agent_count=len(self.agents))
    
    def _setup_default_agents(self):
        """Setup default agents including WeatherAgent"""
        # Add simple hello world agent
        simple_agent = SimpleAgent(
            name="Hello World Agent",
            description="Simple agent for testing A2A protocol",
            response_text="Hello from Zero-A2A! This is a simple response from the enterprise-grade A2A Protocol implementation."
        )
        self.register_agent("default", simple_agent)
        
        # Add weather agent
        weather_agent = WeatherAgent()
        self.register_agent("weather", weather_agent)
    
    def register_agent(self, agent_id: str, agent: BaseAgent) -> None:
        """Register an agent with the server"""
        self.agents[agent_id] = agent
        self.logger.info("Agent registered", agent_id=agent_id, agent_name=agent.name)
    
    def get_agent(self, agent_id: str = "default") -> Optional[BaseAgent]:
        """Get an agent by ID"""
        return self.agents.get(agent_id)
    
    async def authenticate_request(
        self, 
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
    ) -> Optional[Dict]:
        """Authenticate incoming requests using JWT tokens (optional)"""
        if not credentials:
            # For now, allow unauthenticated access for development
            return None
        
        try:
            payload = validate_agent_token(credentials.credentials)
            self.logger.debug("Request authenticated", agent_id=payload.get("agent_id"))
            return payload
        except AuthenticationError as e:
            self.logger.warning("Authentication failed", error=str(e))
            raise HTTPException(status_code=401, detail=str(e))
    
    async def process_task(
        self, 
        task_request: TaskRequest, 
        agent_id: str = "default",
        streaming: bool = False
    ) -> Any:
        """Process A2A task with comprehensive error handling and monitoring"""
        task_id = task_request.id
        agent = self.get_agent(agent_id)
        
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        
        # Validate task request
        try:
            validate_task_request(task_request.model_dump())
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        # Security check - validate content safety
        text_content = agent.extract_text_content(task_request)
        if not is_safe_content(text_content):
            self.logger.warning("Unsafe content detected", task_id=task_id)
            raise HTTPException(status_code=400, detail="Unsafe content detected")
        
        method = "stream" if streaming else "send"
        start_time = asyncio.get_event_loop().time()
        
        # Record task start
        task_metrics.record_task_start(agent_id, task_id)
        await task_logger.log_task_start(task_id, agent_id, task_request.message.model_dump(), task_request.contextId)
        
        try:
            # Save task to database
            try:
                await task_repository.save_task(
                    task_id=task_id,
                    agent_id=agent_id,
                    message=task_request.message.model_dump(),
                    context_id=task_request.contextId,
                    task_ref_id=task_request.taskId
                )
            except Exception as e:
                self.logger.warning("Failed to save task to database", task_id=task_id, error=str(e))
            
            # Track active task
            self.active_tasks[task_id] = {
                'status': 'working',
                'agent': agent_id,
                'start_time': start_time,
                'streaming': streaming
            }
            
            if streaming:
                # Return async generator for streaming
                return self._process_streaming_task(agent, task_request, agent_id)
            else:
                # Process regular task
                result = await agent.execute_task(task_request)
                
                # Update task status in database
                try:
                    await task_repository.update_task_status(
                        task_id=task_id,
                        status="completed",
                        result=result.model_dump() if hasattr(result, 'model_dump') else result
                    )
                except Exception as e:
                    self.logger.warning("Failed to update task status in database", task_id=task_id, error=str(e))
                
                # Update task status
                self.active_tasks[task_id]['status'] = 'completed'
                
                # Record metrics
                duration = asyncio.get_event_loop().time() - start_time
                task_metrics.record_task_completion(agent_id, task_id, duration * 1000, True)
                await task_logger.log_task_completion(task_id, agent_id, duration * 1000, True)
                
                self.logger.info("Task completed", task_id=task_id, agent=agent_id, duration_ms=duration * 1000)
                return result
                
        except Exception as e:
            # Update task status
            self.active_tasks[task_id]['status'] = 'failed'
            
            # Record failure in database
            try:
                await task_repository.update_task_status(
                    task_id=task_id,
                    status="failed",
                    error_message=str(e)
                )
            except Exception as db_error:
                self.logger.warning("Failed to update failed task status in database", task_id=task_id, error=str(db_error))
            
            # Record metrics
            duration = asyncio.get_event_loop().time() - start_time
            task_metrics.record_task_completion(agent_id, task_id, duration * 1000, False, type(e).__name__)
            await task_logger.log_task_completion(task_id, agent_id, duration * 1000, False, str(e))
            
            self.logger.error("Task failed", task_id=task_id, error=str(e))
            raise
    
    async def _process_streaming_task(
        self, 
        agent: BaseAgent, 
        task_request: TaskRequest, 
        agent_id: str
    ) -> AsyncGenerator[str, None]:
        """Process streaming task and yield JSON-RPC responses"""
        task_id = task_request.id
        
        try:
            async for event in agent.execute_streaming_task(task_request):
                # Record streaming event
                task_metrics.record_streaming_event(agent_id, event.type)
                await task_logger.log_streaming_event(
                    task_id, agent_id, event.type, 
                    event.model_dump() if hasattr(event, 'model_dump') else None
                )
                
                # Create JSON-RPC response for each event
                response = JSONRPCResponse(
                    result=event,
                    id=task_request.id
                )
                
                # Yield as Server-Sent Event format
                yield f"data: {response.model_dump_json()}\n\n"
                
                # If this is the final event, break
                if getattr(event, 'final', False):
                    break
            
            # Mark task as completed
            self.active_tasks[task_id]['status'] = 'completed'
            
        except Exception as e:
            # Send error event
            error_response = JSONRPCResponse(
                error=exception_to_jsonrpc_error(e),
                id=task_request.id
            )
            yield f"data: {error_response.model_dump_json()}\n\n"
            
            self.active_tasks[task_id]['status'] = 'failed'
    
    def get_agent_card(self) -> AgentCard:
        """Get the public agent card"""
        base_url = f"http://{settings.host}:{settings.port}"
        
        # Get skills from all registered agents
        all_skills = []
        for agent in self.agents.values():
            all_skills.extend(agent.skills)
        
        return AgentCard(
            name=settings.app_name,
            description="Enterprise-grade A2A Protocol implementation with multiple agent capabilities",
            version=settings.app_version,
            url=base_url,
            capabilities=AgentCapabilities(
                streaming=settings.enable_streaming,
                pushNotifications=settings.enable_push_notifications,
                stateTransitionHistory=True,
                multiTurn=True
            ),
            authentication=AgentAuthentication(
                schemes=["bearer"],
                required=False  # Optional for development
            ),
            skills=all_skills,
            defaultInputModes=["text/plain", "application/json"],
            defaultOutputModes=["text/plain", "application/json"],
            supportsAuthenticatedExtendedCard=False
        )


# Global server instance
a2a_server = ZeroA2AServer()

# Add middleware in correct order (last added = first executed)
if settings.enable_metrics:
    app.add_middleware(MetricsMiddleware)

app.add_middleware(PerformanceLoggingMiddleware, slow_request_threshold=1.0)
app.add_middleware(ErrorLoggingMiddleware)
app.add_middleware(RequestLoggingMiddleware)

# Security middleware
security_middleware = SecurityMiddleware(app)
app.add_middleware(type(security_middleware))
a2a_server.security_middleware = security_middleware

# CORS middleware (should be last)
if settings.enable_cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/.well-known/agent.json", response_model=AgentCard)
async def get_agent_card() -> AgentCard:
    """Return agent capabilities and metadata"""
    return a2a_server.get_agent_card()


@app.post("/rpc")
async def handle_jsonrpc(
    request: Request,
    auth_payload: Optional[Dict] = Depends(a2a_server.authenticate_request)
):
    """Handle JSON-RPC 2.0 requests for A2A protocol"""
    try:
        # Parse JSON-RPC request
        body = await request.json()
        jsonrpc_request = JSONRPCRequest(**body)
        
        # Route based on method
        if jsonrpc_request.method == "message/send":
            return await handle_message_send(jsonrpc_request, auth_payload)
        elif jsonrpc_request.method == "message/stream":
            return await handle_message_stream(jsonrpc_request, auth_payload)
        else:
            error_response = JSONRPCResponse(
                error={
                    "code": JSONRPC_METHOD_NOT_FOUND,
                    "message": f"Method '{jsonrpc_request.method}' not found"
                },
                id=jsonrpc_request.id
            )
            return JSONResponse(content=error_response.model_dump(), status_code=200)
    
    except ValidationError as e:
        error_response = JSONRPCResponse(
            error={
                "code": JSONRPC_INVALID_PARAMS,
                "message": str(e)
            },
            id=getattr(jsonrpc_request, 'id', None) if 'jsonrpc_request' in locals() else None
        )
        return JSONResponse(content=error_response.model_dump(), status_code=200)
    
    except Exception as e:
        logger.error("JSON-RPC request failed", error=str(e))
        error_response = JSONRPCResponse(
            error=exception_to_jsonrpc_error(e),
            id=getattr(jsonrpc_request, 'id', None) if 'jsonrpc_request' in locals() else None
        )
        return JSONResponse(content=error_response.model_dump(), status_code=200)


async def handle_message_send(
    jsonrpc_request: JSONRPCRequest, 
    auth_payload: Optional[Dict]
) -> JSONResponse:
    """Handle message/send method"""
    try:
        # Parse parameters
        params = MessageSendParams(**jsonrpc_request.params)
        
        # Determine agent based on message content (simple routing)
        agent_id = "default"
        text_content = ""
        
        for part in params.message.parts:
            if part.kind == MessagePartType.TEXT:
                text_content += part.text + " "
        
        # Route to weather agent if weather-related
        if any(word in text_content.lower() for word in ["weather", "temperature", "forecast", "rain", "sunny", "cloudy"]):
            agent_id = "weather"
        
        # Create task request
        task_request = TaskRequest(
            id=str(jsonrpc_request.id),
            message=params.message,
            contextId=params.contextId,
            taskId=params.taskId
        )
        
        # Process task
        result = await a2a_server.process_task(task_request, agent_id=agent_id, streaming=False)
        
        # Return JSON-RPC response
        response = JSONRPCResponse(
            result=result,
            id=jsonrpc_request.id
        )
        return JSONResponse(content=response.model_dump(mode='json'))
    
    except Exception as e:
        logger.error("message/send failed", error=str(e))
        raise


async def handle_message_stream(
    jsonrpc_request: JSONRPCRequest, 
    auth_payload: Optional[Dict]
) -> StreamingResponse:
    """Handle message/stream method"""
    try:
        # Parse parameters
        params = MessageSendParams(**jsonrpc_request.params)
        
        # Determine agent based on message content (simple routing)
        agent_id = "default"
        text_content = ""
        
        for part in params.message.parts:
            if part.kind == MessagePartType.TEXT:
                text_content += part.text + " "
        
        # Route to weather agent if weather-related
        if any(word in text_content.lower() for word in ["weather", "temperature", "forecast", "rain", "sunny", "cloudy"]):
            agent_id = "weather"
        
        # Create task request
        task_request = TaskRequest(
            id=str(jsonrpc_request.id),
            message=params.message,
            contextId=params.contextId,
            taskId=params.taskId
        )
        
        # Process streaming task
        event_generator = await a2a_server.process_task(task_request, agent_id=agent_id, streaming=True)
        
        return StreamingResponse(
            event_generator,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    
    except Exception as e:
        logger.error("message/stream failed", error=str(e))
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers"""
    metrics_summary = get_current_metrics_summary()
    
    return {
        "status": "healthy",
        "active_tasks": len(a2a_server.active_tasks),
        "registered_agents": len(a2a_server.agents),
        "metrics": metrics_summary,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus metrics endpoint"""
    return await get_metrics()


@app.get("/debug/agents")
async def debug_agents(
    auth_payload: Optional[Dict] = Depends(a2a_server.authenticate_request)
):
    """Debug endpoint to list registered agents"""
    if not settings.debug:
        raise HTTPException(status_code=404, detail="Debug endpoints disabled")
    
    agents_info = {}
    for agent_id, agent in a2a_server.agents.items():
        agents_info[agent_id] = {
            "name": agent.name,
            "description": agent.description,
            "version": agent.version,
            "skills": [skill.model_dump() for skill in agent.skills],
            "created_at": agent.created_at.isoformat()
        }
    
    return {
        "agents": agents_info,
        "total_count": len(agents_info)
    }


@app.get("/debug/tasks")
async def debug_tasks(
    auth_payload: Optional[Dict] = Depends(a2a_server.authenticate_request)
):
    """Debug endpoint to list active tasks"""
    if not settings.debug:
        raise HTTPException(status_code=404, detail="Debug endpoints disabled")
    
    return {
        "active_tasks": a2a_server.active_tasks,
        "total_count": len(a2a_server.active_tasks)
    }


@app.get("/debug/config")
async def debug_config(
    auth_payload: Optional[Dict] = Depends(a2a_server.authenticate_request)
):
    """Debug endpoint to show configuration"""
    if not settings.debug:
        raise HTTPException(status_code=404, detail="Debug endpoints disabled")
    
    return {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "debug": settings.debug,
        "enable_metrics": settings.enable_metrics,
        "enable_streaming": settings.enable_streaming,
        "enable_security_headers": settings.enable_security_headers,
        "rate_limit_rpm": settings.rate_limit_requests_per_minute,
        "agent_timeout": settings.agent_timeout,
        "max_concurrent_tasks": settings.max_concurrent_tasks
    }


if __name__ == "__main__":
    uvicorn.run(
        "src.server.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
