import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
from sqlalchemy import and_, or_
from sqlalchemy.orm import selectinload

from config import config
from database import SessionLocal, init_db, Insurance, Car, User, Part, Admin, BannedUser

# Импорты роутеров (без vin_router)
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
from handlers.monthly_reports import send_monthly_reports
from handlers.payment import router as payment_router
from handlers.admin import router as admin_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger(__name__)

# ------------------- Вспомогательная функция для проверки бана -------------------
async def is_user_banned(user_id: int) -> bool:
    with SessionLocal() as db:
        banned = db.query(BannedUser).filter(BannedUser.telegram_id == user_id).first()
        return banned is not None

# ------------------- Функции для планировщика -------------------
async def check_insurances(bot: Bot):
    logger.info("🔍 Проверка сроков страховок...")
    try:
        with SessionLocal() as db:
            today = datetime.utcnow().date()
            # Загружаем страховки, которые истекают в ближайшие 7 дней, с автомобилями и владельцами
            insurances = db.query(Insurance).options(
                selectinload(Insurance.car).selectinload(Car.owner)
            ).filter(
                and_(
                    Insurance.end_date <= today + timedelta(days=7),
                    Insurance.end_date > today
                )
            ).all()

            for ins in insurances:
                car = ins.car
                if not car or not car.owner:
                    continue
                user_id = car.owner.telegram_id
                if await is_user_banned(user_id):
                    continue

                days_left = (ins.end_date.date() - today).days

                if days_left <= 7 and not ins.notified_7d:
                    await bot.send_message(
                        user_id,
                        f"⚠️ Напоминание о страховке!\n\n"
                        f"Автомобиль: {car.brand} {car.model}\n"
                        f"Срок действия истекает через {days_left} дн. ({ins.end_date.strftime('%d.%m.%Y')}).\n"
                        f"Не забудьте продлить."
                    )
                    ins.notified_7d = True
                    db.commit()
                    logger.info(f"Уведомление за 7 дней отправлено пользователю {user_id}")

            # Проверка на 3 дня
            insurances_3d = db.query(Insurance).options(
                selectinload(Insurance.car).selectinload(Car.owner)
            ).filter(
                and_(
                    Insurance.end_date <= today + timedelta(days=3),
                    Insurance.end_date > today
                )
            ).all()
            for ins in insurances_3d:
                car = ins.car
                if not car or not car.owner:
                    continue
                user_id = car.owner.telegram_id
                if await is_user_banned(user_id):
                    continue

                days_left = (ins.end_date.date() - today).days
                if days_left <= 3 and not ins.notified_3d:
                    await bot.send_message(
                        user_id,
                        f"⚠️⚠️ СРОЧНО! Страховка на {car.brand} {car.model} "
                        f"истекает через {days_left} дн. ({ins.end_date.strftime('%d.%m.%Y')}).\n"
                        f"Продлите полис, чтобы избежать проблем."
                    )
                    ins.notified_3d = True
                    db.commit()
                    logger.info(f"Уведомление за 3 дня отправлено пользователю {user_id}")

            # Проверка на истекшие
            expired = db.query(Insurance).options(
                selectinload(Insurance.car).selectinload(Car.owner)
            ).filter(
                Insurance.end_date <= today
            ).all()
            for ins in expired:
                car = ins.car
                if not car or not car.owner:
                    continue
                user_id = car.owner.telegram_id
                if await is_user_banned(user_id):
                    continue

                if not ins.notified_expired:
                    await bot.send_message(
                        user_id,
                        f"❗️ СРОК СТРАХОВКИ ИСТЁК!\n\n"
                        f"Автомобиль: {car.brand} {car.model}\n"
                        f"Страховка закончилась {ins.end_date.strftime('%d.%m.%Y')}.\n"
                        f"Необходимо приобрести новый полис."
                    )
                    ins.notified_expired = True
                    db.commit()
                    logger.info(f"Уведомление об истечении отправлено пользователю {user_id}")
    except Exception as e:
        logger.exception(f"Ошибка в check_insurances: {e}")

