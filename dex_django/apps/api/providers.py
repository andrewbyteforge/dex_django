from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1")


class ProviderResponse(BaseModel):
    """Provider response model."""
    id: int
    name: str
    url: str
    chain: str
    kind: str
    enabled: bool
    latency_ms: Optional[int] = None
    status: str = "unknown"
    last_checked: Optional[str] = None


class ProviderCreate(BaseModel):
    """Provider creation request."""
    name: str = Field(..., min_length=1, max_length=100)
    url: str = Field(..., min_length=1, max_length=500)
    kind: str = Field(..., pattern="^(rpc|websocket|graphql)$")
    enabled: bool = True


class ProviderUpdate(BaseModel):
    """Provider update request."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    url: Optional[str] = Field(None, min_length=1, max_length=500)
    enabled: Optional[bool] = None


@router.get("/providers/")
async def get_providers(
    chain: Optional[str] = Query(None, description="Filter by chain name"),
    enabled_only: bool = Query(False, description="Only show enabled providers")
) -> Dict[str, Any]:
    """Get all RPC providers and their status."""
    try:
        providers = []
        
        # Get providers from Django models
        from apps.storage.models import Provider
        from apps.chains.providers import web3_manager
        
        query = Provider.objects.all().order_by('id')
        
        if enabled_only:
            query = query.filter(enabled=True)
        
        for provider in query:
            # Detect chain from provider
            detected_chain = web3_manager._detect_chain_from_provider(provider) if hasattr(web3_manager, '_detect_chain_from_provider') else "unknown"
            
            # Filter by chain if requested
            if chain and detected_chain != chain.lower():
                continue
            
            # Check provider status
            status = "active" if provider.enabled else "disabled"
            latency_ms = None
            
            # You could add actual latency checking here
            # latency_ms = await check_provider_latency(provider.url)
            
            provider_data = ProviderResponse(
                id=provider.id,
                name=provider.name,
                url=provider.url,
                chain=detected_chain,
                kind=provider.kind.value if hasattr(provider.kind, 'value') else str(provider.kind),
                enabled=provider.enabled,
                status=status,
                latency_ms=latency_ms,
                last_checked=provider.updated_at.isoformat() if hasattr(provider, 'updated_at') and provider.updated_at else None
            )
            
            providers.append(provider_data)
        
        return {
            "status": "ok",
            "data": [p.dict() for p in providers],
            "count": len(providers),
            "filters": {
                "chain": chain,
                "enabled_only": enabled_only
            }
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to get providers: {str(e)}") from e


@router.post("/providers/")
async def create_provider(provider: ProviderCreate) -> Dict[str, Any]:
    """Create a new RPC provider."""
    try:
        from apps.storage.models import Provider
        
        # Create new provider
        new_provider = Provider.objects.create(
            name=provider.name,
            url=provider.url,
            kind=provider.kind,
            enabled=provider.enabled
        )
        
        return {
            "status": "ok",
            "message": "Provider created successfully",
            "data": {
                "id": new_provider.id,
                "name": new_provider.name,
                "url": new_provider.url,
                "enabled": new_provider.enabled
            }
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to create provider: {str(e)}") from e


@router.put("/providers/{provider_id}")
async def update_provider(provider_id: int, updates: ProviderUpdate) -> Dict[str, Any]:
    """Update an existing provider."""
    try:
        from apps.storage.models import Provider
        
        provider = Provider.objects.get(id=provider_id)
        
        updated_fields = []
        if updates.name is not None:
            provider.name = updates.name
            updated_fields.append("name")
        
        if updates.url is not None:
            provider.url = updates.url
            updated_fields.append("url")
        
        if updates.enabled is not None:
            provider.enabled = updates.enabled
            updated_fields.append("enabled")
        
        provider.save()
        
        return {
            "status": "ok",
            "message": f"Updated provider: {', '.join(updated_fields)}",
            "data": {
                "id": provider.id,
                "name": provider.name,
                "url": provider.url,
                "enabled": provider.enabled
            }
        }
        
    except Provider.DoesNotExist:
        raise HTTPException(404, f"Provider {provider_id} not found")
    except Exception as e:
        raise HTTPException(500, f"Failed to update provider: {str(e)}") from e