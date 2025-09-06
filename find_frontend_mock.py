#!/usr/bin/env python
"""Check what the discovery API is actually returning."""

import requests
import json

def check_discovery_api():
    """Call the discovery API and see what it returns."""
    
    url = "http://127.0.0.1:8000/api/v1/discovery/discover-traders"
    
    payload = {
        "chains": ["ethereum"],
        "limit": 20,
        "min_volume_usd": 50000,
        "min_win_rate": 60.0,
        "max_risk_level": "Medium",
        "auto_add_threshold": 85.0
    }
    
    try:
        response = requests.post(url, json=payload)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\nResponse has {len(data.get('wallets', []))} wallets")
            
            # Check first few wallets
            for i, wallet in enumerate(data.get('wallets', [])[:3]):
                print(f"\nWallet {i+1}:")
                print(f"  Address: {wallet.get('address', 'N/A')}")
                print(f"  Chain: {wallet.get('chain', 'N/A')}")
                print(f"  Quality Score: {wallet.get('quality_score', 'N/A')}")
                
            # Save full response
            with open('discovery_response.json', 'w') as f:
                json.dump(data, f, indent=2)
            print("\nFull response saved to discovery_response.json")
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Failed to call API: {e}")

if __name__ == "__main__":
    check_discovery_api()