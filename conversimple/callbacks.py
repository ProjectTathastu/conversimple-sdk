"""
Event callbacks and lifecycle management for Conversimple SDK.

Provides structured event handling for:
- Conversation lifecycle events
- Tool execution events  
- Configuration updates
- Error notifications
"""

import logging
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime

from .tools import ToolCall

logger = logging.getLogger(__name__)


@dataclass
class ConversationLifecycleEvent:
    """Represents a conversation lifecycle event."""
    event_type: str  # "started" or "ended"
    conversation_id: str
    timestamp: datetime
    metadata: Dict[str, Any]


@dataclass  
class ToolCallEvent:
    """Represents a tool call event."""
    tool_call: ToolCall
    event_type: str  # "called", "completed", "failed"
    timestamp: datetime
    result: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class ErrorEvent:
    """Represents an error event."""
    error_type: str
    error_message: str
    conversation_id: Optional[str]
    timestamp: datetime
    details: Dict[str, Any]


@dataclass
class ConfigUpdateEvent:
    """Represents a configuration update event."""  
    customer_id: str
    configuration: Dict[str, Any]
    timestamp: datetime


class CallbackManager:
    """
    Manages event callbacks for the Conversimple agent.
    
    Provides a centralized way to register and trigger callbacks
    for various platform events.
    """

    def __init__(self):
        # Event callbacks
        self.on_conversation_started: Optional[Callable[[str], None]] = None
        self.on_conversation_ended: Optional[Callable[[str], None]] = None
        self.on_tool_called: Optional[Callable[[ToolCall], None]] = None
        self.on_tool_completed: Optional[Callable[[str, Any], None]] = None
        self.on_error: Optional[Callable[[str, str, Dict], None]] = None
        self.on_config_update: Optional[Callable[[Dict], None]] = None

    async def trigger_conversation_started(
        self, 
        conversation_id: str, 
        metadata: Optional[Dict] = None
    ) -> None:
        """Trigger conversation started callback."""
        if self.on_conversation_started:
            try:
                if asyncio.iscoroutinefunction(self.on_conversation_started):
                    await self.on_conversation_started(conversation_id)
                else:
                    self.on_conversation_started(conversation_id)
                    
                logger.debug(f"Triggered conversation_started callback for {conversation_id}")
                
            except Exception as e:
                logger.error(f"Error in conversation_started callback: {e}")

    async def trigger_conversation_ended(
        self, 
        conversation_id: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """Trigger conversation ended callback."""
        if self.on_conversation_ended:
            try:
                if asyncio.iscoroutinefunction(self.on_conversation_ended):
                    await self.on_conversation_ended(conversation_id)
                else:
                    self.on_conversation_ended(conversation_id)
                    
                logger.debug(f"Triggered conversation_ended callback for {conversation_id}")
                
            except Exception as e:
                logger.error(f"Error in conversation_ended callback: {e}")

    async def trigger_tool_called(self, tool_call: ToolCall) -> None:
        """Trigger tool called callback."""
        if self.on_tool_called:
            try:
                if asyncio.iscoroutinefunction(self.on_tool_called):
                    await self.on_tool_called(tool_call)
                else:
                    self.on_tool_called(tool_call)
                    
                logger.debug(f"Triggered tool_called callback for {tool_call.tool_name}")
                
            except Exception as e:
                logger.error(f"Error in tool_called callback: {e}")

    async def trigger_tool_completed(self, call_id: str, result: Any) -> None:
        """Trigger tool completed callback."""
        if self.on_tool_completed:
            try:
                if asyncio.iscoroutinefunction(self.on_tool_completed):
                    await self.on_tool_completed(call_id, result)
                else:
                    self.on_tool_completed(call_id, result)
                    
                logger.debug(f"Triggered tool_completed callback for {call_id}")
                
            except Exception as e:
                logger.error(f"Error in tool_completed callback: {e}")

    async def trigger_error(
        self, 
        error_type: str, 
        error_message: str, 
        details: Dict[str, Any]
    ) -> None:
        """Trigger error callback."""
        if self.on_error:
            try:
                if asyncio.iscoroutinefunction(self.on_error):
                    await self.on_error(error_type, error_message, details)
                else:
                    self.on_error(error_type, error_message, details)
                    
                logger.debug(f"Triggered error callback for {error_type}")
                
            except Exception as e:
                logger.error(f"Error in error callback: {e}")

    async def trigger_config_update(self, config: Dict[str, Any]) -> None:
        """Trigger configuration update callback."""
        if self.on_config_update:
            try:
                if asyncio.iscoroutinefunction(self.on_config_update):
                    await self.on_config_update(config)
                else:
                    self.on_config_update(config)
                    
                logger.debug("Triggered config_update callback")
                
            except Exception as e:
                logger.error(f"Error in config_update callback: {e}")


# Import asyncio for callback detection
import asyncio