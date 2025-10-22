"""
Quick test script to verify SDK functionality.

This script tests the basic SDK components without requiring
a running platform instance.
"""

import asyncio
import logging
import json
from typing import Dict

# Configure logging to see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test imports
try:
    from conversimple import ConversimpleAgent, tool, tool_async
    print("✅ SDK imports successful")
except ImportError as e:
    print(f"❌ Import error: {e}")
    exit(1)


class TestAgent(ConversimpleAgent):
    """Test agent to verify SDK functionality."""

    @tool("Get greeting message for a name")
    def get_greeting(self, name: str, formal: bool = False) -> Dict:
        """Test sync tool."""
        if formal:
            return {"message": f"Good day, {name}"}
        else:
            return {"message": f"Hello, {name}!"}

    @tool_async("Simulate async API call")
    async def async_api_call(self, endpoint: str, timeout: int = 5) -> Dict:
        """Test async tool."""
        await asyncio.sleep(0.1)  # Simulate API delay
        return {
            "endpoint": endpoint,
            "status": "success",
            "response_time": 100,
            "timeout": timeout
        }

    @tool("Calculate simple math")
    def calculate(self, operation: str, a: float, b: float) -> Dict:
        """Test tool with multiple parameters."""
        operations = {
            "add": a + b,
            "subtract": a - b,
            "multiply": a * b,
            "divide": a / b if b != 0 else None
        }
        
        if operation not in operations:
            return {"error": f"Unknown operation: {operation}"}
            
        result = operations[operation]
        if result is None:
            return {"error": "Division by zero"}
            
        return {
            "operation": operation,
            "inputs": {"a": a, "b": b},
            "result": result
        }

    def on_conversation_started(self, conversation_id: str) -> None:
        print(f"🎤 Test conversation started: {conversation_id}")

    def on_tool_called(self, tool_call) -> None:
        print(f"🔧 Tool called: {tool_call.tool_name}")


async def test_tool_discovery():
    """Test tool discovery and schema generation."""
    print("\n📋 Testing Tool Discovery")
    print("=" * 40)
    
    # Create agent (won't connect to platform)
    agent = TestAgent(api_key="test-key", customer_id="test-customer")
    
    # Auto-register tools
    from conversimple.tools import auto_register_tools
    auto_register_tools(agent)
    
    # Check registered tools
    tools = agent.tool_registry.get_registered_tools()
    
    print(f"Discovered {len(tools)} tools:")
    for tool in tools:
        print(f"  - {tool['name']}: {tool['description']}")
        print(f"    Parameters: {len(tool['parameters']['properties'])}")
        
        # Show parameter details
        for param_name, param_schema in tool['parameters']['properties'].items():
            required = "required" if param_name in tool['parameters'].get('required', []) else "optional"
            print(f"      • {param_name} ({param_schema['type']}, {required})")
        print()


async def test_tool_execution():
    """Test tool execution."""
    print("\n🔧 Testing Tool Execution")
    print("=" * 40)
    
    agent = TestAgent(api_key="test-key", customer_id="test-customer")
    from conversimple.tools import auto_register_tools
    auto_register_tools(agent)
    
    # Test sync tool
    print("Testing sync tool: get_greeting")
    result = await agent.tool_registry.execute_tool("get_greeting", {"name": "Alice", "formal": True})
    print(f"  Result: {result}")
    
    # Test async tool
    print("Testing async tool: async_api_call")
    result = await agent.tool_registry.execute_tool("async_api_call", {"endpoint": "/users", "timeout": 10})
    print(f"  Result: {result}")
    
    # Test math tool
    print("Testing math tool: calculate")
    result = await agent.tool_registry.execute_tool("calculate", {"operation": "multiply", "a": 7, "b": 6})
    print(f"  Result: {result}")
    
    # Test error handling
    print("Testing error handling: division by zero")
    result = await agent.tool_registry.execute_tool("calculate", {"operation": "divide", "a": 10, "b": 0})
    print(f"  Result: {result}")


def test_schema_generation():
    """Test JSON schema generation from type hints."""
    print("\n📝 Testing Schema Generation")
    print("=" * 40)
    
    from conversimple.tools import ToolRegistry
    import inspect
    
    registry = ToolRegistry()
    
    # Test function with various parameter types
    def test_function(
        name: str,
        age: int,
        height: float,
        active: bool,
        tags: list,
        metadata: dict,
        optional_param: str = "default"
    ) -> dict:
        pass
    
    schema = registry._generate_tool_schema(test_function, "Test function with various types")
    
    print("Generated schema:")
    print(json.dumps(schema, indent=2))


async def main():
    """Run all tests."""
    print("🧪 Conversimple SDK Test Suite")
    print("=" * 50)
    
    try:
        # Run tests
        await test_tool_discovery()
        await test_tool_execution()
        test_schema_generation()
        
        print("\n✅ All tests passed!")
        print("\n💡 Next steps:")
        print("1. Set up environment variables (CONVERSIMPLE_API_KEY, CONVERSIMPLE_CUSTOMER_ID)")
        print("2. Run example agents via dispatcher: python -m conversimple.dispatcher --search-path ./examples")
        print("3. Start developing your own agents!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        logger.exception("Test failure details:")


if __name__ == "__main__":
    asyncio.run(main())
