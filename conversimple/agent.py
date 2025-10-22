"""
Main ConversimpleAgent class for customer workflow integration.

Provides WebSocket-based connection to the Conversimple platform with:
- Tool registration and execution
- Conversation lifecycle management
- Real-time event streaming
- Fault-tolerant connection handling
"""

import asyncio
import json
import logging
import os
import uuid
from typing import Dict, List, Optional, Callable, Any, Union
from datetime import datetime
import datetime as dt

from .connection import WebSocketConnection
from .tools import ToolRegistry, ToolCall, auto_register_tools
from .callbacks import CallbackManager
from .utils import setup_logging

logger = logging.getLogger(__name__)


class ConversimpleAgent:
    """
    Main agent class for Conversimple platform integration.
    
    Follows the agent session model - one instance per conversation.
    Each agent instance handles a single conversation lifecycle.
    """

    def __init__(
        self,
        api_key: str,
        customer_id: Optional[str] = None,
        platform_url: str = "ws://localhost:4000/sdk/websocket",
        max_reconnect_attempts: Optional[int] = None,
        reconnect_backoff: float = 2.0,
        max_backoff: float = 300.0,
        total_retry_duration: Optional[float] = None,
        enable_circuit_breaker: bool = True
    ):
        """
        Initialize Conversimple agent with enhanced connection resilience.

        Args:
            api_key: Customer authentication token
            customer_id: Customer identifier (derived from API key if not provided)
            platform_url: WebSocket URL for platform connection
            max_reconnect_attempts: Maximum reconnection attempts (None = infinite, recommended for production)
            reconnect_backoff: Base backoff multiplier for exponential backoff (default: 2.0)
            max_backoff: Maximum backoff time in seconds (default: 300s = 5min)
            total_retry_duration: Maximum total time to retry in seconds (None = no limit)
            enable_circuit_breaker: Enable circuit breaker for permanent failures (default: True)
        """
        self.api_key = api_key
        self.customer_id = customer_id or self._derive_customer_id(api_key)
        self.platform_url = platform_url

        # Core components
        self.connection = WebSocketConnection(
            url=platform_url,
            api_key=api_key,
            customer_id=self.customer_id,
            max_reconnect_attempts=max_reconnect_attempts,
            reconnect_backoff=reconnect_backoff,
            max_backoff=max_backoff,
            total_retry_duration=total_retry_duration,
            enable_circuit_breaker=enable_circuit_breaker
        )
        self.tool_registry = ToolRegistry()
        self.callback_manager = CallbackManager()
        
        # State management
        self.conversation_id: Optional[str] = None
        self.connection_state = "disconnected"
        self.registered_tools: List[Dict] = []
        self.pending_tool_calls: Dict[str, ToolCall] = {}
        
        # Event callbacks
        self.callbacks: Dict[str, Callable] = {}
        
        # Setup logging
        setup_logging()

    def _derive_customer_id(self, api_key: str) -> str:
        """Derive customer ID from API key if not provided."""
        # In production, this would decode/validate the API key
        # For now, use a hash-based approach
        import hashlib
        return hashlib.md5(api_key.encode()).hexdigest()[:12]

    async def start(self, conversation_id: Optional[str] = None) -> None:
        """
        Start the agent and connect to the platform.
        
        Args:
            conversation_id: Unique conversation identifier (generated if not provided)
        """
        self.conversation_id = conversation_id or f"conv_{uuid.uuid4().hex[:8]}"
        
        logger.info(f"Starting agent for conversation: {self.conversation_id}")
        
        # Set up message handlers
        self.connection.set_message_handler(self._handle_platform_message)
        self.connection.set_connection_handler(self._handle_connection_event)
        
        # Connect to platform
        await self.connection.connect()
        self.connection_state = "connected"
        
        # Auto-register tools from decorated methods
        auto_register_tools(self)
        
        # Store tools for later registration when real conversations start
        # Don't register immediately since we don't have a real conversation ID yet
        await self._register_tools()
        
        logger.info(f"Agent started successfully for conversation: {self.conversation_id}")

    async def stop(self) -> None:
        """Stop the agent and disconnect from platform."""
        logger.info(f"Stopping agent for conversation: {self.conversation_id}")
        
        self.connection_state = "disconnecting"
        await self.connection.disconnect()
        self.connection_state = "disconnected"
        
        # Trigger conversation ended callback
        await self.callback_manager.trigger_conversation_ended(self.conversation_id)

    async def _register_tools(self) -> None:
        """Store discovered tools for registration when conversations start."""
        tools = self.tool_registry.get_registered_tools()
        
        if not tools:
            logger.info("No tools discovered")
            return
            
        self.registered_tools = tools
        logger.info(f"Discovered {len(tools)} tools, will register when conversations start")

    async def _register_conversation_tools(self, conversation_id: str, tools: list) -> None:
        """Register tools for a specific conversation."""
        message = {
            "conversation_id": conversation_id,
            "tools": tools
        }
        
        await self.connection.send_message("register_conversation_tools", message)
        logger.info(f"Registered {len(tools)} tools for conversation {conversation_id}")

    async def _handle_platform_message(self, event: str, payload: Dict) -> None:
        """Handle incoming messages from the platform."""
        logger.info(f"📨 Received platform message: {event} - {payload}")
        
        handlers = {
            "config_update": self._handle_config_update,
            "analytics_update": self._handle_analytics_update, 
            "tool_call_request": self._handle_tool_call_request,
            "conversation_lifecycle": self._handle_conversation_lifecycle,
            "hook_event": self._handle_hook_event,
            "connection_warning": self._handle_connection_warning,
            "error_notification": self._handle_error_notification,
            "conversation_ready": self._handle_conversation_ready
        }
        
        handler = handlers.get(event)
        if handler:
            try:
                await handler(payload)
            except Exception as e:
                logger.error(f"Error handling {event}: {e}")
                await self._send_error_response(event, str(e))
        else:
            logger.warning(f"Unhandled platform message: {event}")

    async def _handle_config_update(self, payload: Dict) -> None:
        """Handle configuration updates from platform."""
        logger.info(f"Configuration updated for customer: {payload.get('customer_id')}")
        await self.callback_manager.trigger_config_update(payload)

    async def _handle_analytics_update(self, payload: Dict) -> None:
        """Handle analytics updates from platform."""
        logger.debug(f"Analytics update received: {payload}")
        # Analytics updates are typically fire-and-forget

    async def _handle_conversation_ready(self, payload: Dict) -> None:
        """Handle conversation ready events from platform."""
        conversation_id = payload.get('conversation_id')
        customer_id = payload.get('customer_id')

        logger.info(f"🔧 AGENT_FLOW: Conversation ready event received for {conversation_id}")
        logger.info(f"🔧 AGENT_FLOW: Payload: {payload}")

        if not conversation_id:
            logger.error("🔧 AGENT_FLOW: No conversation_id in conversation_ready event")
            return

        # Update instance conversation_id for future references
        self.conversation_id = conversation_id

        if not self.registered_tools:
            logger.warning("🔧 AGENT_FLOW: No tools available to register for conversation")
            # Even with no tools, trigger callback
            await self.callback_manager.trigger_conversation_started(conversation_id)
            return

        # Register tools for this specific conversation
        logger.info(f"🔧 AGENT_FLOW: Registering {len(self.registered_tools)} tools for conversation {conversation_id}")
        await self._register_conversation_tools(conversation_id, self.registered_tools)

        # Trigger conversation started callback
        await self.callback_manager.trigger_conversation_started(conversation_id)

    async def _handle_tool_call_request(self, payload: Dict) -> None:
        """Handle tool execution requests from platform."""
        call_id = payload.get("call_id")
        tool_name = payload.get("tool_name")
        arguments = payload.get("arguments", {})
        
        logger.info(f"Tool call requested: {tool_name} (call_id: {call_id})")
        
        if not call_id or not tool_name:
            await self._send_tool_error(call_id or "unknown", "Missing call_id or tool_name")
            return
            
        # Create tool call object
        tool_call = ToolCall(
            call_id=call_id,
            tool_name=tool_name,
            arguments=arguments,
            conversation_id=self.conversation_id,
            timeout_seconds=payload.get("timeout_seconds", 30)
        )
        
        # Store as pending
        self.pending_tool_calls[call_id] = tool_call
        
        # Trigger callback
        await self.callback_manager.trigger_tool_called(tool_call)
        
        try:
            # Execute the tool
            result = await self.tool_registry.execute_tool(tool_name, arguments)
            
            # Send successful result
            await self._send_tool_result(call_id, result)
            
            # Trigger completion callback
            await self.callback_manager.trigger_tool_completed(call_id, result)
            
        except Exception as e:
            logger.error(f"Tool execution failed for {tool_name}: {e}")
            await self._send_tool_error(call_id, str(e))
        finally:
            # Clean up pending call
            self.pending_tool_calls.pop(call_id, None)

    async def _handle_conversation_lifecycle(self, payload: Dict) -> None:
        """Handle conversation lifecycle events."""
        event = payload.get("event")
        conversation_id = payload.get("conversation_id")
        
        logger.info(f"🎭 Conversation lifecycle: {event} for {conversation_id}")
        logger.info(f"🎭 Full payload: {payload}")
        
        if event == "conversation_started":
            # Auto-register tools for this conversation
            if conversation_id and self.registered_tools:
                logger.info(f"🔧 Auto-registering {len(self.registered_tools)} tools for conversation {conversation_id}")
                try:
                    await self._register_conversation_tools(conversation_id, self.registered_tools)
                    logger.info(f"✅ Successfully auto-registered tools for conversation {conversation_id}")
                except Exception as e:
                    logger.error(f"❌ Failed to auto-register tools for conversation {conversation_id}: {e}")
            else:
                logger.warning(f"⚠️  Cannot auto-register tools - conversation_id: {conversation_id}, tools available: {bool(self.registered_tools)}")
            
            await self.callback_manager.trigger_conversation_started(conversation_id, payload)
        elif event == "conversation_ended":
            logger.info(f"🏁 Conversation ended: {conversation_id}")
            await self.callback_manager.trigger_conversation_ended(conversation_id, payload)
        else:
            logger.warning(f"❓ Unknown lifecycle event: {event}")

    async def _handle_hook_event(self, payload: Dict) -> None:
        """Handle hook events from platform."""
        event_type = payload.get("event_type")
        logger.debug(f"Hook event received: {event_type}")
        
        # Hook events are typically informational
        # Customers can subscribe to specific hook events if needed

    async def _handle_connection_warning(self, payload: Dict) -> None:
        """Handle connection warnings from platform."""
        message = payload.get("message", "Connection warning")
        logger.warning(f"Platform connection warning: {message}")

    async def _handle_error_notification(self, payload: Dict) -> None:
        """Handle error notifications from platform."""
        error_type = payload.get("error_type")
        error_message = payload.get("error_message")
        
        logger.error(f"Platform error ({error_type}): {error_message}")
        await self.callback_manager.trigger_error(error_type, error_message, payload)

    async def _handle_connection_event(self, event: str, data: Any = None) -> None:
        """Handle WebSocket connection events including circuit breaker."""
        logger.info(f"🔌 Connection event: {event}")

        if event == "connected":
            self.connection_state = "connected"
            logger.info("✅ Connection established successfully")

        elif event == "disconnected":
            self.connection_state = "disconnected"
            logger.info("🔌 Connection closed")

        elif event == "permanent_error":
            # Circuit breaker opened due to permanent failure
            self.connection_state = "failed"
            error_info = data if isinstance(data, dict) else {"error": data}
            error_code = error_info.get("error_code", "UNKNOWN")
            error_message = error_info.get("message", str(error_info.get("error", "Unknown error")))

            logger.error(f"🚫 PERMANENT CONNECTION FAILURE: {error_code}")
            logger.error(f"🚫 Error: {error_message}")
            logger.error(f"🚫 Circuit breaker open - will not retry automatically")
            logger.error(f"🚫 Please check credentials and customer account status")

            # Trigger error callback for permanent failures
            if hasattr(self.callback_manager, 'on_error') and self.callback_manager.on_error:
                await self.callback_manager.on_error(
                    error_code,
                    error_message,
                    error_info
                )

        elif event == "error":
            # Transient error (will retry automatically)
            self.connection_state = "error"
            logger.error(f"❌ Connection error (retrying): {data}")
            logger.info("🔄 Automatic reconnection will be attempted")

    async def _send_tool_result(self, call_id: str, result: Any) -> None:
        """Send tool execution result to platform."""
        message = {
            "call_id": call_id,
            "result": result
        }
        
        await self.connection.send_message("tool_call_response", message)
        logger.debug(f"Sent tool result for call: {call_id}")

    async def _send_tool_error(self, call_id: str, error: str) -> None:
        """Send tool execution error to platform."""
        message = {
            "call_id": call_id,
            "error": {
                "message": error,
                "timestamp": datetime.now(dt.timezone.utc).isoformat()
            }
        }
        
        await self.connection.send_message("tool_call_error", message)
        logger.debug(f"Sent tool error for call: {call_id}")

    async def _send_error_response(self, event: str, error: str) -> None:
        """Send error response for event handling failure."""
        logger.error(f"Failed to handle event {event}: {error}")
        # Platform will handle this through connection monitoring

    # Event callback registration methods
    def on_conversation_started(self, callback: Callable[[str], None]) -> None:
        """Register callback for conversation started events."""
        self.callback_manager.on_conversation_started = callback

    def on_conversation_ended(self, callback: Callable[[str], None]) -> None:
        """Register callback for conversation ended events."""  
        self.callback_manager.on_conversation_ended = callback

    def on_tool_called(self, callback: Callable[[ToolCall], None]) -> None:
        """Register callback for tool call events."""
        self.callback_manager.on_tool_called = callback

    def on_tool_completed(self, callback: Callable[[str, Any], None]) -> None:
        """Register callback for tool completion events."""
        self.callback_manager.on_tool_completed = callback

    def on_error(self, callback: Callable[[str, str, Dict], None]) -> None:
        """Register callback for error events."""
        self.callback_manager.on_error = callback

    def on_config_update(self, callback: Callable[[Dict], None]) -> None:
        """Register callback for configuration updates."""
        self.callback_manager.on_config_update = callback