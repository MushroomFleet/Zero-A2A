"""
Core data models for Zero-A2A Protocol
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from enum import Enum
import uuid


class BaseZeroA2AModel(BaseModel):
    """Base model with datetime serialization config"""
    model_config = ConfigDict(
        # Enable JSON serialization of datetime objects
        json_encoders={
            datetime: lambda dt: dt.isoformat() + 'Z' if dt.tzinfo is None else dt.isoformat()
        }
    )


class TaskState(str, Enum):
    """Task execution states"""
    PENDING = "pending"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INPUT_REQUIRED = "input_required"


class MessageRole(str, Enum):
    """Message roles in A2A protocol"""
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


class MessagePartType(str, Enum):
    """Types of message parts"""
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    DATA = "data"


class MessagePart(BaseModel):
    """A part of a message (text, image, file, etc.)"""
    kind: MessagePartType = Field(..., description="Type of message part")
    text: Optional[str] = Field(None, description="Text content")
    image_url: Optional[str] = Field(None, description="Image URL")
    file_url: Optional[str] = Field(None, description="File URL")
    data: Optional[Dict[str, Any]] = Field(None, description="Structured data")
    mime_type: Optional[str] = Field(None, description="MIME type")


class Message(BaseZeroA2AModel):
    """A2A Protocol message"""
    role: MessageRole = Field(..., description="Message role")
    parts: List[MessagePart] = Field(..., description="Message parts")
    messageId: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique message ID")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Message timestamp")


class TaskRequest(BaseZeroA2AModel):
    """Request to execute a task"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique task ID")
    message: Message = Field(..., description="Input message")
    contextId: Optional[str] = Field(None, description="Context ID for multi-turn conversations")
    taskId: Optional[str] = Field(None, description="Existing task ID for continuation")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Request timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class TaskStatus(BaseZeroA2AModel):
    """Task execution status"""
    state: TaskState = Field(..., description="Current task state")
    message: Optional[str] = Field(None, description="Status message")
    progress: Optional[float] = Field(None, description="Progress percentage (0-100)")
    error: Optional[str] = Field(None, description="Error message if failed")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")


class TaskResponse(BaseZeroA2AModel):
    """Response from task execution"""
    id: str = Field(..., description="Task ID")
    status: TaskStatus = Field(..., description="Task status")
    result: Optional[Any] = Field(None, description="Task result")
    contextId: Optional[str] = Field(None, description="Context ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class AgentCapabilities(BaseModel):
    """Agent capabilities specification"""
    streaming: bool = Field(default=True, description="Supports streaming responses")
    pushNotifications: bool = Field(default=True, description="Supports push notifications")
    stateTransitionHistory: bool = Field(default=True, description="Maintains state history")
    multiTurn: bool = Field(default=True, description="Supports multi-turn conversations")
    fileUpload: bool = Field(default=False, description="Supports file uploads")
    fileDownload: bool = Field(default=False, description="Supports file downloads")


class AgentAuthentication(BaseModel):
    """Agent authentication schemes"""
    schemes: List[str] = Field(default=["bearer"], description="Supported auth schemes")
    required: bool = Field(default=False, description="Authentication required")


class AgentSkill(BaseModel):
    """Definition of an agent skill"""
    id: str = Field(..., description="Unique skill identifier")
    name: str = Field(..., description="Human-readable skill name")
    description: str = Field(..., description="Detailed skill description")
    tags: List[str] = Field(default_factory=list, description="Skill tags for categorization")
    examples: List[str] = Field(default_factory=list, description="Example usage")
    inputModes: List[str] = Field(default=["text/plain"], description="Supported input modes")
    outputModes: List[str] = Field(default=["text/plain"], description="Supported output modes")


class AgentCard(BaseModel):
    """Agent card for capability discovery"""
    name: str = Field(..., description="Agent name")
    description: str = Field(..., description="Agent description")
    version: str = Field(..., description="Agent version")
    url: str = Field(..., description="Agent endpoint URL")
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities, description="Agent capabilities")
    authentication: AgentAuthentication = Field(default_factory=AgentAuthentication, description="Authentication info")
    skills: List[AgentSkill] = Field(default_factory=list, description="Available skills")
    defaultInputModes: List[str] = Field(default=["text/plain"], description="Default input modes")
    defaultOutputModes: List[str] = Field(default=["text/plain"], description="Default output modes")
    supportsAuthenticatedExtendedCard: bool = Field(default=False, description="Supports extended card")


class StreamingEvent(BaseZeroA2AModel):
    """Base class for streaming events"""
    type: str = Field(..., description="Event type")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    final: bool = Field(default=False, description="Whether this is the final event")


class TaskStatusUpdateEvent(StreamingEvent):
    """Task status update event for streaming"""
    type: str = Field(default="status_update", description="Event type")
    taskId: str = Field(..., description="Task ID")
    status: TaskStatus = Field(..., description="Updated task status")


class TaskArtifactUpdateEvent(StreamingEvent):
    """Task artifact update event for streaming"""
    type: str = Field(default="artifact_update", description="Event type")
    taskId: str = Field(..., description="Task ID")
    artifact: Any = Field(..., description="Task artifact/result")
    lastChunk: bool = Field(default=False, description="Whether this is the last chunk")


class MessageStreamEvent(StreamingEvent):
    """Message event for streaming"""
    type: str = Field(default="message", description="Event type")
    message: Message = Field(..., description="Message content")


# JSON-RPC 2.0 Protocol Models
class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 request"""
    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")
    method: str = Field(..., description="Method name")
    params: Optional[Dict[str, Any]] = Field(None, description="Method parameters")
    id: Union[str, int, None] = Field(..., description="Request ID")


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 response"""
    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")
    result: Optional[Any] = Field(None, description="Method result")
    error: Optional[Dict[str, Any]] = Field(None, description="Error object")
    id: Union[str, int, None] = Field(..., description="Request ID")


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 error object"""
    code: int = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    data: Optional[Any] = Field(None, description="Additional error data")


# A2A Specific Request/Response Models
class MessageSendParams(BaseModel):
    """Parameters for message/send method"""
    message: Message = Field(..., description="Message to send")
    contextId: Optional[str] = Field(None, description="Context ID")
    taskId: Optional[str] = Field(None, description="Task ID")


class SendMessageRequest(JSONRPCRequest):
    """Send message request"""
    method: str = Field(default="message/send", description="Method name")
    params: MessageSendParams = Field(..., description="Send message parameters")


class SendStreamingMessageRequest(JSONRPCRequest):
    """Send streaming message request"""
    method: str = Field(default="message/stream", description="Method name")
    params: MessageSendParams = Field(..., description="Send message parameters")


class SendMessageResponse(JSONRPCResponse):
    """Send message response"""
    result: Union[Message, TaskResponse] = Field(..., description="Message or task response")


class SendStreamingMessageResponse(JSONRPCResponse):
    """Send streaming message response (single chunk)"""
    result: Union[MessageStreamEvent, TaskStatusUpdateEvent, TaskArtifactUpdateEvent] = Field(
        ..., description="Streaming event"
    )
