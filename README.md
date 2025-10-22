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

### Define an Agent

```python
from conversimple import ConversimpleAgent, tool

class MyAgent(ConversimpleAgent):
    agent_id = "1b2bb22f-1c3d-4e5f-6789-abcdef012345"

    @tool("Get current weather for a location")
    def get_weather(self, location: str) -> dict:
        return {"location": location, "temperature": 72, "condition": "sunny"}

    def on_conversation_started(self, conversation_id: str):
        print(f"Conversation started: {conversation_id}")
```

### Run the Dispatcher

Use the dispatcher to discover your agent modules and launch per-conversation instances automatically:

```bash
python -m conversimple.dispatcher \
  --api-key "$CONVERSIMPLE_API_KEY" \
  --platform-url "$CONVERSIMPLE_PLATFORM_URL" \
  --search-path ./agents
```

The dispatcher keeps a single control-plane connection, listens for `conversation_ready` events, and spawns a dedicated `ConversimpleAgent` for each active conversation. This applies even if you only have one agent—the dispatcher guarantees safe concurrency and simplifies redeployments.

## Core Concepts

### Dispatcher-Orchestrated Sessions

All deployments (even single-agent) must run through the dispatcher so each conversation is isolated in its own `ConversimpleAgent` instance. The dispatcher:

- Watches for `conversation_ready` events over a persistent control connection
- Scans a directory for `ConversimpleAgent` subclasses that expose an `agent_id`
- Spawns one agent instance per conversation and stops it when the session ends

#### Declaring Agent Identity

Embed the platform agent UUID (or a stable identifier) on each agent class so the dispatcher can auto-register it:

```python
from conversimple import ConversimpleAgent, tool

class BillingAgent(ConversimpleAgent):
    agent_id = "7f1f28f7-4c4c-4a77-8f7a-9cf6580e3f32"

    @tool("Lookup outstanding invoices")
    def lookup_invoices(self, customer_id: str) -> dict:
        ...
```

#### Running the Dispatcher

Point the dispatcher at a directory of agent modules (typically your project root):

```bash
python -m conversimple.dispatcher --api-key "$CONVERSIMPLE_API_KEY" \
  --platform-url "$CONVERSIMPLE_PLATFORM_URL" \
  --search-path ./agents
```

The dispatcher discovers all agents under `--search-path`, matches incoming `agent_id` values from the platform, and launches dedicated `ConversimpleAgent` instances for each conversation. Because the dispatcher brokers every session, you get safe concurrency, easy hot-reloads, and no need to hand-wire credentials inside individual agents. Existing conversations keep running during redeploys; new sessions pick up the latest code automatically.

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

### Basic Configuration

```python
# Simple production setup (recommended)
agent = ConversimpleAgent(
    api_key="your-api-key",
    customer_id="your-customer-id",
    platform_url="wss://platform.conversimple.com/sdk/websocket"
)
# Uses infinite retry with circuit breaker (production defaults)
```

### Advanced Connection Configuration

Control reconnection behavior, timeouts, and circuit breaker:

```python
agent = ConversimpleAgent(
    api_key="your-api-key",
    customer_id="your-customer-id",
    platform_url="wss://platform.conversimple.com/sdk/websocket",

    # Retry configuration
    max_reconnect_attempts=None,      # None = infinite retries (default)
                                      # Set to number for limited retries
    reconnect_backoff=2.0,            # Exponential backoff multiplier (default: 2.0)
    max_backoff=300.0,                # Max wait between retries: 5 minutes (default)
    total_retry_duration=None,        # None = no time limit (default)
                                      # Set to seconds for max retry duration

    # Circuit breaker (stops retrying on permanent failures)
    enable_circuit_breaker=True       # Default: True (recommended)
)
```

### Configuration Examples

#### Production: Infinite Retry with Circuit Breaker
```python
# Recommended for production - never gives up on transient failures
agent = ConversimpleAgent(
    api_key=os.getenv("CONVERSIMPLE_API_KEY"),
    platform_url="wss://platform.conversimple.com/sdk/websocket",
    max_reconnect_attempts=None,      # Infinite retries
    enable_circuit_breaker=True       # Stop on auth failures
)
```

#### Development: Fast Failure
```python
# Good for testing - fails quickly
agent = ConversimpleAgent(
    api_key="test-key",
    platform_url="ws://localhost:4000/sdk/websocket",
    max_reconnect_attempts=5,         # Only 5 attempts
    reconnect_backoff=1.5,            # Faster backoff
    max_backoff=30,                   # Max 30 seconds between retries
    total_retry_duration=120          # Give up after 2 minutes
)
```

#### Aggressive Retry (Long-Running Services)
```python
# For services that must stay connected
agent = ConversimpleAgent(
    api_key=os.getenv("CONVERSIMPLE_API_KEY"),
    max_reconnect_attempts=None,      # Never give up
    max_backoff=600,                  # Max 10 minutes between retries
    enable_circuit_breaker=True       # Still stop on permanent failures
)
```

#### Debugging: Disable Circuit Breaker
```python
# WARNING: Only for debugging - will retry even on auth failures
agent = ConversimpleAgent(
    api_key="invalid-key",
    max_reconnect_attempts=10,
    enable_circuit_breaker=False      # Retry all errors (not recommended)
)
```

