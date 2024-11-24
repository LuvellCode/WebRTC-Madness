import asyncio
from threading import Thread
from servers.signaling import run_signaling_server
from servers.web import run_web_server
from cert import gen_cert

async def main():
    #print("\nGenerating cert....")
    #gen_cert() # Auto-generating cert

    print("\nStarting WEB....")
    web_thread = Thread(target=run_web_server, daemon=True)
    web_thread.start()

    print("\nStarting SIGNAL....")
    await run_signaling_server()

if __name__ == "__main__":
    asyncio.run(main())