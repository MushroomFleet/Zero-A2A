#!/usr/bin/env python3
"""
Test Zero-A2A Weather Agent functionality
"""

import asyncio
import httpx
import json

async def test_weather_agent():
    """Test the weather agent functionality"""
    
    print("🌤️ Testing Zero-A2A Weather Agent")
    print("=" * 50)
    
    base_url = "http://localhost:8000"
    
    try:
        # Test weather request
        print("\n1. Testing weather query...")
        
        weather_request = {
            "message": {
                "parts": [
                    {
                        "type": "text",
                        "content": "What's the weather like in London?"
                    }
                ]
            }
        }
        
        async with httpx.AsyncClient() as client:
            # Start the server first
            try:
                health_response = await client.get(f"{base_url}/health", timeout=5.0)
                if health_response.status_code != 200:
                    print("❌ Server not running. Please start with: python main.py")
                    return
            except:
                print("❌ Server not running. Please start with: python main.py")
                return
            
            # Test weather message
            response = await client.post(
                f"{base_url}/messages/send",
                json=weather_request,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Weather query successful!")
                print(f"   Response: {result.get('message', {}).get('parts', [{}])[0].get('content', 'No content')[:100]}...")
            else:
                print(f"❌ Weather query failed: {response.status_code}")
                print(f"   Error: {response.text}")
        
        # Test different weather queries
        test_queries = [
            "Weather forecast for Tokyo this week",
            "Is it raining in Paris?", 
            "Temperature in New York tomorrow",
            "Weather in Sydney"
        ]
        
        print("\n2. Testing various weather queries...")
        
        async with httpx.AsyncClient() as client:
            for i, query in enumerate(test_queries, 1):
                print(f"\n   Query {i}: {query}")
                
                request_data = {
                    "message": {
                        "parts": [
                            {
                                "type": "text",
                                "content": query
                            }
                        ]
                    }
                }
                
                try:
                    response = await client.post(
                        f"{base_url}/messages/send",
                        json=request_data,
                        timeout=20.0
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        content = result.get('message', {}).get('parts', [{}])[0].get('content', 'No content')
                        # Show first line of response
                        first_line = content.split('\n')[0]
                        print(f"   ✅ Response: {first_line}")
                    else:
                        print(f"   ❌ Failed: {response.status_code}")
                        
                except Exception as e:
                    print(f"   ❌ Error: {str(e)}")
                
                # Small delay between requests
                await asyncio.sleep(0.5)
        
        # Test streaming weather
        print("\n3. Testing weather streaming...")
        
        stream_request = {
            "message": {
                "parts": [
                    {
                        "type": "text", 
                        "content": "Give me the weather forecast for Berlin"
                    }
                ]
            }
        }
        
        async with httpx.AsyncClient() as client:
            try:
                async with client.stream(
                    "POST",
                    f"{base_url}/messages/stream",
                    json=stream_request,
                    timeout=30.0
                ) as response:
                    
                    if response.status_code == 200:
                        print("✅ Weather streaming started")
                        
                        event_count = 0
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                event_count += 1
                                try:
                                    data = json.loads(line[6:])  # Remove "data: " prefix
                                    event_type = data.get("type", "unknown")
                                    print(f"   📡 Event {event_count}: {event_type}")
                                    
                                    if event_type == "message":
                                        content = data.get("message", {}).get("parts", [{}])[0].get("content", "")
                                        if content:
                                            first_line = content.split('\n')[0]
                                            print(f"   💬 Weather: {first_line}")
                                    
                                    if event_count >= 5:  # Limit output
                                        break
                                        
                                except json.JSONDecodeError:
                                    continue
                        
                        print("   🏁 Weather streaming completed")
                    else:
                        print(f"❌ Weather streaming failed: {response.status_code}")
                        
            except Exception as e:
                print(f"❌ Weather streaming error: {str(e)}")
        
        print("\n" + "=" * 50)
        print("🎉 Weather Agent Testing Complete!")
        print("\nThe WeatherAgent is working with mock data.")
        print("For real weather data, add a valid WEATHER_API_KEY to your .env file.")
        
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_weather_agent())
