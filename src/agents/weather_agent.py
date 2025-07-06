"""
Weather Agent implementation for Zero-A2A Protocol
"""

import asyncio
import httpx
import structlog
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import re

from src.agents.base_agent import BaseAgent
from src.core.models import TaskRequest, TaskResponse, AgentSkill, Message, MessagePart
from src.core.config import settings
from src.core.database import cache_manager

logger = structlog.get_logger()


class WeatherAgent(BaseAgent):
    """Weather forecasting agent with external API integration and caching"""
    
    def __init__(self):
        # Define weather skills
        weather_skill = AgentSkill(
            id="weather_forecast",
            name="Weather Forecast",
            description="Get current weather conditions and forecasts for any location",
            examples=[
                "What's the weather in New York?",
                "Weather forecast for London tomorrow",
                "Current temperature in Tokyo",
                "Will it rain in Paris this week?"
            ]
        )
        
        super().__init__(
            name="Weather Agent",
            description="Advanced weather forecasting agent with real-time data",
            skills=[weather_skill]
        )
        
        self.api_key = settings.weather_api_key
        self.base_url = "https://api.openweathermap.org/data/2.5"
        self.cache_ttl = 600  # 10 minutes cache
        self.logger = logger.bind(component="weather_agent")
        
        if not self.api_key:
            self.logger.warning("Weather API key not configured - using mock data")
    
    async def execute_task(self, task_request: TaskRequest) -> TaskResponse:
        """Execute weather-related tasks"""
        try:
            task_request = await self.preprocess_task(task_request)
            
            # Extract text content from message
            text_content = self.extract_text_content(task_request)
            self.logger.info("Processing weather request", text=text_content, task_id=task_request.id)
            
            # Parse location and weather type from text
            location_info = await self._parse_weather_request(text_content)
            
            # Get weather data
            weather_data = await self._get_weather_data(
                location_info["location"],
                location_info["forecast_type"]
            )
            
            # Format response message
            response_text = await self._format_weather_response(
                location_info["location"],
                weather_data,
                location_info["forecast_type"]
            )
            
            # Create response message
            result_message = self.create_text_message(response_text)
            
            self.logger.info(
                "Weather task completed",
                task_id=task_request.id,
                location=location_info["location"],
                forecast_type=location_info["forecast_type"]
            )
            
            return await self.postprocess_result(result_message, task_request.id)
            
        except Exception as e:
            self.logger.error(
                "Weather task failed",
                task_id=task_request.id,
                error=str(e),
                error_type=type(e).__name__
            )
            
            error_message = self.create_text_message(
                f"I apologize, but I encountered an error while getting weather information: {str(e)}"
            )
            return await self.postprocess_result(error_message, task_request.id)
    
    async def execute_streaming_task(self, task_request: TaskRequest):
        """Execute weather task with streaming response"""
        task_id = task_request.id
        
        try:
            # Send working status
            yield self.create_status_update_event(
                task_id=task_id,
                state="working",
                message="Getting weather information..."
            )
            
            # Process request
            text_content = self.extract_text_content(task_request)
            location_info = await self._parse_weather_request(text_content)
            
            # Send progress update
            yield self.create_status_update_event(
                task_id=task_id,
                state="working",
                message=f"Fetching weather data for {location_info['location']}..."
            )
            
            # Get weather data
            weather_data = await self._get_weather_data(
                location_info["location"],
                location_info["forecast_type"]
            )
            
            # Format and send response
            response_text = await self._format_weather_response(
                location_info["location"],
                weather_data,
                location_info["forecast_type"]
            )
            
            result_message = self.create_text_message(response_text)
            
            # Send final result
            yield self.create_message_event(
                task_id=task_id,
                message=result_message,
                final=True
            )
            
        except Exception as e:
            self.logger.error("Streaming weather task failed", task_id=task_id, error=str(e))
            
            error_message = self.create_text_message(
                f"I apologize, but I encountered an error while getting weather information: {str(e)}"
            )
            
            yield self.create_message_event(
                task_id=task_id,
                message=error_message,
                final=True
            )
    
    async def _parse_weather_request(self, text: str) -> Dict[str, str]:
        """Parse weather request to extract location and forecast type"""
        text_lower = text.lower()
        
        # Extract location
        location = self._extract_location(text)
        
        # Determine forecast type
        forecast_type = "current"  # Default
        
        if any(word in text_lower for word in ["tomorrow", "next day"]):
            forecast_type = "tomorrow"
        elif any(word in text_lower for word in ["week", "weekly", "7 day", "forecast"]):
            forecast_type = "weekly"
        elif any(word in text_lower for word in ["today", "now", "current"]):
            forecast_type = "current"
        
        return {
            "location": location,
            "forecast_type": forecast_type
        }
    
    def _extract_location(self, text: str) -> str:
        """Extract location from natural language text"""
        # Common patterns for location extraction
        patterns = [
            r"(?:in|for|at)\s+([A-Za-z\s,]+?)(?:\s|$|[.!?])",
            r"weather\s+([A-Za-z\s,]+?)(?:\s|$|[.!?])",
            r"([A-Za-z\s,]+?)(?:\s+weather|$)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                location = match.group(1).strip()
                # Clean up common words
                location = re.sub(r'\b(weather|forecast|temperature|in|for|at)\b', '', location, flags=re.IGNORECASE).strip()
                if location and len(location) > 1:
                    return location.title()
        
        # Fallback: look for capitalized words (likely city names)
        words = text.split()
        for word in words:
            if word[0].isupper() and len(word) > 2:
                return word
        
        return "New York"  # Default location
    
    async def _get_weather_data(self, location: str, forecast_type: str) -> Dict[str, Any]:
        """Fetch weather data from API with caching"""
        
        # Check cache first
        cache_key = f"weather:{location.lower()}:{forecast_type}"
        cached_data = await cache_manager.get(cache_key)
        if cached_data:
            self.logger.debug("Weather data retrieved from cache", location=location)
            return cached_data
        
        # If no API key, return mock data
        if not self.api_key:
            return await self._get_mock_weather_data(location, forecast_type)
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if forecast_type == "weekly":
                    # Get 5-day forecast
                    response = await client.get(
                        f"{self.base_url}/forecast",
                        params={
                            "q": location,
                            "appid": self.api_key,
                            "units": "metric",
                            "cnt": 40  # 5 days * 8 (3-hour intervals)
                        }
                    )
                else:
                    # Get current weather
                    response = await client.get(
                        f"{self.base_url}/weather",
                        params={
                            "q": location,
                            "appid": self.api_key,
                            "units": "metric"
                        }
                    )
                
                response.raise_for_status()
                weather_data = response.json()
                
                # Cache the result
                await cache_manager.set(cache_key, weather_data, self.cache_ttl)
                
                self.logger.info(
                    "Weather data fetched from API",
                    location=location,
                    forecast_type=forecast_type
                )
                
                return weather_data
                
        except httpx.HTTPError as e:
            self.logger.error("Weather API error", location=location, error=str(e))
            # Fallback to mock data on API error
            return await self._get_mock_weather_data(location, forecast_type)
        except Exception as e:
            self.logger.error("Unexpected weather error", location=location, error=str(e))
            raise
    
    async def _get_mock_weather_data(self, location: str, forecast_type: str) -> Dict[str, Any]:
        """Generate mock weather data for testing"""
        
        if forecast_type == "weekly":
            return {
                "city": {"name": location},
                "list": [
                    {
                        "dt": int((datetime.now() + timedelta(days=i)).timestamp()),
                        "main": {
                            "temp": 20 + (i * 2),
                            "humidity": 60 + i,
                            "pressure": 1013
                        },
                        "weather": [{"description": "partly cloudy", "main": "Clouds"}],
                        "dt_txt": (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d %H:%M:%S")
                    }
                    for i in range(5)
                ]
            }
        else:
            return {
                "name": location,
                "main": {
                    "temp": 22.5,
                    "humidity": 65,
                    "pressure": 1013,
                    "feels_like": 24.0
                },
                "weather": [{"description": "partly cloudy", "main": "Clouds"}],
                "wind": {"speed": 3.5, "deg": 230},
                "dt": int(datetime.now().timestamp())
            }
    
    async def _format_weather_response(
        self, 
        location: str, 
        weather_data: Dict[str, Any], 
        forecast_type: str
    ) -> str:
        """Format weather data into a natural language response"""
        
        try:
            if forecast_type == "weekly":
                return self._format_weekly_forecast(location, weather_data)
            else:
                return self._format_current_weather(location, weather_data)
                
        except Exception as e:
            self.logger.error("Error formatting weather response", error=str(e))
            return f"I received weather data for {location}, but encountered an error formatting the response."
    
    def _format_current_weather(self, location: str, data: Dict[str, Any]) -> str:
        """Format current weather data"""
        try:
            location_name = data.get("name", location)
            main = data.get("main", {})
            weather = data.get("weather", [{}])[0]
            wind = data.get("wind", {})
            
            temp = main.get("temp", 0)
            feels_like = main.get("feels_like", temp)
            humidity = main.get("humidity", 0)
            description = weather.get("description", "unknown").title()
            wind_speed = wind.get("speed", 0)
            
            response = f"🌤️ Current weather in {location_name}:\n\n"
            response += f"Temperature: {temp:.1f}°C (feels like {feels_like:.1f}°C)\n"
            response += f"Conditions: {description}\n"
            response += f"Humidity: {humidity}%\n"
            response += f"Wind Speed: {wind_speed:.1f} m/s\n"
            
            # Add contextual advice
            if temp < 0:
                response += "\n❄️ Bundle up! It's freezing out there."
            elif temp < 10:
                response += "\n🧥 Quite cold - don't forget your jacket!"
            elif temp > 30:
                response += "\n☀️ It's hot! Stay hydrated and seek shade."
            elif "rain" in description.lower():
                response += "\n☔ Don't forget your umbrella!"
            
            return response
            
        except Exception as e:
            return f"I have weather information for {location}, but there was an error formatting it: {str(e)}"
    
    def _format_weekly_forecast(self, location: str, data: Dict[str, Any]) -> str:
        """Format weekly forecast data"""
        try:
            location_name = data.get("city", {}).get("name", location)
            forecast_list = data.get("list", [])
            
            response = f"📅 5-day weather forecast for {location_name}:\n\n"
            
            # Group by day (taking one forecast per day)
            daily_forecasts = {}
            for item in forecast_list:
                dt = datetime.fromtimestamp(item["dt"])
                date_key = dt.strftime("%Y-%m-%d")
                
                if date_key not in daily_forecasts:
                    daily_forecasts[date_key] = item
            
            # Format each day
            for i, (date_key, forecast) in enumerate(list(daily_forecasts.items())[:5]):
                dt = datetime.strptime(date_key, "%Y-%m-%d")
                day_name = dt.strftime("%A")
                
                main = forecast.get("main", {})
                weather = forecast.get("weather", [{}])[0]
                
                temp = main.get("temp", 0)
                description = weather.get("description", "unknown").title()
                
                response += f"{day_name}: {temp:.1f}°C, {description}\n"
            
            return response
            
        except Exception as e:
            return f"I have forecast information for {location}, but there was an error formatting it: {str(e)}"
