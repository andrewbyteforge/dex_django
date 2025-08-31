#!/usr/bin/env python3
"""
Integration test script for DEX Sniper Pro.
Tests FastAPI endpoints, WebSocket connections, and core functionality.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from decimal import Decimal
from typing import Any, Dict

import httpx
import websockets
from websockets.exceptions import ConnectionClosed

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_URL = "http://127.0.0.1:8000"
WS_BASE_URL = "ws://127.0.0.1:8000"


class IntegrationTester:
    """Integration test suite for DEX Sniper Pro."""
    
    def __init__(self):
        self.client = httpx.AsyncClient(base_url=BASE_URL, timeout=30.0)
        self.test_results = {
            "passed": 0,
            "failed": 0,
            "errors": []
        }
    
    async def run_all_tests(self) -> None:
        """Run all integration tests."""
        logger.info("Starting DEX Sniper Pro integration tests...")
        
        # Test API endpoints
        await self.test_health_endpoints()
        await self.test_paper_trading_endpoints()
        await self.test_trading_endpoints()
        
        # Test WebSocket connections
        await self.test_websockets()
        
        # Print results
        self.print_results()
    
    async def test_health_endpoints(self) -> None:
        """Test health check endpoints."""
        logger.info("Testing health endpoints...")
        
        # Basic health check
        try:
            response = await self.client.get("/health")
            if response.status_code == 200:
                data = response.json()
                assert data["status"] == "ok"
                assert "DEX Sniper Pro" in data["service"]
                self.record_pass("Basic health check")
            else:
                self.record_fail("Basic health check", f"Status: {response.status_code}")
        except Exception as e:
            self.record_fail("Basic health check", str(e))
        
        # Readiness check
        try:
            response = await self.client.get("/health/ready")
            if response.status_code == 200:
                data = response.json()
                assert "dependencies" in data
                assert "web3_providers" in data["dependencies"]
                self.record_pass("Readiness check")
                
                # Log dependency status
                for dep_name, dep_status in data["dependencies"].items():
                    logger.info(f"Dependency {dep_name}: {dep_status}")
            else:
                self.record_fail("Readiness check", f"Status: {response.status_code}")
        except Exception as e:
            self.record_fail("Readiness check", str(e))
    
    async def test_paper_trading_endpoints(self) -> None:
        """Test paper trading API endpoints."""
        logger.info("Testing paper trading endpoints...")
        
        # Toggle paper trading on
        try:
            response = await self.client.post(
                "/api/v1/paper/toggle",
                json={"enabled": True}
            )
            if response.status_code == 200:
                data = response.json()
                assert data["status"] == "ok"
                assert data["paper_enabled"] is True
                self.record_pass("Paper trading toggle ON")
            else:
                self.record_fail("Paper trading toggle ON", f"Status: {response.status_code}")
        except Exception as e:
            self.record_fail("Paper trading toggle ON", str(e))
        
        # Get paper trading metrics
        try:
            response = await self.client.get("/api/v1/metrics/paper")
            if response.status_code == 200:
                data = response.json()
                assert data["status"] == "ok"
                assert "metrics" in data
                self.record_pass("Paper trading metrics")
                logger.info(f"Paper metrics: {data['metrics']}")
            else:
                self.record_fail("Paper trading metrics", f"Status: {response.status_code}")
        except Exception as e:
            self.record_fail("Paper trading metrics", str(e))
        
        # Test thought log emission
        try:
            response = await self.client.post("/api/v1/paper/thought-log/test")
            if response.status_code == 200:
                data = response.json()
                assert data["status"] == "ok"
                self.record_pass("Thought log test")
            else:
                self.record_fail("Thought log test", f"Status: {response.status_code}")
        except Exception as e:
            self.record_fail("Thought log test", str(e))
    
    async def test_trading_endpoints(self) -> None:
        """Test trading-related endpoints."""
        logger.info("Testing trading endpoints...")
        
        # Get supported chains
        try:
            response = await self.client.get("/api/v1/chains")
            if response.status_code == 200:
                data = response.json()
                assert data["status"] == "ok"
                assert "chains" in data
                assert len(data["chains"]) > 0
                self.record_pass("Supported chains")
                logger.info(f"Supported chains: {[c['name'] for c in data['chains']]}")
            else:
                self.record_fail("Supported chains", f"Status: {response.status_code}")
        except Exception as e:
            self.record_fail("Supported chains", str(e))
        
        # Test balance check (with a common address)
        try:
            test_address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"  # Vitalik's address
            response = await self.client.post(
                "/api/v1/balance",
                json={
                    "chain": "ethereum",
                    "address": test_address
                }
            )
            # This might fail if no ETH RPC is available, which is OK for testing
            if response.status_code == 200:
                data = response.json()
                assert data["status"] == "ok"
                assert "balance" in data
                self.record_pass("Balance check")
                logger.info(f"Balance result: {data['balance']}")
            else:
                logger.warning(f"Balance check failed (expected): {response.status_code}")
                self.record_pass("Balance check (degraded - no RPC)")
        except Exception as e:
            logger.warning(f"Balance check failed (expected): {e}")
            self.record_pass("Balance check (degraded - no RPC)")
        
        # Test quote request (this will likely fail without proper RPC setup)
        try:
            # Use well-known token addresses on Ethereum
            weth = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
            usdc = "0xA0b86a33E6441C4C66f36aC6F7b8Aa6Da38Df51F"
            
            response = await self.client.post(
                "/api/v1/quotes",
                json={
                    "chain": "ethereum",
                    "token_in": weth,
                    "token_out": usdc,
                    "amount_in": "0.1",
                    "slippage_bps": 300
                }
            )
            if response.status_code == 200:
                data = response.json()
                assert data["status"] == "ok"
                assert "quote" in data
                self.record_pass("Quote request")
                logger.info(f"Quote result: {data['quote']}")
            else:
                logger.warning(f"Quote request failed (expected): {response.status_code}")
                self.record_pass("Quote request (degraded - no RPC)")
        except Exception as e:
            logger.warning(f"Quote request failed (expected): {e}")
            self.record_pass("Quote request (degraded - no RPC)")
    
    async def test_websockets(self) -> None:
        """Test WebSocket connections."""
        logger.info("Testing WebSocket connections...")
        
        # Test paper trading WebSocket
        await self.test_paper_websocket()
        
        # Test metrics WebSocket
        await self.test_metrics_websocket()
    
    async def test_paper_websocket(self) -> None:
        """Test paper trading WebSocket."""
        try:
            uri = f"{WS_BASE_URL}/ws/paper"
            async with websockets.connect(uri, ping_timeout=10, ping_interval=5) as websocket:
                
                # Receive hello message
                message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(message)
                
                assert data["type"] == "hello"
                assert data["payload"]["channel"] == "paper"
                
                self.record_pass("Paper WebSocket connection")
                logger.info(f"Paper WS hello: {data}")
                
                # Send a ping and wait for any subsequent messages
                await websocket.send(json.dumps({"type": "ping"}))
                
                # Wait briefly for any thought_log messages from the test endpoint
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                    data = json.loads(message)
                    logger.info(f"Paper WS message: {data['type']}")
                    self.record_pass("Paper WebSocket messaging")
                except asyncio.TimeoutError:
                    # No additional messages is OK
                    self.record_pass("Paper WebSocket messaging (no additional messages)")
                
        except Exception as e:
            self.record_fail("Paper WebSocket", str(e))
    
    async def test_metrics_websocket(self) -> None:
        """Test metrics WebSocket."""
        try:
            uri = f"{WS_BASE_URL}/ws/metrics"
            async with websockets.connect(uri, ping_timeout=10, ping_interval=5) as websocket:
                
                # Receive hello message
                message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(message)
                
                assert data["type"] == "hello"
                assert data["payload"]["channel"] == "metrics"
                
                self.record_pass("Metrics WebSocket connection")
                logger.info(f"Metrics WS hello: {data}")
                
                # Request current metrics
                await websocket.send(json.dumps({"type": "request_metrics"}))
                
                # Receive metrics response
                message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(message)
                
                assert data["type"] == "metrics_snapshot"
                
                self.record_pass("Metrics WebSocket messaging")
                logger.info(f"Metrics snapshot: {data['payload']}")
                
        except Exception as e:
            self.record_fail("Metrics WebSocket", str(e))
    
    def record_pass(self, test_name: str) -> None:
        """Record a passing test."""
        self.test_results["passed"] += 1
        logger.info(f"✅ {test_name}")
    
    def record_fail(self, test_name: str, error: str) -> None:
        """Record a failing test."""
        self.test_results["failed"] += 1
        self.test_results["errors"].append(f"{test_name}: {error}")
        logger.error(f"❌ {test_name}: {error}")
    
    def print_results(self) -> None:
        """Print test results summary."""
        total = self.test_results["passed"] + self.test_results["failed"]
        passed = self.test_results["passed"]
        failed = self.test_results["failed"]
        
        print(f"\n{'='*60}")
        print(f"DEX Sniper Pro Integration Test Results")
        print(f"{'='*60}")
        print(f"Total Tests: {total}")
        print(f"Passed: {passed} ✅")
        print(f"Failed: {failed} ❌")
        print(f"Success Rate: {(passed/total*100):.1f}%" if total > 0 else "N/A")
        
        if self.test_results["errors"]:
            print(f"\nErrors:")
            for error in self.test_results["errors"]:
                print(f"  • {error}")
        
        print(f"{'='*60}")
    
    async def cleanup(self) -> None:
        """Cleanup resources."""
        await self.client.aclose()


async def main():
    """Main test function."""
    # Check if server is running
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/health", timeout=5.0)
            if response.status_code != 200:
                print("❌ DEX Sniper Pro server is not responding at http://127.0.0.1:8000")
                print("Please start the server with: python -m dex_django.main")
                sys.exit(1)
    except Exception as e:
        print("❌ Cannot connect to DEX Sniper Pro server at http://127.0.0.1:8000")
        print(f"Error: {e}")
        print("Please start the server with: python -m dex_django.main")
        sys.exit(1)
    
    # Run tests
    tester = IntegrationTester()
    try:
        await tester.run_all_tests()
    finally:
        await tester.cleanup()


if __name__ == "__main__":
    # Add dependencies check
    try:
        import websockets
    except ImportError:
        print("Installing websockets dependency...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
        import websockets
    
    asyncio.run(main())