import asyncio
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import config
from database import init_db
from handlers import *  # все ваши роутеры

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация
bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode='Markdown')
)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Подключаем все роутеры
dp.include_router(start_router)
dp.include_router(cars_router)
# ... все остальные

# URL для вебхука
WEBHOOK_PATH = f"/webhook/{config.BOT_TOKEN}"
WEBHOOK_URL = os.getenv("WEBHOOK_URL") + WEBHOOK_PATH  # WEBHOOK_URL вы зададите позже

async def on_startup():
    """Действия при старте функции"""
    await bot.set_webhook(WEBHOOK_URL)
    init_db()
    logger.info(f"Бот запущен, вебхук установлен на {WEBHOOK_URL}")

async def on_shutdown():
    """Действия при остановке"""
    await bot.delete_webhook()
    await bot.session.close()

async def main(request):
    """Точка входа для Yandex Cloud Functions"""
    # Обрабатываем запрос от Telegram
    return await dp.feed_webhook(bot, request)

# Создаём приложение aiohttp
app = web.Application()
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

# Подключаем обработчик вебхуков
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
setup_application(app, dp, bot=bot)

if __name__ == "__main__":
    # Локально можно запустить для теста
    web.run_app(app, host="0.0.0.0", port=8080)
