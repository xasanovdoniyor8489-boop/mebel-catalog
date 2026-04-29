import asyncio
import subprocess
import sys
import os

async def run_bot():
    from bot import main
    await main()

def run_web():
    port = os.getenv("PORT", "8000")
    subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", port])

if __name__ == "__main__":
    run_web()
    asyncio.run(run_bot())
