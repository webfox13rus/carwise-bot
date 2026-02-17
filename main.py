import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # новый импорт
from datetime import datetime, timedelta
import os

from config import config
from database import init_db, SessionLocal, Insurance, Car, User  # добавили SessionLocal, Insurance
from handlers.start import router as start_router
from handlers.cars import router as cars_router
from handlers.fuel import router as fuel_router
from handlers.maintenance import router as maintenance_router
from handlers.reports import router as reports_router
from handlers.insurance import router as insurance_router  # новый роутер

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger(__name__)

# Функция для проверки страховок и отправки напоминаний
async def check_insurances(bot: Bot):
    logger.info("🔍 Проверка сроков страховок...")
    with SessionLocal() as db:
        today = datetime.now().date()
        insurances = db.query(Insurance).all()
        for ins in insurances:
            days_left = (ins.end_date.date() - today).days
            car = ins.car
            user_id = car.user.telegram_id

            # Напоминание за 7 дней
            if days_left <= 7 and not ins.notified_7d:
                try:
                    await bot.send_message(
                        user_id,
                        f"⚠️ Напоминание о страховке!\n\n"
                        f"Автомобиль: {car.brand} {car.model}\n"
                        f"Срок действия истекает через {days_left} дней ({ins.end_date.strftime('%d.%m.%Y')}).\n"
                        f"Не забудьте продлить."
                    )
                    ins.notified_7d = True
                    db.commit()
                    logger.info(f"Уведомление за 7 дней отправлено пользователю {user_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления (7 дней): {e}")

            # Напоминание за 3 дня (если ещё не отправляли)
            elif days_left <= 3 and not ins.notified_3d:
                try:
                    await bot.send_message(
                        user_id,
                        f"⚠️⚠️ СРОЧНО! Страховка на {car.brand} {car.model} "
                        f"истекает через {days_left} дней ({ins.end_date.strftime('%d.%m.%Y')}).\n"
                        f"Продлите полис, чтобы избежать проблем."
                    )
                    ins.notified_3d = True
                    db.commit()
                    logger.info(f"Уведомление за 3 дня отправлено пользователю {user_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления (3 дня): {e}")

async def main():
    # Проверяем токен
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
        default=DefaultBotProperties(parse_mode=None)  # без Markdown
    )
    
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Подключаем все роутеры
    dp.include_router(start_router)
    dp.include_router(cars_router)
    dp.include_router(fuel_router)
    dp.include_router(maintenance_router)
    dp.include_router(reports_router)
    dp.include_router(insurance_router)  # новый роутер

    # Удаляем вебхук
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Настройка планировщика
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_insurances, 'cron', hour=10, minute=0, args=(bot,))  # каждый день в 10:00 UTC
    scheduler.start()
    logger.info("⏰ Планировщик напоминаний запущен (ежедневно в 10:00 UTC)")

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
