import logging
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.filters import Command
from sqlalchemy import func

from database import SessionLocal, Car, FuelEvent, MaintenanceEvent, User, Insurance, Part
from keyboards.main_menu import get_stats_submenu
from config import config

router = Router()
logger = logging.getLogger(__name__)

# Функция для получения краткой статистики по всем авто пользователя
def get_short_stats(db, user_id):
    cars = db.query(Car).filter(Car.user_id == user_id, Car.is_active == True).all()
    total_fuel = 0
    total_maintenance = 0
    total_mileage = 0
    details = []

    for car in cars:
        fuel = db.query(func.sum(FuelEvent.cost)).filter(FuelEvent.car_id == car.id).scalar() or 0
        maint = db.query(func.sum(MaintenanceEvent.cost)).filter(MaintenanceEvent.car_id == car.id).scalar() or 0
        total_fuel += fuel
        total_maintenance += maint
        total_mileage += car.current_mileage
        details.append({
            "name": f"{car.brand} {car.model}",
            "fuel": fuel,
            "maint": maint,
            "mileage": car.current_mileage
        })
    return {
        "total_fuel": total_fuel,
        "total_maintenance": total_maintenance,
        "total_mileage": total_mileage,
        "cars": details
    }

# Функция для получения детальной статистики (расширенной)
def get_detailed_stats(db, user_id):
    cars = db.query(Car).filter(Car.user_id == user_id, Car.is_active == True).all()
    result = []
    for car in cars:
        # Расход топлива за последние 10 заправок
        fuel_events = db.query(FuelEvent).filter(FuelEvent.car_id == car.id).order_by(FuelEvent.date.desc()).limit(10).all()
        if len(fuel_events) >= 2:
            total_liters = sum(ev.liters for ev in fuel_events if ev.liters)
            total_distance = 0
            prev = None
            for ev in sorted(fuel_events, key=lambda x: x.date):
                if prev and ev.mileage and prev.mileage and ev.mileage > prev.mileage:
                    total_distance += ev.mileage - prev.mileage
                prev = ev
            avg_consumption = (total_liters / total_distance * 100) if total_distance > 0 else 0
        else:
            avg_consumption = 0

        # Страховка (ближайшая)
        insurances = db.query(Insurance).filter(Insurance.car_id == car.id).all()
        if insurances:
            nearest_ins = min(insurances, key=lambda x: x.end_date)
            insurance_expiry = nearest_ins.end_date.strftime('%d.%m.%Y')
            days_left = (nearest_ins.end_date.date() - datetime.utcnow().date()).days
        else:
            insurance_expiry = "не оформлена"
            days_left = "—"

        # Предстоящие замены деталей
        parts = db.query(Part).filter(Part.car_id == car.id).all()
        upcoming_parts = []
        for part in parts:
            if part.interval_mileage and part.last_mileage:
                next_mileage = part.last_mileage + part.interval_mileage
                remaining_mileage = next_mileage - car.current_mileage
                if remaining_mileage > 0 and remaining_mileage < 10000:
                    upcoming_parts.append(f"{part.name} (осталось {remaining_mileage:,.0f} км)")
            if part.interval_months and part.last_date:
                next_date = part.last_date + timedelta(days=30 * part.interval_months)
                days_left_part = (next_date.date() - datetime.utcnow().date()).days
                if days_left_part > 0 and days_left_part < 90:
                    upcoming_parts.append(f"{part.name} (осталось {days_left_part} дн.)")
        upcoming = ", ".join(upcoming_parts) if upcoming_parts else "нет"

        result.append({
            "car": f"{car.brand} {car.model} ({car.year})",
            "mileage": f"{car.current_mileage:,.0f} км",
            "avg_consumption": f"{avg_consumption:.1f} л/100км" if avg_consumption else "нет данных",
            "insurance": insurance_expiry,
            "days_left": days_left,
            "upcoming": upcoming
        })
    return result

@router.message(F.text == "📊 Краткая статистика")
async def short_stats(message: types.Message):
    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь, отправив /start")
            return
        stats = get_short_stats(db, user.id)
        if not stats["cars"]:
            await message.answer("У вас нет автомобилей.", reply_markup=get_stats_submenu())
            return
        text = "📊 *Краткая статистика*\n\n"
        for car in stats["cars"]:
            text += f"🚗 {car['name']}\n"
            text += f"  Пробег: {car['mileage']:,.0f} км\n"
            text += f"  Топливо: {car['fuel']:,.2f} ₽\n"
            text += f"  Обслуживание: {car['maint']:,.2f} ₽\n\n"
        text += f"*Итого по всем авто:*\n"
        text += f"⛽ Топливо: {stats['total_fuel']:,.2f} ₽\n"
        text += f"🔧 Обслуживание: {stats['total_maintenance']:,.2f} ₽\n"
        text += f"💰 Всего: {stats['total_fuel'] + stats['total_maintenance']:,.2f} ₽\n"
        text += f"📏 Общий пробег: {stats['total_mileage']:,.0f} км"
        await message.answer(text, parse_mode="Markdown", reply_markup=get_stats_submenu())

@router.message(F.text == "📈 Детальная статистика")
async def detailed_stats(message: types.Message):
    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь, отправив /start")
            return
        stats = get_detailed_stats(db, user.id)
        if not stats:
            await message.answer("У вас нет автомобилей.", reply_markup=get_stats_submenu())
            return
        text = "📈 *Детальная статистика*\n\n"
        for car in stats:
            text += f"🚗 {car['car']}\n"
            text += f"  Пробег: {car['mileage']}\n"
            text += f"  Средний расход: {car['avg_consumption']}\n"
            text += f"  Страховка до: {car['insurance']}"
            if car['days_left'] != "—":
                text += f" (осталось {car['days_left']} дн.)\n"
            else:
                text += "\n"
            text += f"  Предстоящие замены: {car['upcoming']}\n\n"
        await message.answer(text, parse_mode="Markdown", reply_markup=get_stats_submenu())

@router.message(F.text == "📤 Экспорт данных (Premium)")
async def export_data(message: types.Message):
    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь, отправив /start")
            return
        if not user.is_premium and message.from_user.id not in config.ADMIN_IDS:
            await message.answer(
                "❌ *Экспорт данных* доступен только для премиум-пользователей.\n\n"
                "Оформите подписку, чтобы выгрузить все данные в CSV.",
                parse_mode="Markdown",
                reply_markup=get_stats_submenu()
            )
            return
        # Здесь будет логика экспорта (пока заглушка)
        await message.answer("Функция экспорта данных в разработке. Скоро будет доступна.", reply_markup=get_stats_submenu())
