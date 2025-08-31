import httpx
import asyncio
import json

async def test_debug_server():
    async with httpx.AsyncClient() as client:
        print("Testing debug server endpoints...")
        
        # Test health endpoint
        response = await client.get("http://127.0.0.1:8000/health")
        print(f"GET /health -> {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {data}")
            print(f"Has 'status' key: {'status' in data}")
        
        # Test API endpoints
        endpoints = [
            ("GET", "/health/ready"),
            ("POST", "/api/v1/paper/toggle", {"enabled": True}),
            ("GET", "/api/v1/metrics/paper"),
            ("GET", "/api/v1/chains"),
        ]
        
        for method, path, *body in endpoints:
            try:
                if method == "GET":
                    resp = await client.get(f"http://127.0.0.1:8000{path}")
                else:
                    payload = body[0] if body else {}
                    resp = await client.post(f"http://127.0.0.1:8000{path}", json=payload)
                
                status = "✅" if resp.status_code < 400 else "❌"
                print(f"{status} {method} {path} -> {resp.status_code}")
                
            except Exception as e:
                print(f"❌ {method} {path} -> Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_debug_server())