import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from config import config
from database import init_db
from handlers.start import router as start_router
from handlers.cars import router as cars_router
from handlers.fuel import router as fuel_router
from handlers.maintenance import router as maintenance_router
from handlers.reports import router as reports_router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger(__name__)

async def main():
    # Проверяем наличие токена
    BOT_TOKEN = config.BOT_TOKEN or os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не найден в переменных окружения!")
        logger.info("Добавьте BOT_TOKEN в Railway Variables или в .env файл")
        return

    # Инициализация базы данных
    try:
        init_db()
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
        return

    # Инициализация бота
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="Markdown")
    )
    
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Подключаем все роутеры
    dp.include_router(start_router)
    dp.include_router(cars_router)
    dp.include_router(fuel_router)
    dp.include_router(maintenance_router)
    dp.include_router(reports_router)

    # Удаляем вебхук (на случай если был установлен)
    await bot.delete_webhook(drop_pending_updates=True)
    
    logger.info("🚀 CarWise Bot запущен на Railway!")
    
    # Запуск поллинга
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
