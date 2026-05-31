import ssl
import asyncio
import aiohttp
from vkbottle.http import AiohttpClient
from vkbottle.api import API
from app.config import VK_TOKEN
from app.handlers import bot, router
from app.database import init_db, import_from_json

ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


if __name__ == '__main__':
    async def main():
        await init_db()
        await import_from_json()

        connector = aiohttp.TCPConnector(ssl=ssl_context)
        session = aiohttp.ClientSession(connector=connector)
        http_client = AiohttpClient(session=session)
        api = API(token=VK_TOKEN, http_client=http_client)
        bot.api = api

        print("Бот запущен! Ожидаю события...")

        async for event in bot.polling.listen():
            for raw_update in event.get("updates", []):
                event_type = raw_update.get("type")
                print(f"Тип события: {event_type}")
                try:
                    await bot.router.route(raw_update, bot.api)
                except Exception as e:
                    print(f"Ошибка роутинга: {type(e).__name__}: {e}")

    asyncio.run(main())