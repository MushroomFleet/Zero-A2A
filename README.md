# Zero-A2A: Enterprise-Grade Agent-to-Agent Protocol Implementation

Zero-A2A is a production-ready implementation of the Agent-to-Agent (A2A) Protocol, designed for enterprise environments with comprehensive security, monitoring, and scalability features.

## 🚀 Features

- **Enterprise Security**: JWT authentication with RSA256 signing, rate limiting, CORS protection
- **A2A Protocol Compliance**: Full JSON-RPC 2.0 implementation with streaming support
- **High Performance**: Async/await throughout, FastAPI framework, connection pooling ready
- **Monitoring & Observability**: Prometheus metrics, structured logging, health checks
- **Agent Framework**: Extensible base agent system with skill-based capabilities
- **Production Ready**: Comprehensive error handling, validation, and configuration management

## 📋 Requirements

- Python 3.12+
- PostgreSQL (for persistence - optional)
- Redis (for caching - optional)

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd zero-a2a
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -e .
   ```

4. **Configuration**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

## 🏃‍♂️ Quick Start

1. **Start the server**
   ```bash
   python main.py
   ```

2. **Test the agent card endpoint**
   ```bash
   curl http://localhost:8000/.well-known/agent.json
   ```

3. **Send a message to the agent**
   ```bash
   curl -X POST http://localhost:8000/rpc \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "method": "message/send",
       "params": {
         "message": {
           "role": "user",
           "parts": [{"kind": "text", "text": "Hello, Zero-A2A!"}]
         }
       },
       "id": "test-123"
     }'
   ```

## 🏗️ Architecture

### Core Components

- **`src/core/`**: Configuration, models, and exceptions
- **`src/agents/`**: Agent framework and implementations
- **`src/auth/`**: JWT authentication system
- **`src/server/`**: FastAPI application and routing
- **`src/middleware/`**: Security and monitoring middleware
- **`src/utils/`**: Utility functions and helpers

### A2A Protocol Endpoints

- **`GET /.well-known/agent.json`**: Agent capability discovery
- **`POST /rpc`**: JSON-RPC 2.0 endpoint for A2A methods
  - `message/send`: Send message and get response
  - `message/stream`: Send message and get streaming response

### Monitoring Endpoints

- **`GET /health`**: Health check for load balancers
- **`GET /metrics`**: Prometheus metrics (if enabled)
- **`GET /debug/agents`**: Debug agent information (dev mode)
- **`GET /debug/tasks`**: Debug active tasks (dev mode)

## 🔧 Configuration

All configuration is handled through environment variables. See `.env.example` for all available options.

### Key Settings

```bash
# Server
HOST=0.0.0.0
PORT=8000
DEBUG=false

# Security
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=RS256

# External APIs
WEATHER_API_KEY=your-openweather-api-key
```

## 🤖 Creating Custom Agents

Extend the `BaseAgent` class to create custom agents:

```python
from src.agents.base_agent import BaseAgent
from src.core.models import TaskRequest, TaskResponse, AgentSkill

class MyCustomAgent(BaseAgent):
    def __init__(self):
        skill = AgentSkill(
            id="custom_skill",
            name="Custom Skill",
            description="My custom agent skill",
            examples=["example query"]
        )
        super().__init__(
            name="My Custom Agent",
            description="A custom agent implementation",
            skills=[skill]
        )
    
    async def execute_task(self, task_request: TaskRequest) -> TaskResponse:
        # Your custom logic here
        text_content = self.extract_text_content(task_request)
        result = self.create_text_message(f"Processed: {text_content}")
        return await self.postprocess_result(result, task_request.id)
    
    async def execute_streaming_task(self, task_request: TaskRequest):
        # Streaming implementation
        yield self.create_status_update_event(
            task_id=task_request.id,
            state=TaskState.WORKING,
            message="Processing..."
        )
        # ... more events
```

Register your agent with the server:

```python
from src.server.app import a2a_server

my_agent = MyCustomAgent()
a2a_server.register_agent("my_agent", my_agent)
```

## 🔒 Security Features

- **JWT Authentication**: RSA256 signed tokens with configurable expiration
- **Rate Limiting**: Configurable requests per minute with burst protection
- **CORS Protection**: Configurable allowed origins
- **Security Headers**: X-Frame-Options, X-Content-Type-Options, etc.
- **Input Validation**: Comprehensive request validation with Pydantic
- **Error Handling**: Secure error responses without information leakage

## 📊 Monitoring

### Prometheus Metrics

Available at `/metrics` endpoint:

- `zero_a2a_tasks_total`: Total tasks processed
- `zero_a2a_task_duration_seconds`: Task processing time
- `zero_a2a_requests_total`: Total HTTP requests

### Structured Logging

JSON-formatted logs with contextual information:

```json
{
  "timestamp": "2025-01-07T17:55:00Z",
  "level": "info",
  "logger": "zero_a2a.server",
  "message": "Task completed",
  "task_id": "abc123",
  "agent": "default"
}
```

## 🧪 Development

### Debug Mode

Enable debug mode for development:

```bash
DEBUG=true python main.py
```

This enables:
- Auto-reload on code changes
- Debug endpoints (`/debug/agents`, `/debug/tasks`)
- Detailed error responses
- OpenAPI documentation at `/docs`

### Testing

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=src
```

## 📚 A2A Protocol Compliance

Zero-A2A implements the A2A Protocol specification:

- **JSON-RPC 2.0**: Standard request/response format
- **Agent Discovery**: `.well-known/agent.json` endpoint
- **Message Types**: Text, data, image, and file support
- **Streaming**: Server-Sent Events for real-time responses
- **Multi-turn Conversations**: Context and task ID support
- **Error Handling**: Standard JSON-RPC error codes

## 🐳 Docker Deployment

See `docs/Docker-Plan.md` for comprehensive containerization and deployment strategies.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

## 🆘 Support

- **Documentation**: Check the `docs/` directory
- **Issues**: Use GitHub Issues for bug reports
- **Discussions**: Use GitHub Discussions for questions

---

**Zero-A2A** - Enterprise-grade Agent-to-Agent Protocol implementation for the modern AI ecosystem.
