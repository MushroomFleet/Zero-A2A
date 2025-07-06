"""
Base agent implementation for Zero-A2A Protocol
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, AsyncGenerator
import asyncio
import uuid
from datetime import datetime
import structlog

from src.core.models import (
    TaskRequest, TaskResponse, TaskStatus, TaskState,
    AgentCard, AgentSkill, Message, MessagePart, MessagePartType, MessageRole,
    StreamingEvent, TaskStatusUpdateEvent, TaskArtifactUpdateEvent, MessageStreamEvent
)
from src.core.exceptions import AgentError, ValidationError, TaskError

logger = structlog.get_logger()


class BaseAgent(ABC):
    """Base class for all A2A agents with common functionality"""
    
    def __init__(
        self, 
        name: str, 
        description: str, 
        version: str = "1.0.0",
        skills: Optional[List[AgentSkill]] = None
    ):
        self.name = name
        self.description = description
        self.version = version
        self.skills = skills or []
        self.id = str(uuid.uuid4())
        self.created_at = datetime.utcnow()
        
        # Initialize logger with agent context
        self.logger = logger.bind(agent_id=self.id, agent_name=self.name)
        
    @abstractmethod
    async def execute_task(self, task_request: TaskRequest) -> TaskResponse:
        """Execute the main task logic - must be implemented by subclasses"""
        pass
    
    @abstractmethod
    async def execute_streaming_task(
        self, 
        task_request: TaskRequest
    ) -> AsyncGenerator[StreamingEvent, None]:
        """Execute task with streaming response - must be implemented by subclasses"""
        pass
    
    async def validate_input(self, task_request: TaskRequest) -> bool:
        """Validate incoming task request"""
        try:
            if not task_request.message:
                raise ValidationError("Task message is required")
            
            if not task_request.message.parts:
                raise ValidationError("Message must contain at least one part")
            
            # Validate message parts
            for part in task_request.message.parts:
                if part.kind == MessagePartType.TEXT and not part.text:
                    raise ValidationError("Text parts must have content")
                elif part.kind == MessagePartType.IMAGE and not part.image_url:
                    raise ValidationError("Image parts must have image_url")
                elif part.kind == MessagePartType.FILE and not part.file_url:
                    raise ValidationError("File parts must have file_url")
            
            self.logger.debug("Input validation passed", task_id=task_request.id)
            return True
            
        except ValidationError:
            self.logger.error("Input validation failed", task_id=task_request.id)
            raise
        except Exception as e:
            self.logger.error("Unexpected validation error", error=str(e), task_id=task_request.id)
            raise ValidationError(f"Validation error: {str(e)}")
    
    async def preprocess_task(self, task_request: TaskRequest) -> TaskRequest:
        """Preprocess task before execution"""
        await self.validate_input(task_request)
        
        # Log task start
        self.logger.info(
            "Task preprocessing started", 
            task_id=task_request.id,
            context_id=task_request.contextId,
            existing_task_id=task_request.taskId
        )
        
        return task_request
    
    async def postprocess_result(self, result: Any, task_id: str) -> TaskResponse:
        """Postprocess result after execution"""
        self.logger.info("Task postprocessing started", task_id=task_id)
        
        return TaskResponse(
            id=task_id,
            status=TaskStatus(
                state=TaskState.COMPLETED,
                message="Task completed successfully",
                progress=100.0,
                updated_at=datetime.utcnow()
            ),
            result=result,
            timestamp=datetime.utcnow()
        )
    
    def create_text_message(self, text: str, role: MessageRole = MessageRole.AGENT) -> Message:
        """Create a text message"""
        return Message(
            role=role,
            parts=[MessagePart(kind=MessagePartType.TEXT, text=text)],
            messageId=str(uuid.uuid4()),
            timestamp=datetime.utcnow()
        )
    
    def create_data_message(
        self, 
        data: Dict[str, Any], 
        mime_type: str = "application/json",
        role: MessageRole = MessageRole.AGENT
    ) -> Message:
        """Create a data message"""
        return Message(
            role=role,
            parts=[MessagePart(
                kind=MessagePartType.DATA,
                data=data,
                mime_type=mime_type
            )],
            messageId=str(uuid.uuid4()),
            timestamp=datetime.utcnow()
        )
    
    def create_status_update_event(
        self, 
        task_id: str, 
        state: TaskState, 
        message: Optional[str] = None,
        progress: Optional[float] = None,
        final: bool = False
    ) -> TaskStatusUpdateEvent:
        """Create a task status update event"""
        return TaskStatusUpdateEvent(
            taskId=task_id,
            status=TaskStatus(
                state=state,
                message=message,
                progress=progress,
                updated_at=datetime.utcnow()
            ),
            final=final
        )
    
    def create_artifact_update_event(
        self, 
        task_id: str, 
        artifact: Any, 
        last_chunk: bool = False,
        final: bool = False
    ) -> TaskArtifactUpdateEvent:
        """Create a task artifact update event"""
        return TaskArtifactUpdateEvent(
            taskId=task_id,
            artifact=artifact,
            lastChunk=last_chunk,
            final=final
        )
    
    def create_message_stream_event(
        self, 
        message: Message, 
        final: bool = False
    ) -> MessageStreamEvent:
        """Create a message stream event"""
        return MessageStreamEvent(
            message=message,
            final=final
        )
    
    def get_agent_card(self, base_url: str) -> AgentCard:
        """Generate agent card for capability discovery"""
        return AgentCard(
            name=self.name,
            description=self.description,
            version=self.version,
            url=base_url,
            skills=self.skills,
            defaultInputModes=["text/plain", "application/json"],
            defaultOutputModes=["text/plain", "application/json"]
        )
    
    async def cancel_task(self, task_id: str) -> None:
        """Cancel a running task - can be overridden by subclasses"""
        self.logger.info("Task cancellation requested", task_id=task_id)
        raise TaskError("Task cancellation not supported by this agent", task_id=task_id)
    
    def get_skill_by_id(self, skill_id: str) -> Optional[AgentSkill]:
        """Get a skill by its ID"""
        for skill in self.skills:
            if skill.id == skill_id:
                return skill
        return None
    
    def has_skill(self, skill_id: str) -> bool:
        """Check if agent has a specific skill"""
        return self.get_skill_by_id(skill_id) is not None
    
    def extract_text_content(self, task_request: TaskRequest) -> str:
        """Extract text content from task request message"""
        text_parts = []
        for part in task_request.message.parts:
            if part.kind == MessagePartType.TEXT and part.text:
                text_parts.append(part.text)
        return " ".join(text_parts)
    
    def extract_data_content(self, task_request: TaskRequest) -> List[Dict[str, Any]]:
        """Extract data content from task request message"""
        data_parts = []
        for part in task_request.message.parts:
            if part.kind == MessagePartType.DATA and part.data:
                data_parts.append(part.data)
        return data_parts
    
    async def handle_error(self, error: Exception, task_id: str) -> TaskResponse:
        """Handle errors during task execution"""
        self.logger.error(
            "Task execution error",
            task_id=task_id,
            error=str(error),
            error_type=type(error).__name__
        )
        
        if isinstance(error, AgentError):
            error_message = error.message
            error_code = error.code
        else:
            error_message = f"Internal agent error: {str(error)}"
            error_code = 4001
        
        return TaskResponse(
            id=task_id,
            status=TaskStatus(
                state=TaskState.FAILED,
                message=error_message,
                error=str(error),
                updated_at=datetime.utcnow()
            ),
            timestamp=datetime.utcnow()
        )
    
    async def handle_streaming_error(
        self, 
        error: Exception, 
        task_id: str
    ) -> AsyncGenerator[StreamingEvent, None]:
        """Handle errors during streaming task execution"""
        self.logger.error(
            "Streaming task execution error",
            task_id=task_id,
            error=str(error),
            error_type=type(error).__name__
        )
        
        if isinstance(error, AgentError):
            error_message = error.message
        else:
            error_message = f"Internal agent error: {str(error)}"
        
        # Yield final error status
        yield self.create_status_update_event(
            task_id=task_id,
            state=TaskState.FAILED,
            message=error_message,
            final=True
        )


class SimpleAgent(BaseAgent):
    """Simple agent implementation for basic tasks"""
    
    def __init__(self, name: str, description: str, response_text: str = "Hello from Zero-A2A!"):
        # Define basic skill
        skill = AgentSkill(
            id="simple_response",
            name="Simple Response",
            description="Provides a simple text response",
            tags=["simple", "text"],
            examples=["hello", "hi", "test"]
        )
        
        super().__init__(name, description, skills=[skill])
        self.response_text = response_text
    
    async def execute_task(self, task_request: TaskRequest) -> TaskResponse:
        """Execute simple task with text response"""
        try:
            task_request = await self.preprocess_task(task_request)
            
            # Create response message
            result = self.create_text_message(self.response_text)
            
            return await self.postprocess_result(result, task_request.id)
            
        except Exception as e:
            return await self.handle_error(e, task_request.id)
    
    async def execute_streaming_task(
        self, 
        task_request: TaskRequest
    ) -> AsyncGenerator[StreamingEvent, None]:
        """Execute simple task with streaming response"""
        try:
            task_request = await self.preprocess_task(task_request)
            
            # Yield status update
            yield self.create_status_update_event(
                task_id=task_request.id,
                state=TaskState.WORKING,
                message="Processing request...",
                progress=50.0
            )
            
            # Simulate some processing time
            await asyncio.sleep(0.5)
            
            # Yield result
            result = self.create_text_message(self.response_text)
            yield self.create_message_stream_event(result, final=True)
            
        except Exception as e:
            async for error_event in self.handle_streaming_error(e, task_request.id):
                yield error_event
