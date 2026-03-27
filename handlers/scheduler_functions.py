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

async def check_maintenance_reminders(bot):
    logger.info("🔧 Проверка сроков ТО...")
    try:
        with SessionLocal() as db:
            today = datetime.utcnow().date()
            cars = db.query(Car).options(selectinload(Car.owner)).filter(
                Car.is_active == True,
                (Car.to_mileage_interval != None) | (Car.to_months_interval != None)
            ).all()
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

async def check_parts_reminders(bot):
    logger.info("🔧 Проверка сроков замены деталей...")
    try:
        with SessionLocal() as db:
            today = datetime.utcnow().date()
            parts = db.query(Part).options(
                selectinload(Part.car).selectinload(Car.owner)
            ).filter(
                (Part.interval_mileage != None) | (Part.interval_months != None),
                Part.notified == False
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
                    if car.current_mileage >= next_mileage:
                        need_notify = True
                        reasons.append("пробег")
                if part.interval_months and part.last_date is not None:
                    next_date = part.last_date + timedelta(days=30 * part.interval_months)
                    if next_date.date() <= today:
                        need_notify = True
                        reasons.append("время")

                if need_notify:
                    await bot.send_message(
                        user_id,
                        f"⚠️ Напоминание о замене детали!\n\n"
                        f"Автомобиль: {car.brand} {car.model}\n"
                        f"Деталь/жидкость: {part.name}\n"
                        f"Причина: истёк интервал по {', '.join(reasons)}.\n"
                        f"Рекомендуется заменить."
                    )
                    part.notified = True
                    db.commit()
                    logger.info(f"Уведомление о детали '{part.name}' отправлено пользователю {user_id}")
    except Exception as e:
        logger.exception(f"Ошибка в check_parts_reminders: {e}")

async def send_monthly_reports(bot):
    logger.info("📅 Ежемесячные отчёты...")
    try:
        # Здесь будет логика отправки отчётов (можно оставить заглушку)
        pass
    except Exception as e:
        logger.exception(f"Ошибка в send_monthly_reports: {e}")
