"""
Simple test script to verify Zero-A2A is working
"""

import asyncio
import httpx
import json
from datetime import datetime


async def test_zero_a2a():
    """Test the Zero-A2A server functionality"""
    
    base_url = "http://localhost:8000"
    
    print("🚀 Testing Zero-A2A Protocol Implementation")
    print("=" * 50)
    
    async with httpx.AsyncClient() as client:
        
        # Test 1: Health Check
        print("\n1. Testing Health Check...")
        try:
            response = await client.get(f"{base_url}/health")
            if response.status_code == 200:
                health_data = response.json()
                print(f"✅ Health check passed: {health_data['status']}")
                print(f"   Active tasks: {health_data['active_tasks']}")
                print(f"   Registered agents: {health_data['registered_agents']}")
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return
        except Exception as e:
            print(f"❌ Health check error: {e}")
            print("   Make sure the server is running: python main.py")
            return
        
        # Test 2: Agent Card Discovery
        print("\n2. Testing Agent Card Discovery...")
        try:
            response = await client.get(f"{base_url}/.well-known/agent.json")
            if response.status_code == 200:
                agent_card = response.json()
                print(f"✅ Agent card retrieved")
                print(f"   Agent name: {agent_card['name']}")
                print(f"   Version: {agent_card['version']}")
                print(f"   Skills: {len(agent_card['skills'])} available")
                for skill in agent_card['skills']:
                    print(f"     - {skill['name']}: {skill['description']}")
            else:
                print(f"❌ Agent card failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Agent card error: {e}")
        
        # Test 3: Message Send (Non-streaming)
        print("\n3. Testing Message Send (Non-streaming)...")
        try:
            message_request = {
                "jsonrpc": "2.0",
                "method": "message/send",
                "params": {
                    "message": {
                        "role": "user",
                        "parts": [{"kind": "text", "text": "Hello, Zero-A2A! Please respond."}]
                    }
                },
                "id": f"test-{datetime.now().isoformat()}"
            }
            
            response = await client.post(
                f"{base_url}/rpc",
                json=message_request,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                if "result" in result:
                    message = result["result"]["result"]
                    if "parts" in message and len(message["parts"]) > 0:
                        reply_text = message["parts"][0]["text"]
                        print(f"✅ Message send successful")
                        print(f"   Agent reply: {reply_text}")
                    else:
                        print(f"✅ Message send successful (structured response)")
                else:
                    print(f"❌ Unexpected response format: {result}")
            else:
                print(f"❌ Message send failed: {response.status_code}")
                print(f"   Response: {response.text}")
        except Exception as e:
            print(f"❌ Message send error: {e}")
        
        # Test 4: Message Stream
        print("\n4. Testing Message Stream...")
        try:
            stream_request = {
                "jsonrpc": "2.0",
                "method": "message/stream",
                "params": {
                    "message": {
                        "role": "user",
                        "parts": [{"kind": "text", "text": "Hello, streaming test!"}]
                    }
                },
                "id": f"stream-test-{datetime.now().isoformat()}"
            }
            
            async with client.stream(
                "POST",
                f"{base_url}/rpc",
                json=stream_request,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status_code == 200:
                    print("✅ Streaming started")
                    event_count = 0
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            event_count += 1
                            data = line[6:]  # Remove "data: " prefix
                            try:
                                event = json.loads(data)
                                if "result" in event:
                                    event_type = event["result"].get("type", "unknown")
                                    print(f"   📡 Event {event_count}: {event_type}")
                                    if event["result"].get("final", False):
                                        print("   🏁 Stream completed")
                                        break
                            except json.JSONDecodeError:
                                pass
                else:
                    print(f"❌ Streaming failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Streaming error: {e}")
        
        # Test 5: Metrics (if enabled)
        print("\n5. Testing Metrics Endpoint...")
        try:
            response = await client.get(f"{base_url}/metrics")
            if response.status_code == 200:
                metrics_text = response.text
                print("✅ Metrics endpoint accessible")
                task_metrics = [line for line in metrics_text.split('\n') if 'zero_a2a_tasks_total' in line and not line.startswith('#')]
                if task_metrics:
                    print(f"   📊 Task metrics available: {len(task_metrics)} entries")
                else:
                    print("   📊 Metrics endpoint ready (no tasks processed yet)")
            else:
                print(f"⚠️  Metrics endpoint returned: {response.status_code}")
        except Exception as e:
            print(f"⚠️  Metrics error: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 Zero-A2A Testing Complete!")
    print("\nNext steps:")
    print("- Phase 2: Implement WeatherAgent and advanced features")
    print("- Phase 3: Add security middleware and performance optimization")
    print("- Check logs for detailed execution information")


if __name__ == "__main__":
    asyncio.run(test_zero_a2a())
