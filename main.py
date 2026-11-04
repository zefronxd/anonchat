import asyncio
import logging
import os

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from database.mongo import database, init_db, close_db
from middlewares.db_session import DbSessionMiddleware
from middlewares.user_registration import UserRegistrationMiddleware
from handlers import start, profile, relay, match, admin, referral

PING_INTERVAL = 300  # 5 minutes


async def health(request):
    return web.Response(text="OK")


async def start_web_server():
    """
    Tiny HTTP server so Render's free Web Service sees an open port.
    Only started when the PORT env variable exists (Render sets it
    automatically for Web Services; Background Workers and VPS don't have it).
    """
    port = os.getenv("PORT")
    if not port:
        return None

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(port))
    await site.start()
    logging.info(f"Keep-alive web server started on port {port}")
    return runner


async def self_ping():
    """
    Pings our own public URL every 5 minutes so Render's free
    Web Service doesn't spin down after 15 minutes of inactivity.
    """
    url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("SELF_PING_URL")
    if not url:
        logging.info("No RENDER_EXTERNAL_URL / SELF_PING_URL set, self-ping disabled.")
        return

    url = url.rstrip("/") + "/health"
    logging.info(f"Self-ping enabled: {url} every {PING_INTERVAL}s")

    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while True:
            await asyncio.sleep(PING_INTERVAL)
            try:
                async with session.get(url) as resp:
                    logging.info(f"Self-ping OK ({resp.status})")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logging.warning(f"Self-ping failed: {e}")


async def main():
    logging.basicConfig(level=logging.INFO)

    # Connect to MongoDB + create indexes
    await init_db()

    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Register Middleware (channel lock / force-subscribe removed)
    dp.update.middleware(DbSessionMiddleware(database))
    dp.update.middleware(UserRegistrationMiddleware())

    # Register Routers (order matters!)
    dp.include_router(referral.router)    # High priority to catch menu clicks in any state
    dp.include_router(admin.router)       # Admin high priority
    dp.include_router(match.router)       # Random-chat buttons: must come BEFORE relay (its FSM-state handler would swallow them)
    dp.include_router(start.router)
    dp.include_router(profile.router)
    dp.include_router(relay.router)
    dp.include_router(match.chat_router)  # Must stay LAST (catch-all that relays chat messages)

    # Keep-alive web server + self-ping (only on Render Web Service)
    web_runner = await start_web_server()
    ping_task = asyncio.create_task(self_ping()) if web_runner else None

    logging.info("Starting bot...")
    try:
        await dp.start_polling(bot)
    finally:
        if ping_task:
            ping_task.cancel()
        if web_runner:
            await web_runner.cleanup()
        await bot.session.close()
        await close_db()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")
