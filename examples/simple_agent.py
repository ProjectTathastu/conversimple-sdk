"""
Simple Weather Agent Example

Demonstrates basic SDK usage with a weather tool.
Shows conversation lifecycle management and tool execution.
"""

import asyncio
import logging
from typing import Dict

from conversimple import ConversimpleAgent, tool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WeatherAgent(ConversimpleAgent):
    """
    Simple weather agent with basic weather lookup functionality.
    
    Demonstrates:
    - Tool registration with @tool decorator
    - Conversation lifecycle callbacks  
    - Basic agent structure
    """

    @tool("Get current weather for a location")
    def get_weather(self, location: str) -> Dict:
        """
        Get weather information for a specified location.
        
        Args:
            location: City name or location string
            
        Returns:
            Dictionary with weather information
        """
        logger.info(f"Getting weather for: {location}")
        
        # Simulate weather API call
        # In production, this would call a real weather service
        weather_data = {
            "location": location,
            "temperature": 22,
            "condition": "sunny",
            "humidity": 65,
            "wind_speed": 10,
            "description": f"It's a beautiful sunny day in {location} with a temperature of 22°C"
        }
        
        return weather_data

    @tool("Get weather forecast for multiple days")
    def get_forecast(self, location: str, days: int = 3) -> Dict:
        """
        Get weather forecast for specified location and number of days.
        
        Args:
            location: City name or location string
            days: Number of days for forecast (default: 3)
            
        Returns:
            Dictionary with forecast information
        """
        logger.info(f"Getting {days}-day forecast for: {location}")
        
        # Simulate forecast data
        forecast = {
            "location": location,
            "days": days,
            "forecast": []
        }
        
        for day in range(days):
            forecast["forecast"].append({
                "day": day + 1,
                "temperature": 20 + (day * 2),
                "condition": ["sunny", "cloudy", "rainy"][day % 3],
                "precipitation": [0, 20, 80][day % 3]
            })
            
        return forecast

    def on_conversation_started(self, conversation_id: str) -> None:
        """Handle conversation started events."""
        logger.info(f"🌤️  Weather agent ready for conversation: {conversation_id}")
        print(f"Weather agent is now active and ready to help with weather information!")

    def on_conversation_ended(self, conversation_id: str) -> None:
        """Handle conversation ended events."""
        logger.info(f"Weather agent conversation ended: {conversation_id}")
        print(f"Weather agent conversation ended. Goodbye!")

    def on_tool_called(self, tool_call) -> None:
        """Handle tool call events."""
        logger.info(f"🔧 Weather tool called: {tool_call.tool_name}")
        print(f"Executing weather tool: {tool_call.tool_name}")

    def on_tool_completed(self, call_id: str, result) -> None:
        """Handle tool completion events."""
        logger.info(f"✅ Weather tool completed: {call_id}")
        print(f"Weather tool completed successfully")

    def on_error(self, error_type: str, error_message: str, details: Dict) -> None:
        """Handle error events including circuit breaker."""
        logger.error(f"❌ Weather agent error ({error_type}): {error_message}")

        # Handle different error types
        if error_type == "AUTH_FAILED":
            print(f"🚫 Authentication failed: {error_message}")
            print("🔑 Circuit breaker opened - check your API key")
        elif error_type == "CUSTOMER_SUSPENDED":
            print(f"⛔ Account suspended: {error_message}")
            print("📧 Contact support to reactivate your account")
        else:
            # Transient error - will auto-retry
            print(f"⚠️  Temporary error: {error_message}")
            print("🔄 Agent will reconnect automatically")


async def main():
    """
    Main function demonstrating weather agent usage.
    """
    print("🌤️  Starting Weather Agent Example")
    print("=" * 50)
    
    # Get configuration from environment or use defaults
    import os
    api_key = os.getenv("CONVERSIMPLE_API_KEY", "demo-weather-key-123")
    customer_id = os.getenv("CONVERSIMPLE_CUSTOMER_ID", "weather-demo-customer")
    platform_url = os.getenv("CONVERSIMPLE_PLATFORM_URL", "ws://localhost:4000/sdk/websocket")
    
    print(f"Customer ID: {customer_id}")
    print(f"Platform URL: {platform_url}")
    print()

    # Create weather agent with production defaults
    # - Infinite retries for transient errors (network issues)
    # - Circuit breaker stops retries on permanent errors (auth failures)
    # - Exponential backoff up to 5 minutes between retries
    agent = WeatherAgent(
        api_key=api_key,
        customer_id=customer_id,
        platform_url=platform_url
        # Optional connection configuration (showing defaults):
        # max_reconnect_attempts=None,      # Infinite retries (recommended)
        # reconnect_backoff=2.0,            # Exponential backoff multiplier
        # max_backoff=300.0,                # Max 5 minutes between retries
        # enable_circuit_breaker=True       # Stop on auth failures
    )

    # For testing with limited retries:
    # agent = WeatherAgent(
    #     api_key=api_key,
    #     customer_id=customer_id,
    #     platform_url=platform_url,
    #     max_reconnect_attempts=5,         # Only 5 retry attempts
    #     total_retry_duration=60           # Give up after 1 minute
    # )

    # Set up event callbacks
    agent.on_conversation_started = agent.on_conversation_started
    agent.on_conversation_ended = agent.on_conversation_ended  
    agent.on_tool_called = agent.on_tool_called
    agent.on_tool_completed = agent.on_tool_completed
    agent.on_error = agent.on_error

    try:
        # Start the agent
        print("🔗 Connecting to platform...")
        await agent.start()
        
        print("✅ Agent connected successfully!")
        print("🎯 Registered tools:")
        for tool in agent.registered_tools:
            print(f"  - {tool['name']}: {tool['description']}")
        print()
        
        print("🎤 Agent is now listening for conversations...")
        print("💡 Try asking about weather in your voice conversation!")
        print()
        print("Press Ctrl+C to stop the agent")
        
        # Keep the agent running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping weather agent...")
        
    except Exception as e:
        print(f"❌ Error running weather agent: {e}")
        logger.error(f"Weather agent error: {e}")
        
    finally:
        # Clean up
        try:
            await agent.stop()
            print("✅ Weather agent stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping agent: {e}")


if __name__ == "__main__":
    """
    Run the weather agent example.
    
    Usage:
        export CONVERSIMPLE_API_KEY="your-api-key"
        export CONVERSIMPLE_CUSTOMER_ID="your-customer-id"
        python examples/simple_agent.py
    """
    asyncio.run(main())