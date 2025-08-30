# Conversimple SDK

Python client library for the Conversimple Conversational AI Platform.

This SDK enables customers to build and deploy AI agents that integrate with the Conversimple platform's WebRTC infrastructure and conversation management, providing real-time voice conversation capabilities with function calling support.

## Features

- **Real-time Voice Conversations**: Integrate with WebRTC-based voice conversations
- **Function Calling**: Define tools that can be executed during conversations
- **Event-Driven Architecture**: React to conversation lifecycle events  
- **Auto-Reconnection**: Fault-tolerant WebSocket connection with exponential backoff
- **Type Hints**: Full typing support for better development experience
- **Async/Await Support**: Both sync and async tool definitions

## Quick Start

### Installation

```bash
pip install conversimple-sdk
```

### Basic Usage

```python
import asyncio
from conversimple import ConversimpleAgent, tool

class MyAgent(ConversimpleAgent):
    @tool("Get current weather for a location")
    def get_weather(self, location: str) -> dict:
        return {"location": location, "temperature": 72, "condition": "sunny"}

    def on_conversation_started(self, conversation_id: str):
        print(f"Conversation started: {conversation_id}")

async def main():
    agent = MyAgent(
        api_key="your-api-key",
        customer_id="your-customer-id"
    )
    
    await agent.start()
    
    # Keep running
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
```

## Core Concepts

### Agent Session Model

Each `ConversimpleAgent` instance handles a single conversation session. For multiple concurrent conversations, create multiple agent instances:

```python
# Per-conversation agent instances
async def handle_conversation(conversation_id):
    agent = MyAgent(api_key=api_key, customer_id=customer_id)
    await agent.start(conversation_id=conversation_id)
```

### Tool Registration

Define tools using the `@tool` and `@tool_async` decorators:

```python
from conversimple import tool, tool_async

class BusinessAgent(ConversimpleAgent):
    @tool("Look up customer information")
    def lookup_customer(self, customer_id: str) -> dict:
        # Synchronous tool execution
        return customer_database.get(customer_id)
    
    @tool_async("Send email notification")
    async def send_email(self, email: str, subject: str, body: str) -> dict:
        # Asynchronous tool execution
        result = await email_service.send(email, subject, body)
        return {"sent": True, "message_id": result.id}
```

### Event Callbacks

Handle conversation lifecycle events:

```python
class MyAgent(ConversimpleAgent):
    def on_conversation_started(self, conversation_id: str):
        print(f"🎤 Conversation started: {conversation_id}")
    
    def on_conversation_ended(self, conversation_id: str):
        print(f"📞 Conversation ended: {conversation_id}")
    
    def on_tool_called(self, tool_call):
        print(f"🔧 Executing tool: {tool_call.tool_name}")
    
    def on_error(self, error_type: str, message: str, details: dict):
        print(f"❌ Error ({error_type}): {message}")
```

## Configuration

### Environment Variables

```bash
export CONVERSIMPLE_API_KEY="your-api-key"
export CONVERSIMPLE_CUSTOMER_ID="your-customer-id" 
export CONVERSIMPLE_PLATFORM_URL="ws://localhost:4000/sdk/websocket"
export CONVERSIMPLE_LOG_LEVEL="INFO"
```

### Programmatic Configuration

```python
agent = ConversimpleAgent(
    api_key="your-api-key",
    customer_id="your-customer-id",
    platform_url="wss://platform.conversimple.com/sdk/websocket"
)
```

## Examples

The SDK includes several example implementations:

### Simple Weather Agent
```bash
python examples/simple_agent.py
```

A basic agent that provides weather information, demonstrating:
- Tool registration with `@tool` decorator
- Conversation lifecycle callbacks
- Basic agent structure

### Customer Service Agent  
```bash
python examples/customer_service.py
```

Advanced customer service agent with multiple tools:
- Customer lookup and account management
- Support ticket creation
- Email notifications
- Refund processing
- Async tool execution

### Multi-Step Booking Agent
```bash  
python examples/booking_agent.py
```

Complex booking workflow demonstrating:
- Multi-turn conversation state management
- Booking creation, confirmation, and cancellation
- Business rule validation
- Transaction-like processes

## API Reference

### ConversimpleAgent

Main agent class for platform integration.

#### Methods

- `__init__(api_key, customer_id=None, platform_url="ws://localhost:4000/sdk/websocket")`
- `async start(conversation_id=None)` - Start agent and connect to platform
- `async stop()` - Stop agent and disconnect
- `on_conversation_started(conversation_id)` - Conversation started callback
- `on_conversation_ended(conversation_id)` - Conversation ended callback  
- `on_tool_called(tool_call)` - Tool execution callback
- `on_tool_completed(call_id, result)` - Tool completion callback
- `on_error(error_type, message, details)` - Error handling callback

### Tool Decorators

#### @tool(description)
Register synchronous tool function.

```python
@tool("Description of what this tool does")
def my_tool(self, param1: str, param2: int = 10) -> dict:
    return {"result": "success"}
```

#### @tool_async(description)  
Register asynchronous tool function.

```python
@tool_async("Description of async tool")
async def my_async_tool(self, param: str) -> dict:
    await asyncio.sleep(0.1)  # Async operation
    return {"result": "success"}
```

### Type Hints

The SDK automatically generates JSON schemas from Python type hints:

- `str` → `"type": "string"`
- `int` → `"type": "integer"`  
- `float` → `"type": "number"`
- `bool` → `"type": "boolean"`
- `list` → `"type": "array"`
- `dict` → `"type": "object"`
- `Optional[T]` → Same as T (nullable)

## Protocol Details

### WebSocket Messages

The SDK communicates with the platform using these message types:

#### Outgoing (SDK → Platform)
- `register_conversation_tools` - Register available tools
- `tool_call_response` - Tool execution results
- `tool_call_error` - Tool execution failures  
- `heartbeat` - Connection keepalive

#### Incoming (Platform → SDK)
- `tool_call_request` - Tool execution requests
- `conversation_lifecycle` - Conversation started/ended
- `config_update` - Configuration updates
- `analytics_update` - Usage analytics

### Message Format

Tool registration:
```json
{
  "conversation_id": "conv_123",
  "tools": [
    {
      "name": "get_weather",
      "description": "Get weather for location", 
      "parameters": {
        "type": "object",
        "properties": {
          "location": {"type": "string"}
        },
        "required": ["location"]
      }
    }
  ]
}
```

Tool execution:
```json
{
  "call_id": "call_abc123",
  "result": {"temperature": 22, "condition": "sunny"}
}
```

## Error Handling

The SDK provides comprehensive error handling:

### Connection Errors
- Automatic reconnection with exponential backoff
- Configurable retry attempts and timeouts
- Connection state monitoring

### Tool Execution Errors
- Automatic error reporting to platform
- Exception wrapping and formatting
- Timeout handling

### Logging
```python
import logging

# Configure SDK logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("conversimple")
```

## Development

### Setup Development Environment

```bash
git clone https://github.com/conversimple/conversimple-sdk
cd conversimple-sdk

# Create virtual environment  
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Install in editable mode
pip install -e .
```

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black conversimple/
flake8 conversimple/
mypy conversimple/
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

- **Documentation**: https://docs.conversimple.com/sdk
- **GitHub Issues**: https://github.com/conversimple/conversimple-sdk/issues  
- **Email Support**: support@conversimple.com
- **Community**: https://community.conversimple.com