import asyncio
from decimal import Decimal
from datetime import datetime, timedelta
from apps.trading.engine import TradeExecution, TradeStatus, ExecutionMode, trading_engine

async def test_mock_execution():
    print("Testing mock execution...")
    
    # Create a mock execution
    execution = TradeExecution(
        signal_id="test_001",
        pair_address="0xtest123",
        chain="ethereum", 
        dex_name="uniswap_v2",
        token_address="0xtoken456",
        action="BUY",
        amount_usd=Decimal("10"),
        expected_slippage=Decimal("5"),
        stop_loss_price=None,
        take_profit_price=None,
        execution_deadline=datetime.now() + timedelta(minutes=5),
        status=TradeStatus.PENDING
    )
    
    # Set paper mode
    trading_engine.execution_mode = ExecutionMode.PAPER
    
    # Execute the trade
    await trading_engine._execute_single_trade(execution)
    
    print(f"Execution result: {execution.status}")
    print(f"TX Hash: {execution.transaction_hash}")
    print(f"Gas Used: {execution.gas_used}")

if __name__ == "__main__":
    asyncio.run(test_mock_execution())