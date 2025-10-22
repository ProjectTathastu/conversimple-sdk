"""
Conversimple SDK - Python client library for the Conversational AI Platform.

This SDK enables customers to build and deploy AI agents that integrate with
the Conversimple platform's WebRTC infrastructure and conversation management.
"""

from .agent import ConversimpleAgent
from .dispatcher import AgentRegistry, ConversimpleDispatcher, run_dispatcher
from .tools import tool, tool_async
from .callbacks import (
    ConversationLifecycleEvent,
    ToolCallEvent,
    ErrorEvent,
    ConfigUpdateEvent
)

__version__ = "0.1.0"
__all__ = [
    "ConversimpleAgent",
    "tool", 
    "tool_async",
    "ConversationLifecycleEvent",
    "ToolCallEvent", 
    "ErrorEvent",
    "ConfigUpdateEvent",
    "AgentRegistry",
    "ConversimpleDispatcher",
    "run_dispatcher",
]
