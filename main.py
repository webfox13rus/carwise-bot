import asyncio
import logging
import logging.handlers
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
from sqlalchemy import and_
from sqlalchemy.orm import selectinload

from config import config
from database import SessionLocal, init_db, Insurance, Car, User, Part, Admin, BannedUser

# Импорты всех роутеров
from handlers.start import router as start_router
from handlers.cars import router as cars_router
from handlers.fuel import router as fuel_router
from handlers.maintenance import router as maintenance_router
from handlers.reports import router as reports_router
from handlers.insurance import router as insurance_router
from handlers.reminders import router as reminders_router
from handlers.parts import router as parts_router
from handlers.export import router as export_router
from handlers.edit import router as edit_router
from handlers.photos import router as photos_router
from handlers.feedback import router as feedback_router
from handlers.feedback_admin import router as feedback_admin_router
from handlers.navigation import router as navigation_router
from handlers.ai_advice import router as ai_advice_router
from handlers.monthly_reports import router as monthly_reports_router
from handlers.payment import router as payment_router
from handlers.admin import router as admin_router

# Импорт функций планировщика из отдельного модуля
from handlers.scheduler_functions import (
    check_insurances,
    check_maintenance_reminders,
    check_parts_reminders,
    send_monthly_reports
)

# ------------------- Настройка логирования -------------------
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
date_format = "%Y-%m-%d %H:%M:%S"

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Консольный обработчик
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(log_format, date_format))
logger.addHandler(console_handler)

# Файловый обработчик с ротацией (10 МБ, 5 бэкапов)
file_handler = logging.handlers.RotatingFileHandler(
    'carwise.log', maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter(log_format, date_format))
logger.addHandler(file_handler)

# ------------------- Точка входа -------------------
async def main():
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не найден!")
        return

    try:
        init_db()
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
        return

    # Синхронизация администраторов
    try:
        with SessionLocal() as db:
            for aid in config.ADMIN_IDS:
                admin = db.query(Admin).filter(Admin.telegram_id == aid).first()
                if not admin:
                    new_admin = Admin(telegram_id=aid, added_by=0)
                    db.add(new_admin)
            db.commit()
            logger.info(f"Синхронизировано {len(config.ADMIN_IDS)} администраторов")
    except Exception as e:
        logger.error(f"Ошибка синхронизации администраторов: {e}")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode='Markdown')
    )
    
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Подключаем роутеры
    dp.include_router(navigation_router)
    dp.include_router(start_router)
    dp.include_router(cars_router)
    dp.include_router(fuel_router)
    dp.include_router(maintenance_router)
    dp.include_router(reports_router)
    dp.include_router(insurance_router)
    dp.include_router(reminders_router)
    dp.include_router(parts_router)
    dp.include_router(export_router)
    dp.include_router(edit_router)
    dp.include_router(photos_router)
    dp.include_router(feedback_router)
    dp.include_router(feedback_admin_router)
    dp.include_router(ai_advice_router)
    dp.include_router(monthly_reports_router)
    dp.include_router(payment_router)
    dp.include_router(admin_router)

    # Удаляем вебхук (если был установлен ранее)
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Настройка планировщика
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_insurances, 'cron', hour=10, minute=0, args=(bot,))
    scheduler.add_job(check_maintenance_reminders, 'cron', hour=9, minute=0, args=(bot,))
    scheduler.add_job(check_parts_reminders, 'cron', hour=8, minute=0, args=(bot,))
    scheduler.add_job(send_monthly_reports, 'cron', hour=10, minute=0, args=(bot,))
    scheduler.start()
    logger.info("⏰ Планировщик напоминаний запущен")

    logger.info("🚀 CarWise Bot запущен на Railway!")
    
    # Запуск polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
