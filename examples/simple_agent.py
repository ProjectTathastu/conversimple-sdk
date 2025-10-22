"""Simple weather agent definition discovered by the dispatcher."""

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

    agent_id = "example-weather-agent"

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
