import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
import os

# Локальный импорт для тестирования
try:
    from config import config
    from database import init_db
    from handlers.start import router as start_router
    from handlers.cars import router as cars_router
    from handlers.fuel import router as fuel_router
    from handlers.maintenance import router as maintenance_router
    from handlers.reports import router as reports_router
    HAS_MODULES = True
except ImportError as e:
    print(f"Модуль не найден: {e}")
    HAS_MODULES = False

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger(__name__)

async def main():
    # Проверяем токен
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не найден в переменных окружения!")
        logger.info("Добавьте BOT_TOKEN в Railway Variables")
        return
    
    # Инициализация базы данных (если модули есть)
    if HAS_MODULES:
        try:
            init_db()
            logger.info("✅ База данных инициализирована")
        except Exception as e:
            logger.error(f"❌ Ошибка БД: {e}")
    
    # Инициализация бота
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="Markdown")
    )
    
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Подключаем роутеры (если модули есть)
    if HAS_MODULES:
        dp.include_router(start_router)
        dp.include_router(cars_router)
        dp.include_router(fuel_router)
        dp.include_router(maintenance_router)
        dp.include_router(reports_router)
    else:
        # Минимальный роутер для теста
        from aiogram import types, F
        from aiogram.filters import Command
        
        @dp.message(Command("start"))
        async def cmd_start(message: types.Message):
            await message.answer(
                "🚗 *CarWise Bot запущен!*\n\n"
                "Пока доступны базовые функции.\n"
                "Используйте /help для списка команд.",
                parse_mode="Markdown"
            )
        
        @dp.message(Command("help"))
        async def cmd_help(message: types.Message):
            await message.answer(
                "*Помощь:*\n"
                "/start - начало\n"
                "/fuel - добавить заправку\n"
                "5000 45.5 - быстрая заправка",
                parse_mode="Markdown"
            )
        
        @dp.message(F.text.regexp(r'^(\d+)\s+(\d+(?:\.\d+)?)$'))
        async def quick_fuel(message: types.Message):
            parts = message.text.split()
            cost = float(parts[0])
            liters = float(parts[1])
            price = cost / liters
            
            await message.answer(
                f"⛽ *Заправка добавлена!*\n\n"
                f"Сумма: *{cost} ₽*\n"
                f"Литры: *{liters} л*\n"
                f"Цена за литр: *{price:.2f} ₽*",
                parse_mode="Markdown"
            )
    
    # Удаляем вебхук
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запуск бота
    logger.info("🚀 CarWise Bot запущен на Railway!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ Бот остановлен")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")