import asyncio
import logging
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

# Импорты всех роутеров (убедитесь, что все файлы существуют в папке handlers)
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger(__name__)

# Функция проверки бана
async def is_user_banned(user_id: int) -> bool:
    with SessionLocal() as db:
        banned = db.query(BannedUser).filter(BannedUser.telegram_id == user_id).first()
        return banned is not None

# Функции планировщика (сокращены для читаемости, оставьте свои реализации)
async def check_insurances(bot: Bot):
    logger.info("🔍 Проверка сроков страховок...")
    try:
        with SessionLocal() as db:
            today = datetime.utcnow().date()
            # ... ваш код ...
    except Exception as e:
        logger.exception(f"Ошибка в check_insurances: {e}")

async def check_maintenance_reminders(bot: Bot):
    logger.info("🔧 Проверка сроков ТО...")
    try:
        with SessionLocal() as db:
            today = datetime.utcnow().date()
            # ... ваш код ...
    except Exception as e:
        logger.exception(f"Ошибка в check_maintenance_reminders: {e}")

async def check_parts_reminders(bot: Bot):
    logger.info("🔧 Проверка сроков замены деталей...")
    try:
        with SessionLocal() as db:
            today = datetime.utcnow().date()
            # ... ваш код ...
    except Exception as e:
        logger.exception(f"Ошибка в check_parts_reminders: {e}")

async def send_monthly_reports(bot: Bot):
    logger.info("📅 Проверка ежемесячных отчётов...")
    try:
        # ... ваш код ...
    except Exception as e:
        logger.exception(f"Ошибка в send_monthly_reports: {e}")

# Команда для пинга (чтобы бот не засыпал)
from aiogram.types import Message
from aiogram.filters import Command

@router.message(Command("ping"))
async def cmd_ping(message: Message):
    await message.answer("pong")

async def main():
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не найден в переменных окружения!")
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

    # Настройка планировщика
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_insurances, 'cron', hour=10, minute=0, args=(bot,))
    scheduler.add_job(check_maintenance_reminders, 'cron', hour=9, minute=0, args=(bot,))
    scheduler.add_job(check_parts_reminders, 'cron', hour=8, minute=0, args=(bot,))
    scheduler.add_job(send_monthly_reports, 'cron', hour=10, minute=0, args=(bot,))
    scheduler.start()
    logger.info("⏰ Планировщик напоминаний запущен")

    # Удаляем вебхук (на случай, если был установлен ранее) – при serverless это не обязательно, но безопасно
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запускаем polling (для serverless этот режим не подойдёт, но для отладки оставим; позже перейдём на webhook)
    # Однако для Яндекс.Cloud Functions мы должны использовать вебхук. Пока оставим polling для локального теста,
    # но для деплоя нужно будет закомментировать polling и раскомментировать код вебхука.
    # Ниже приведён код для вебхука, который нужно будет активировать.

    # # Для работы в Яндекс.Cloud Functions раскомментируйте следующий блок:
    # from aiohttp import web
    # from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
    # 
    # WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
    # WEBHOOK_URL = os.getenv("WEBHOOK_URL") + WEBHOOK_PATH
    # 
    # async def on_startup():
    #     await bot.set_webhook(WEBHOOK_URL)
    # 
    # async def on_shutdown():
    #     await bot.delete_webhook()
    # 
    # app = web.Application()
    # app.on_startup.append(on_startup)
    # app.on_shutdown.append(on_shutdown)
    # SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    # setup_application(app, dp, bot=bot)
    # 
    # # Запуск aiohttp сервера
    # port = int(os.getenv("PORT", 8080))
    # web.run_app(app, host="0.0.0.0", port=port)

    # Пока оставляем polling для локального тестирования (не для продакшена!)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
