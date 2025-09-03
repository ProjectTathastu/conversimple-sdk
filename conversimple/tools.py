"""
Tool decorators and management system for Conversimple SDK.

Provides:
- @tool and @tool_async decorators for function registration
- Tool discovery and schema generation
- Tool execution with proper sync/async handling
- JSON schema generation from Python type hints
"""

import asyncio
import inspect
import json
import logging
from typing import Dict, List, Optional, Any, Callable, Union, get_type_hints
from dataclasses import dataclass
from datetime import datetime
import datetime as dt

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """Represents a tool call request from the platform."""
    call_id: str
    tool_name: str
    arguments: Dict[str, Any]
    conversation_id: str
    timeout_seconds: int = 30
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(dt.timezone.utc)


class ToolRegistry:
    """
    Registry for managing customer tools.
    
    Handles tool discovery, schema generation, and execution
    with support for both sync and async functions.
    """

    def __init__(self):
        self.sync_tools: Dict[str, Dict] = {}
        self.async_tools: Dict[str, Dict] = {}

    def register_sync_tool(self, func: Callable, description: str) -> None:
        """Register a synchronous tool function."""
        tool_name = func.__name__
        schema = self._generate_tool_schema(func, description)
        
        self.sync_tools[tool_name] = {
            "function": func,
            "schema": schema,
            "description": description,
            "type": "sync"
        }
        
        logger.debug(f"Registered sync tool: {tool_name}")

    def register_async_tool(self, func: Callable, description: str) -> None:
        """Register an asynchronous tool function."""
        tool_name = func.__name__
        schema = self._generate_tool_schema(func, description)
        
        self.async_tools[tool_name] = {
            "function": func,
            "schema": schema, 
            "description": description,
            "type": "async"
        }
        
        logger.debug(f"Registered async tool: {tool_name}")

    def get_registered_tools(self) -> List[Dict]:
        """Get all registered tools in platform format."""
        tools = []
        
        # Add sync tools
        for tool_name, tool_data in self.sync_tools.items():
            tools.append(tool_data["schema"])
            
        # Add async tools  
        for tool_name, tool_data in self.async_tools.items():
            tools.append(tool_data["schema"])
            
        return tools

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool by name with given arguments."""
        # Check sync tools first
        if tool_name in self.sync_tools:
            tool_data = self.sync_tools[tool_name]
            func = tool_data["function"]
            
            try:
                # Execute synchronous function
                result = func(**arguments)
                logger.debug(f"Sync tool {tool_name} executed successfully")
                return result
                
            except Exception as e:
                logger.error(f"Sync tool {tool_name} execution failed: {e}")
                raise

        # Check async tools
        elif tool_name in self.async_tools:
            tool_data = self.async_tools[tool_name]
            func = tool_data["function"]
            
            try:
                # Execute asynchronous function
                result = await func(**arguments)
                logger.debug(f"Async tool {tool_name} executed successfully")
                return result
                
            except Exception as e:
                logger.error(f"Async tool {tool_name} execution failed: {e}")
                raise
                
        else:
            raise ValueError(f"Tool not found: {tool_name}")

    def _generate_tool_schema(self, func: Callable, description: str) -> Dict:
        """Generate JSON schema for a tool function."""
        signature = inspect.signature(func)
        type_hints = get_type_hints(func)
        
        parameters = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        # Process function parameters
        for param_name, param in signature.parameters.items():
            # Skip self parameter
            if param_name == "self":
                continue
                
            param_schema = self._get_parameter_schema(param, type_hints.get(param_name))
            parameters["properties"][param_name] = param_schema
            
            # Add to required if no default value
            if param.default is inspect.Parameter.empty:
                parameters["required"].append(param_name)

        return {
            "name": func.__name__,
            "description": description,
            "parameters": parameters
        }

    def _get_parameter_schema(self, param: inspect.Parameter, type_hint: Any) -> Dict:
        """Generate schema for a single parameter."""
        schema = {}
        
        # Handle type hints
        if type_hint:
            schema.update(self._type_to_schema(type_hint))
        else:
            schema["type"] = "string"  # Default fallback
            
        # Add description from docstring if available
        # This is a simplified approach - in practice you might want
        # more sophisticated docstring parsing
        
        return schema

    def _type_to_schema(self, type_hint: Any) -> Dict:
        """Convert Python type hint to JSON schema."""
        # Handle basic types
        if type_hint == str:
            return {"type": "string"}
        elif type_hint == int:
            return {"type": "integer"}
        elif type_hint == float:
            return {"type": "number"}
        elif type_hint == bool:
            return {"type": "boolean"}
        elif type_hint == list:
            return {"type": "array"}
        elif type_hint == dict:
            return {"type": "object"}
            
        # Handle Optional types
        if hasattr(type_hint, '__origin__'):
            if type_hint.__origin__ is Union:
                # Check for Optional (Union with None)
                args = type_hint.__args__
                if len(args) == 2 and type(None) in args:
                    # This is Optional[T] - get the non-None type
                    non_none_type = args[0] if args[1] is type(None) else args[1]
                    schema = self._type_to_schema(non_none_type)
                    # JSON Schema doesn't have nullable, but we can document it
                    return schema
                    
            elif type_hint.__origin__ is list:
                # Handle List[T]
                if type_hint.__args__:
                    item_type = type_hint.__args__[0]
                    return {
                        "type": "array",
                        "items": self._type_to_schema(item_type)
                    }
                else:
                    return {"type": "array"}
                    
            elif type_hint.__origin__ is dict:
                # Handle Dict[K, V] 
                return {"type": "object"}
                
        # Fallback for unknown types
        return {"type": "string", "description": f"Type: {type_hint}"}

    def copy(self) -> 'ToolRegistry':
        """Create a copy of this tool registry."""
        new_registry = ToolRegistry()
        new_registry.sync_tools = self.sync_tools.copy()
        new_registry.async_tools = self.async_tools.copy()
        return new_registry


# Global tool decorators
def tool(description: str):
    """
    Decorator for registering synchronous tools.
    
    Usage:
        @tool("Get current weather for a location")
        def get_weather(location: str) -> dict:
            return {"location": location, "temperature": 72}
    """
    def decorator(func):
        # Mark function as a tool
        func._conversimple_tool = {
            "description": description,
            "type": "sync"
        }
        return func
    return decorator


def tool_async(description: str):
    """
    Decorator for registering asynchronous tools.
    
    Usage:
        @tool_async("Fetch user data from API")
        async def fetch_user(user_id: str) -> dict:
            # Async API call
            return {"user_id": user_id, "name": "John"}
    """
    def decorator(func):
        # Mark function as an async tool
        func._conversimple_tool = {
            "description": description,
            "type": "async"
        }
        return func
    return decorator


def discover_tools(obj: Any) -> List[tuple]:
    """
    Discover tools decorated with @tool or @tool_async in an object.
    
    Args:
        obj: Object to scan for decorated methods
        
    Returns:
        List of (method, tool_info) tuples
    """
    tools = []
    
    # Get all methods of the object
    for attr_name in dir(obj):
        attr = getattr(obj, attr_name)
        
        # Check if it's a callable with tool decoration
        if (callable(attr) and 
            hasattr(attr, '_conversimple_tool')):
            
            tool_info = attr._conversimple_tool
            tools.append((attr, tool_info))
            
    return tools


def auto_register_tools(agent_instance: Any) -> None:
    """
    Automatically register tools from an agent instance.
    
    This function scans the agent for decorated methods and registers
    them with the agent's tool registry.
    """
    discovered_tools = discover_tools(agent_instance)
    
    for method, tool_info in discovered_tools:
        description = tool_info["description"]
        tool_type = tool_info["type"]
        
        if tool_type == "sync":
            agent_instance.tool_registry.register_sync_tool(method, description)
        elif tool_type == "async":
            agent_instance.tool_registry.register_async_tool(method, description)
        else:
            logger.warning(f"Unknown tool type: {tool_type}")

    logger.info(f"Auto-registered {len(discovered_tools)} tools")