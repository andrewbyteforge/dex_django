from __future__ import annotations

import asyncio
import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal
from dataclasses import dataclass
from web3 import Web3
from web3.contract import Contract
from eth_account import Account
import os

logger = logging.getLogger("trading.router")

@dataclass 
class RouterConfig:
    """Configuration for a DEX router."""
    name: str
    chain: str
    router_address: str
    factory_address: str
    router_abi: List[Dict]
    supports_eth: bool
    fee_tiers: Optional[List[int]] = None  # For V3 routers

class RouterExecutor:
    """Direct DEX router execution engine."""
    
    def __init__(self):
        self.web3_connections = {}
        self.router_configs = {}
        self.private_key = None  # Will load from encrypted storage
        self.initialized = False
        
    async def initialize(self) -> bool:
        """Initialize Web3 connections and router configurations."""
        try:
            # Load router configurations
            await self._load_router_configs()
            
            # Initialize Web3 connections
            await self._initialize_web3_connections()
            
            # Load private key (encrypted)
            await self._load_private_key()
            
            self.initialized = True
            logger.info("Router executor initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize router executor: {e}")
            return False
    
    async def _load_router_configs(self):
        """Load DEX router configurations for all chains."""
        self.router_configs = {
            # Ethereum - Uniswap V2
            "uniswap_v2_ethereum": RouterConfig(
                name="Uniswap V2",
                chain="ethereum", 
                router_address="0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
                factory_address="0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
                router_abi=UNISWAP_V2_ROUTER_ABI,
                supports_eth=True
            ),
            
            # Ethereum - Uniswap V3
            "uniswap_v3_ethereum": RouterConfig(
                name="Uniswap V3",
                chain="ethereum",
                router_address="0xE592427A0AEce92De3Edee1F18E0157C05861564", 
                factory_address="0x1F98431c8aD98523631AE4a59f267346ea31F984",
                router_abi=UNISWAP_V3_ROUTER_ABI,
                supports_eth=True,
                fee_tiers=[500, 3000, 10000]
            ),
            
            # BSC - PancakeSwap V2
            "pancake_v2_bsc": RouterConfig(
                name="PancakeSwap V2", 
                chain="bsc",
                router_address="0x10ED43C718714eb63d5aA57B78B54704E256024E",
                factory_address="0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73", 
                router_abi=PANCAKE_V2_ROUTER_ABI,
                supports_eth=False
            ),
            
            # Base - Uniswap V3
            "uniswap_v3_base": RouterConfig(
                name="Uniswap V3 Base",
                chain="base",
                router_address="0x2626664c2603336E57B271c5C0b26F421741e481",
                factory_address="0x33128a8fC17869897dcE68Ed026d694621f6FDfD",
                router_abi=UNISWAP_V3_ROUTER_ABI,
                supports_eth=True,
                fee_tiers=[500, 3000, 10000]
            ),
            
            # Polygon - QuickSwap
            "quickswap_polygon": RouterConfig(
                name="QuickSwap",
                chain="polygon",
                router_address="0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
                factory_address="0x5757371414417b8C6CAad45bAeF941aBc7d3Ab32",
                router_abi=QUICKSWAP_ROUTER_ABI,
                supports_eth=False
            )
        }

    async def _initialize_web3_connections(self):
        """Initialize Web3 connections for each chain."""
        
        rpc_endpoints = {
            "ethereum": os.getenv("ETH_RPC_URL", "https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY"),
            "bsc": os.getenv("BSC_RPC_URL", "https://bsc-dataseed1.binance.org/"),
            "base": os.getenv("BASE_RPC_URL", "https://mainnet.base.org/"),
            "polygon": os.getenv("POLYGON_RPC_URL", "https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY")
        }
        
        for chain, rpc_url in rpc_endpoints.items():
            try:
                web3 = Web3(Web3.HTTPProvider(rpc_url))
                if web3.is_connected():
                    self.web3_connections[chain] = web3
                    logger.info(f"Connected to {chain}")
                else:
                    logger.error(f"Failed to connect to {chain}")
            except Exception as e:
                logger.error(f"Connection error for {chain}: {e}")

    async def _validate_router_contract(self, router_config: RouterConfig) -> bool:
        """
        Validate router contract exists and has expected interface.
        Handles both V2 and V3 router types correctly.
        """
        try:
            web3 = self.web3_connections.get(router_config.chain)
            if not web3:
                logger.error(f"No Web3 connection for {router_config.chain}")
                return False
            
            router_address = web3.to_checksum_address(router_config.router_address)
            
            # Check if contract exists at address
            code = web3.eth.get_code(router_address)
            if code == b'':
                logger.error(f"No contract at {router_address} on {router_config.chain}")
                return False
            
            # Different validation strategies for V2 vs V3
            if "v3" in router_config.name.lower():
                return await self._validate_v3_router(web3, router_address, router_config)
            else:
                return await self._validate_v2_router(web3, router_address, router_config)
                
        except Exception as e:
            logger.error(f"Router validation failed for {router_config.name}: {e}")
            return False

    async def _validate_v2_router(self, web3: Web3, router_address: str, config: RouterConfig) -> bool:
        """Validate Uniswap V2 style router (has factory() function)."""
        try:
            # V2 routers have factory() function
            router_contract = web3.eth.contract(
                address=router_address,
                abi=[{
                    "constant": True,
                    "inputs": [],
                    "name": "factory",
                    "outputs": [{"name": "", "type": "address"}],
                    "type": "function"
                }]
            )
            
            factory_address = router_contract.functions.factory().call()
            expected_factory = config.factory_address
            
            if factory_address.lower() == expected_factory.lower():
                logger.info(f"✓ {config.name}: V2 router validated (factory: {factory_address})")
                return True
            else:
                logger.warning(f"✗ {config.name}: Factory mismatch. Got {factory_address}, expected {expected_factory}")
                return False
                
        except Exception as e:
            logger.error(f"V2 router validation failed for {config.name}: {e}")
            return False

    async def _validate_v3_router(self, web3: Web3, router_address: str, config: RouterConfig) -> bool:
        """Validate Uniswap V3 style router (has WETH9() function)."""
        try:
            # V3 routers have WETH9() function instead of factory()
            router_contract = web3.eth.contract(
                address=router_address,
                abi=[{
                    "constant": True,
                    "inputs": [],
                    "name": "WETH9",
                    "outputs": [{"name": "", "type": "address"}],
                    "type": "function"
                }]
            )
            
            weth_address = router_contract.functions.WETH9().call()
            
            # V3 validation: check if WETH address is reasonable (not zero)
            if weth_address != "0x0000000000000000000000000000000000000000":
                logger.info(f"✓ {config.name}: V3 router validated (WETH9: {weth_address})")
                return True
            else:
                logger.warning(f"✗ {config.name}: Invalid WETH9 address")
                return False
                
        except Exception as e:
            logger.error(f"V3 router validation failed for {config.name}: {e}")
            return False
    
    async def _load_private_key(self):
        """Load encrypted private key."""
        # TODO: Implement secure key loading
        # For now, load from environment (NOT SECURE FOR PRODUCTION)
        self.private_key = os.getenv("PRIVATE_KEY")
        if not self.private_key:
            logger.warning("PRIVATE_KEY not found in environment - live trading will fail")
    
    async def execute_swap(
        self,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        chain: str,
        dex: str,
        slippage_bps: int = 300
    ) -> Dict[str, Any]:
        """Execute swap directly through DEX router."""
        
        if not self.initialized:
            return {"success": False, "error": "Router executor not initialized"}
        
        router_key = f"{dex}_{chain}"
        if router_key not in self.router_configs:
            return {"success": False, "error": f"Unsupported router: {router_key}"}
        
        config = self.router_configs[router_key]
        
        if chain not in self.web3_connections:
            return {"success": False, "error": f"No Web3 connection for chain: {chain}"}
            
        web3 = self.web3_connections[chain]
        
        try:
            # Get router contract
            router = web3.eth.contract(
                address=config.router_address,
                abi=config.router_abi
            )
            
            # Calculate minimum output with slippage
            amount_out_min = await self._calculate_min_output(
                router, token_in, token_out, amount_in, slippage_bps
            )
            
            # Build transaction
            tx = await self._build_swap_transaction(
                router, token_in, token_out, amount_in, amount_out_min
            )
            
            # Execute transaction
            result = await self._execute_transaction(web3, tx)
            
            return result
            
        except Exception as e:
            logger.error(f"Swap execution failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _calculate_min_output(
        self,
        router: Contract,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        slippage_bps: int
    ) -> int:
        """Calculate minimum output amount accounting for slippage."""
        
        try:
            # Get amounts out from router
            path = [token_in, token_out]
            amounts_out = router.functions.getAmountsOut(
                int(amount_in),
                path
            ).call()
            
            expected_output = amounts_out[-1]
            
            # Apply slippage tolerance
            slippage_multiplier = Decimal(10000 - slippage_bps) / Decimal(10000)
            min_output = int(Decimal(expected_output) * slippage_multiplier)
            
            logger.info(f"Expected output: {expected_output}, Min output: {min_output}")
            return min_output
            
        except Exception as e:
            logger.error(f"Failed to calculate min output: {e}")
            raise
    
    async def _build_swap_transaction(
        self,
        router: Contract,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        amount_out_min: int
    ) -> Dict[str, Any]:
        """Build swap transaction data."""
        
        account = Account.from_key(self.private_key)
        deadline = int(asyncio.get_event_loop().time()) + 300  # 5 minutes
        
        # Choose swap function based on whether ETH is involved
        path = [token_in, token_out]
        
        if token_in.lower() == "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2":  # WETH
            # Swapping ETH for tokens
            function = router.functions.swapExactETHForTokens(
                amount_out_min,
                path,
                account.address,
                deadline
            )
            tx_data = {
                'value': int(amount_in),
                'from': account.address
            }
        elif token_out.lower() == "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2":  # WETH
            # Swapping tokens for ETH
            function = router.functions.swapExactTokensForETH(
                int(amount_in),
                amount_out_min,
                path,
                account.address,
                deadline
            )
            tx_data = {'from': account.address}
        else:
            # Token to token swap
            function = router.functions.swapExactTokensForTokens(
                int(amount_in),
                amount_out_min,
                path,
                account.address,
                deadline
            )
            tx_data = {'from': account.address}
        
        # Build transaction
        tx = function.buildTransaction(tx_data)
        return tx
    
    async def _execute_transaction(self, web3: Web3, tx: Dict[str, Any]) -> Dict[str, Any]:
        """Sign and execute transaction."""
        
        try:
            account = Account.from_key(self.private_key)
            
            # Set gas price and nonce
            tx['gasPrice'] = await self._get_optimal_gas_price(web3)
            tx['nonce'] = web3.eth.get_transaction_count(account.address)
            
            # Estimate gas if not set
            if 'gas' not in tx:
                tx['gas'] = web3.eth.estimate_gas(tx)
            
            # Sign transaction
            signed_tx = web3.eth.account.sign_transaction(tx, self.private_key)
            
            # Send transaction
            tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            logger.info(f"Transaction sent: {tx_hash.hex()}")
            
            # Wait for confirmation
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt['status'] == 1:
                return {
                    "success": True,
                    "tx_hash": tx_hash.hex(),
                    "gas_used": receipt['gasUsed'],
                    "block_number": receipt['blockNumber']
                }
            else:
                return {
                    "success": False,
                    "error": "Transaction reverted",
                    "tx_hash": tx_hash.hex()
                }
                
        except Exception as e:
            logger.error(f"Transaction execution failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _get_optimal_gas_price(self, web3: Web3) -> int:
        """Get optimal gas price for fast execution."""
        
        try:
            # Get current gas price
            current_gas = web3.eth.gas_price
            
            # Add 20% premium for faster inclusion
            optimal_gas = int(current_gas * 1.2)
            
            logger.debug(f"Current gas: {current_gas}, Optimal gas: {optimal_gas}")
            return optimal_gas
            
        except Exception as e:
            logger.warning(f"Failed to get gas price, using default: {e}")
            return 50_000_000_000  # 50 gwei fallback

# Complete Router ABIs
UNISWAP_V2_ROUTER_ABI = [
    {
        "inputs": [
            {"internalType": "uint", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactETHForTokens",
        "outputs": [{"internalType": "uint[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactTokensForETH",
        "outputs": [{"internalType": "uint[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactTokensForTokens",
        "outputs": [{"internalType": "uint[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint", "name": "amountIn", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"}
        ],
        "name": "getAmountsOut",
        "outputs": [{"internalType": "uint[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "factory",
        "outputs": [{"name": "", "type": "address"}],
        "type": "function"
    }
]

# PancakeSwap uses same interface as Uniswap V2
PANCAKE_V2_ROUTER_ABI = UNISWAP_V2_ROUTER_ABI
QUICKSWAP_ROUTER_ABI = UNISWAP_V2_ROUTER_ABI

# Uniswap V3 has different interface - simplified version
UNISWAP_V3_ROUTER_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "address", "name": "tokenIn", "type": "address"},
                    {"internalType": "address", "name": "tokenOut", "type": "address"},
                    {"internalType": "uint24", "name": "fee", "type": "uint24"},
                    {"internalType": "address", "name": "recipient", "type": "address"},
                    {"internalType": "uint256", "name": "deadline", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountOutMinimum", "type": "uint256"},
                    {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"}
                ],
                "internalType": "struct ISwapRouter.ExactInputSingleParams",
                "name": "params",
                "type": "tuple"
            }
        ],
        "name": "exactInputSingle",
        "outputs": [{"internalType": "uint256", "name": "amountOut", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "WETH9",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# Global instance
router_executor = RouterExecutor()