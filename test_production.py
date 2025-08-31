#!/usr/bin/env python3
"""
Test script for production DEX Sniper Pro API.
Validates all endpoints are working with real Django integration.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any, Dict

import httpx

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "http://127.0.0.1:8000"

class ProductionTester:
    def __init__(self):
        self.client = httpx.AsyncClient(base_url=BASE_URL, timeout=10.0)
        self.passed = 0
        self.failed = 0

    async def test_all_endpoints(self):
        """Test all production endpoints."""
        
        print("🧪 Testing Production DEX Sniper Pro API")
        print("=" * 50)
        
        # Test health endpoints
        await self.test_health()
        
        # Test bot endpoints
        await self.test_bot_endpoints()
        
        # Test provider endpoints
        await self.test_provider_endpoints()
        
        # Test token endpoints
        await self.test_token_endpoints()
        
        # Test trade endpoints
        await self.test_trade_endpoints()
        
        # Test trading endpoints
        await self.test_trading_endpoints()
        
        # Print results
        total = self.passed + self.failed
        print(f"\n{'='*50}")
        print(f"Results: {self.passed}/{total} passed ({(self.passed/total*100):.1f}%)")
        print(f"{'='*50}")

    async def test_health(self):
        print("\n--- Health Endpoints ---")
        
        endpoints = [
            ("GET", "/health"),
            ("GET", "/health/ready"),
        ]
        
        for method, path in endpoints:
            await self.test_endpoint(method, path)

    async def test_bot_endpoints(self):
        print("\n--- Bot Management Endpoints ---")
        
        endpoints = [
            ("GET", "/api/v1/bot/status"),
            ("GET", "/api/v1/bot/settings"),
        ]
        
        for method, path in endpoints:
            await self.test_endpoint(method, path)

    async def test_provider_endpoints(self):
        print("\n--- Provider Endpoints ---")
        
        endpoints = [
            ("GET", "/api/v1/providers/"),
            ("GET", "/api/v1/providers/?enabled_only=true"),
        ]
        
        for method, path in endpoints:
            await self.test_endpoint(method, path)

    async def test_token_endpoints(self):
        print("\n--- Token Endpoints ---")
        
        endpoints = [
            ("GET", "/api/v1/tokens/"),
            ("GET", "/api/v1/tokens/?page=1&limit=10"),
            ("GET", "/api/v1/tokens/?verified_only=true"),
        ]
        
        for method, path in endpoints:
            await self.test_endpoint(method, path)

    async def test_trade_endpoints(self):
        print("\n--- Trade Endpoints ---")
        
        endpoints = [
            ("GET", "/api/v1/trades/"),
            ("GET", "/api/v1/trades/?page=1&limit=10"),
        ]
        
        for method, path in endpoints:
            await self.test_endpoint(method, path)

    async def test_trading_endpoints(self):
        print("\n--- Trading Endpoints ---")
        
        endpoints = [
            ("GET", "/api/v1/chains"),
        ]
        
        for method, path in endpoints:
            await self.test_endpoint(method, path)

    async def test_endpoint(self, method: str, path: str, data: Dict[str, Any] = None):
        try:
            if method == "GET":
                response = await self.client.get(path)
            elif method == "POST":
                response = await self.client.post(path, json=data or {})
            else:
                response = await self.client.request(method, path, json=data)
            
            status = "✅" if response.status_code < 400 else "❌"
            print(f"{status} {method} {path} -> {response.status_code}")
            
            if response.status_code < 400:
                self.passed += 1
                # Optionally print response structure for key endpoints
                if "/status" in path or "/settings" in path:
                    try:
                        data = response.json()
                        if "data" in data:
                            print(f"    Response keys: {list(data['data'].keys())}")
                    except:
                        pass
            else:
                self.failed += 1
                
        except Exception as e:
            print(f"❌ {method} {path} -> Error: {e}")
            self.failed += 1

    async def cleanup(self):
        await self.client.aclose()

async def main():
    # Check if server is running
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/health", timeout=3.0)
            print(f"Server connectivity: {response.status_code}")
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        print("Please start the server with: python -m dex_django.main")
        return
    
    tester = ProductionTester()
    try:
        await tester.test_all_endpoints()
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    asyncio.run(main())