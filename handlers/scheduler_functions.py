import logging
from datetime import datetime, timedelta
from sqlalchemy import and_
from sqlalchemy.orm import selectinload
from database import SessionLocal, Insurance, Car, User, Part, BannedUser
from config import config

logger = logging.getLogger(__name__)

async def is_user_banned(user_id: int) -> bool:
    with SessionLocal() as db:
        banned = db.query(BannedUser).filter(BannedUser.telegram_id == user_id).first()
        return banned is not None

async def check_insurances(bot):
    logger.info("🔍 Проверка сроков страховок...")
    try:
        with SessionLocal() as db:
            today = datetime.utcnow().date()
            # Загружаем только активные страховки, которые истекают в ближайшие 7 дней
            insurances = db.query(Insurance).options(
                selectinload(Insurance.car).selectinload(Car.owner)
            ).filter(
                Insurance.is_active == True,
                Insurance.end_date <= today + timedelta(days=7)
            ).all()

            for ins in insurances:
                car = ins.car
                if not car or not car.owner:
                    continue
                user_id = car.owner.telegram_id
                if await is_user_banned(user_id):
                    continue

                days_left = (ins.end_date.date() - today).days

                # Уведомление за 7 дней
                if 0 < days_left <= 7 and not ins.notified_7d:
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

                # Уведомление за 3 дня (если ещё не отправлено)
                elif 0 < days_left <= 3 and not ins.notified_3d:
                    await bot.send_message(
                        user_id,
                        f"⚠️⚠️ СРОЧНО! Страховка на {car.brand} {car.model} "
                        f"истекает через {days_left} дн. ({ins.end_date.strftime('%d.%m.%Y')}).\n"
                        f"Продлите полис, чтобы избежать проблем."
                    )
                    ins.notified_3d = True
                    db.commit()
                    logger.info(f"Уведомление за 3 дня отправлено пользователю {user_id}")

                # Уведомление о просрочке (если ещё не отправлено)
                elif days_left <= 0 and not ins.notified_expired:
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

# Остальные функции (check_maintenance_reminders, check_parts_reminders, send_monthly_reports) остаются без изменений.
