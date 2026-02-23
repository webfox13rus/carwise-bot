import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import os

# Импортируем конфигурацию и функции работы с БД
from config import config
from database import init_db, SessionLocal, Insurance, Car, User, Part
# Импортируем все роутеры (обработчики команд)
from handlers.export import router as export_router
from handlers.start import router as start_router
from handlers.cars import router as cars_router
from handlers.fuel import router as fuel_router
from handlers.maintenance import router as maintenance_router
from handlers.reports import router as reports_router
from handlers.insurance import router as insurance_router
from handlers.reminders import router as reminders_router
from handlers.parts import router as parts_router   # новый роутер для деталей

# Настройка логирования (вывод в консоль с временем и уровнем)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger(__name__)

# ------------------- Функции для планировщика (уведомления) -------------------

async def check_insurances(bot: Bot):
    """Проверка сроков страховок и отправка уведомлений (за 7 дней, 3 дня, при истечении)."""
    logger.info("🔍 Проверка сроков страховок...")
    with SessionLocal() as db:
        today = datetime.now().date()
        insurances = db.query(Insurance).all()
        for ins in insurances:
            days_left = (ins.end_date.date() - today).days
            car = ins.car
            if not car or not car.owner:
                continue
            user_id = car.owner.telegram_id

            # За 7 дней (если ещё не уведомляли)
            if 0 < days_left <= 7 and not ins.notified_7d:
                try:
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
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления (7 дней): {e}")

            # За 3 дня
            elif 0 < days_left <= 3 and not ins.notified_3d:
                try:
                    await bot.send_message(
                        user_id,
                        f"⚠️⚠️ СРОЧНО! Страховка на {car.brand} {car.model} "
                        f"истекает через {days_left} дн. ({ins.end_date.strftime('%d.%m.%Y')}).\n"
                        f"Продлите полис, чтобы избежать проблем."
                    )
                    ins.notified_3d = True
                    db.commit()
                    logger.info(f"Уведомление за 3 дня отправлено пользователю {user_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления (3 дня): {e}")

            # После истечения
            elif days_left <= 0 and not ins.notified_expired:
                try:
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
                    logger.error(f"Ошибка отправки уведомления об истечении: {e}")

async def check_maintenance_reminders(bot: Bot):
    """Проверка необходимости ТО по пробегу и по дате последнего ТО."""
    logger.info("🔧 Проверка сроков ТО...")
    with SessionLocal() as db:
        today = datetime.now().date()
        cars = db.query(Car).filter(Car.is_active == True).all()
        for car in cars:
            if not car.owner:
                continue
            user_id = car.owner.telegram_id

            # Проверка по пробегу
            if car.to_mileage_interval and car.last_maintenance_mileage is not None:
                next_mileage = car.last_maintenance_mileage + car.to_mileage_interval
                if car.current_mileage >= next_mileage and not car.notified_to_mileage:
                    try:
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
                    except Exception as e:
                        logger.error(f"Ошибка отправки уведомления о ТО (пробег): {e}")

            # Проверка по дате
            if car.to_months_interval and car.last_maintenance_date is not None:
                next_date = car.last_maintenance_date + timedelta(days=30 * car.to_months_interval)
                days_left = (next_date.date() - today).days
                if days_left <= 0 and not car.notified_to_date:
                    try:
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
                        logger.error(f"Ошибка отправки уведомления о ТО (дата): {e}")

async def check_parts_reminders(bot: Bot):
    """Проверка сроков замены деталей (интервалы по пробегу и времени)."""
    logger.info("🔧 Проверка сроков замены деталей...")
    with SessionLocal() as db:
        today = datetime.now().date()
        parts = db.query(Part).all()
        for part in parts:
            car = part.car
            if not car or not car.owner:
                continue
            user_id = car.owner.telegram_id
            need_notify = False
            reasons = []

            # Проверка по пробегу
            if part.interval_mileage and part.last_mileage is not None:
                next_mileage = part.last_mileage + part.interval_mileage
                if car.current_mileage >= next_mileage and not part.notified:
                    need_notify = True
                    reasons.append("пробег")
            # Проверка по времени
            if part.interval_months and part.last_date is not None:
                next_date = part.last_date + timedelta(days=30 * part.interval_months)
                if next_date.date() <= today and not part.notified:
                    need_notify = True
                    reasons.append("время")

            if need_notify:
                try:
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
                    logger.error(f"Ошибка отправки уведомления о детали: {e}")

# ------------------- Основная функция запуска бота -------------------
async def main():
    # Получаем токен бота из переменных окружения (или из config)
    BOT_TOKEN = config.BOT_TOKEN or os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не найден в переменных окружения!")
        logger.info("Добавьте BOT_TOKEN в Railway Variables или в .env файл")
        return

    # Инициализация базы данных (создание таблиц, если их нет)
    try:
        init_db()
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
        return

    # Создаём экземпляр бота (отключаем встроенный parse_mode, чтобы избежать ошибок с Markdown)
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=None)
    )
    
    # Хранилище состояний FSM (в оперативной памяти)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Подключаем все обработчики (роутеры)
    dp.include_router(start_router)          # /start, /help
    dp.include_router(cars_router)           # управление автомобилями
    dp.include_router(fuel_router)           # заправки
    dp.include_router(maintenance_router)    # обслуживание (с категориями и запчастями)
    dp.include_router(reports_router)        # статистика
    dp.include_router(insurance_router)      # страховки
    dp.include_router(reminders_router)      # настройка напоминаний ТО
    dp.include_router(parts_router)          # отчёт по деталям (кнопка "🔧 Детали")
    dp.include_router(export_router)

    # Удаляем возможный вебхук (чтобы не мешал поллингу)
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Настройка планировщика задач (apscheduler)
    scheduler = AsyncIOScheduler()
    # Добавляем задания на каждый день в определённое время (UTC)
    scheduler.add_job(check_insurances, 'cron', hour=10, minute=0, args=(bot,))
    scheduler.add_job(check_maintenance_reminders, 'cron', hour=9, minute=0, args=(bot,))
    scheduler.add_job(check_parts_reminders, 'cron', hour=8, minute=0, args=(bot,))  # новая проверка деталей
    scheduler.start()
    logger.info("⏰ Планировщик напоминаний запущен (страховки 10:00, ТО 9:00, детали 8:00 UTC)")

    logger.info("🚀 CarWise Bot запущен на Railway!")
    
    # Запуск поллинга (бесконечный цикл получения обновлений)
    await dp.start_polling(bot)

# ------------------- Точка входа -------------------
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
