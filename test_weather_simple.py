#!/usr/bin/env python3
"""
Simple weather test for Zero-A2A
"""

import asyncio
import httpx
import json

async def test_weather_simple():
    """Test weather agent through the standard messaging interface"""
    
    print("🌤️ Testing Weather Agent via Standard Interface")
    print("=" * 50)
    
    base_url = "http://localhost:8000"
    
    # Test with weather-related message that should route to WeatherAgent
    weather_message = {
        "message": {
            "parts": [
                {
                    "type": "text",
                    "content": "What's the weather like in London? I need current weather conditions."
                }
            ]
        }
    }
    
    try:
        async with httpx.AsyncClient() as client:
            # Test health
            health = await client.get(f"{base_url}/health", timeout=5.0)
            print(f"✅ Server Status: {health.json()['status']}")
            
            # Send weather message
            print("\n🌦️ Sending weather query...")
            response = await client.post(
                f"{base_url}/messages/send",
                json=weather_message,
                timeout=20.0
            )
            
            if response.status_code == 200:
                result = response.json()
                message_content = result.get('message', {}).get('parts', [{}])[0].get('content', 'No content')
                
                print("✅ Weather response received!")
                print(f"   Response: {message_content[:150]}...")
                
                # Check if it looks like weather data
                if any(word in message_content.lower() for word in ['weather', 'temperature', 'humidity', 'wind']):
                    print("✅ Response contains weather information!")
                else:
                    print("⚠️ Response doesn't seem weather-related")
                    
            else:
                print(f"❌ Request failed: {response.status_code}")
                print(f"   Error: {response.text}")
    
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_weather_simple())
