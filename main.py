import asyncio
import logging
from threading import Thread
from servers.signaling_main import run_signaling_server
from servers.web import run_web_server
from cert import gen_cert

from servers.logging_config import get_logger

async def main():
    logger = get_logger(__name__)
    logger.setLevel(logging.DEBUG)
    #print("\nGenerating cert....")
    #gen_cert() # Auto-generating cert

    print("\nStarting WEB....")
    web_thread = Thread(target=run_web_server, daemon=True)
    web_thread.start()

    print("\nStarting SIGNAL....")
    await run_signaling_server()

if __name__ == "__main__":
    asyncio.run(main())