async def check_maintenance_reminders(bot: Bot):
    logger.info("🔧 Проверка сроков ТО...")
    try:
        with SessionLocal() as db:
            today = datetime.utcnow().date()
            cars = db.query(Car).options(selectinload(Car.owner)).filter(Car.is_active == True).all()
            for car in cars:
                if not car.owner:
                    continue
                user_id = car.owner.telegram_id
                if await is_user_banned(user_id):
                    continue

                if car.to_mileage_interval and car.last_maintenance_mileage is not None:
                    next_mileage = car.last_maintenance_mileage + car.to_mileage_interval
                    if car.current_mileage >= next_mileage and not car.notified_to_mileage:
                        await bot.send_message(
                            user_id,
                            f"⚠️ Напоминание о ТО по пробегу!\n\n"
                            f"Автомобиль: {car.brand} {car.model}\n"
                            f"Пробег: {car.current_mileage:,.0f} км\n"
                            f"Последнее ТО было при пробеге {car.last_maintenance_mileage:,.0f} км.\n"
                            f"Интервал: {car.to_mileage_interval:,.0f} км.\n"
                            f"Рекомендуется пройти ТО."
                        )
                        car.notified_to_mileage = True
                        db.commit()
                        logger.info(f"Уведомление о ТО по пробегу отправлено пользователю {user_id}")

                if car.to_months_interval and car.last_maintenance_date is not None:
                    next_date = car.last_maintenance_date + timedelta(days=30 * car.to_months_interval)
                    days_left = (next_date.date() - today).days
                    if days_left <= 0 and not car.notified_to_date:
                        await bot.send_message(
                            user_id,
                            f"⚠️ Напоминание о ТО по времени!\n\n"
                            f"Автомобиль: {car.brand} {car.model}\n"
                            f"Последнее ТО было {car.last_maintenance_date.strftime('%d.%m.%Y')}.\n"
                            f"Интервал: {car.to_months_interval} мес.\n"
                            f"Рекомендуется пройти ТО."
                        )
                        car.notified_to_date = True
                        db.commit()
                        logger.info(f"Уведомление о ТО по дате отправлено пользователю {user_id}")
    except Exception as e:
        logger.exception(f"Ошибка в check_maintenance_reminders: {e}")

async def check_parts_reminders(bot: Bot):
    logger.info("🔧 Проверка сроков замены деталей...")
    try:
        with SessionLocal() as db:
            today = datetime.utcnow().date()
            # Загружаем детали с автомобилями и владельцами
            parts = db.query(Part).options(
                selectinload(Part.car).selectinload(Car.owner)
            ).all()
            for part in parts:
                car = part.car
                if not car or not car.owner:
                    continue
                user_id = car.owner.telegram_id
                if await is_user_banned(user_id):
                    continue

                need_notify = False
                reasons = []

                if part.interval_mileage and part.last_mileage is not None:
                    next_mileage = part.last_mileage + part.interval_mileage
                    if car.current_mileage >= next_mileage and not part.notified:
                        need_notify = True
                        reasons.append("пробег")
                if part.interval_months and part.last_date is not None:
                    next_date = part.last_date + timedelta(days=30 * part.interval_months)
                    if next_date.date() <= today and not part.notified:
                        need_notify = True
                        reasons.append("время")

                if need_notify:
                    await bot.send_message(
                        user_id,
                        f"⚠️ Напоминание о замене детали!\n\n"
                        f"Автомобиль: {car.brand} {car.model}\n"
                        f"Деталь: {part.name}\n"
                        f"Причина: истёк интервал по {', '.join(reasons)}.\n"
                        f"Рекомендуется заменить."
                    )
                    part.notified = True
                    db.commit()
                    logger.info(f"Уведомление о детали '{part.name}' отправлено пользователю {user_id}")
    except Exception as e:
        logger.exception(f"Ошибка в check_parts_reminders: {e}")

async def send_seasonal_reminders(bot: Bot):
    logger.info("🌦️ Проверка сезонных напоминаний...")
    # Заглушка
    pass

async def main():
    BOT_TOKEN = config.BOT_TOKEN
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не найден в переменных окружения!")
        return

    try:
        init_db()
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
        return

    # Синхронизация администраторов из config в БД
    try:
        with SessionLocal() as db:
            for aid in config.ADMIN_IDS:
                admin = db.query(Admin).filter(Admin.telegram_id == aid).first()
                if not admin:
                    new_admin = Admin(telegram_id=aid, added_by=0)
                    db.add(new_admin)
            db.commit()
            logger.info(f"Синхронизировано {len(config.ADMIN_IDS)} администраторов из config")
    except Exception as e:
        logger.error(f"Ошибка синхронизации администраторов: {e}")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode='Markdown')  # Установлен Markdown
    )
    
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Подключаем все роутеры (без vin_router)
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

    # Удаляем вебхук
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Настройка планировщика
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_insurances, 'cron', hour=10, minute=0, args=(bot,))
    scheduler.add_job(check_maintenance_reminders, 'cron', hour=9, minute=0, args=(bot,))
    scheduler.add_job(check_parts_reminders, 'cron', hour=8, minute=0, args=(bot,))
    scheduler.add_job(send_seasonal_reminders, 'cron', hour=12, minute=0, args=(bot,))
    scheduler.add_job(send_monthly_reports, 'cron', hour=10, minute=0, args=(bot,))
    scheduler.start()
    logger.info("⏰ Планировщик напоминаний запущен")

    logger.info("🚀 CarWise Bot запущен на Railway!")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