## Examples

Example agents live in `examples/` and are discovered automatically when you point the dispatcher at that directory:

```bash
python -m conversimple.dispatcher \
  --api-key "$CONVERSIMPLE_API_KEY" \
  --platform-url "$CONVERSIMPLE_PLATFORM_URL" \
  --search-path ./examples
```

### Simple Weather Agent (`examples/simple_agent.py`)
- Basic weather information tools
- Conversation lifecycle callbacks
- Good starting point for lightweight agents

### Customer Service Agent (`examples/customer_service.py`)
- Customer lookup, balance, and ticket management tools
- Mix of synchronous and asynchronous operations
- Demonstrates stateful workflows and external API usage

### Multi-Step Booking Agent (`examples/booking_agent.py`)
- Availability checks, booking creation, confirmation, and cancellation
- Stateful booking sessions with validations
- Shows how to manage multi-turn transactional flows

## API Reference

### ConversimpleAgent

Main agent class for platform integration.

#### Constructor

```python
ConversimpleAgent(
    api_key: str,
    customer_id: Optional[str] = None,
    platform_url: str = "ws://localhost:4000/sdk/websocket",
    max_reconnect_attempts: Optional[int] = None,
    reconnect_backoff: float = 2.0,
    max_backoff: float = 300.0,
    total_retry_duration: Optional[float] = None,
    enable_circuit_breaker: bool = True
)
```

**Parameters:**
- `api_key` (str): Customer API key for authentication
- `customer_id` (str, optional): Customer identifier (derived from API key if not provided)
- `platform_url` (str): WebSocket URL for platform connection
- `max_reconnect_attempts` (int, optional): Maximum reconnection attempts (None = infinite)
- `reconnect_backoff` (float): Exponential backoff multiplier (default: 2.0)
- `max_backoff` (float): Maximum backoff time in seconds (default: 300s)
- `total_retry_duration` (float, optional): Maximum total retry time (None = no limit)
- `enable_circuit_breaker` (bool): Enable circuit breaker for permanent failures (default: True)

#### Methods

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

The SDK provides comprehensive error handling with intelligent retry logic:

### Connection Errors

#### Automatic Reconnection
- **Exponential backoff** with jitter to prevent thundering herd
- **Infinite retries** by default for transient failures (network issues, server restarts)
- **Circuit breaker** stops retrying on permanent failures (invalid credentials, suspended accounts)

#### Circuit Breaker Behavior

The circuit breaker detects **permanent errors** and stops retrying immediately:

**Permanent Errors (No Retry):**
- Authentication failures (invalid API key, expired credentials)
- Authorization errors (customer suspended, account inactive)
- HTTP 401, 403, 400 status codes
- Missing required credentials

**Transient Errors (Auto Retry):**
- Network timeouts and connection refused
- Server temporarily unavailable
- WebSocket connection drops
- Database connection issues

#### Connection Event Handling

```python
class MyAgent(ConversimpleAgent):
    def on_error(self, error_type: str, message: str, details: dict):
        if error_type == "AUTH_FAILED":
            # Circuit breaker opened - permanent failure
            print(f"🚫 Authentication failed: {message}")
            print("🔑 Check your API key and try again")
            # Do NOT retry - fix credentials first

        elif error_type == "CUSTOMER_SUSPENDED":
            # Circuit breaker opened - account issue
            print(f"⛔ Account suspended: {message}")
            print("📧 Contact support to reactivate account")

        else:
            # Transient error - will auto-retry
            print(f"⚠️  Temporary error: {message}")
            print("🔄 Will reconnect automatically")
```

#### Retry Behavior Examples

```python
# Default: Infinite retry with circuit breaker (recommended)
agent = ConversimpleAgent(api_key="valid-key")
# Network issue → Retries: 2s, 4s, 8s, 16s, ... up to 300s, forever
# Invalid key → Circuit breaker opens immediately, no retries

# Limited retries for testing
agent = ConversimpleAgent(
    api_key="test-key",
    max_reconnect_attempts=5,
    total_retry_duration=120  # Give up after 2 minutes
)
# Network issue → Retries: 2s, 4s, 8s, 16s, 32s, then gives up
# Invalid key → Circuit breaker opens immediately

# Aggressive retry for critical services
agent = ConversimpleAgent(
    api_key="prod-key",
    max_backoff=600,  # Max 10 minutes between retries
    enable_circuit_breaker=True
)
# Network issue → Retries forever, up to 10 min between attempts
# Invalid key → Still stops immediately (circuit breaker)
```

### Tool Execution Errors
- Automatic error reporting to platform
- Exception wrapping and formatting
- Timeout handling (configurable per tool call)

### Logging

```python
import logging

# Configure SDK logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# SDK logger
logger = logging.getLogger("conversimple")
logger.setLevel(logging.DEBUG)  # Detailed connection logs

# Connection-specific logging
connection_logger = logging.getLogger("conversimple.connection")
connection_logger.setLevel(logging.INFO)  # Less verbose
```

**Log Levels:**
- `DEBUG`: Detailed connection events, retry attempts, backoff calculations
- `INFO`: Connection status, tool calls, conversation events
- `WARNING`: Connection warnings, approaching timeouts
- `ERROR`: Connection failures, tool errors, permanent failures

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
