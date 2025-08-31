@echo off
echo Starting DEX Sniper Pro Integration Tests...
echo.

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Install test dependencies
echo Installing test dependencies...
pip install websockets httpx

REM Run the test script
echo.
echo Running integration tests...
python test_integration.py

echo.
echo Integration tests completed.
pause