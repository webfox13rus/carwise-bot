import logging
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.filters import Command
from sqlalchemy import func
from decimal import Decimal

from database import SessionLocal, Car, FuelEvent, MaintenanceEvent, User, Insurance, Part
from keyboards.main_menu import get_stats_submenu
from config import config

router = Router()
logger = logging.getLogger(__name__)

# ------------------- Вспомогательные функции -------------------
def get_last_fuel_events(db, car_id, limit=3):
    events = db.query(FuelEvent).filter(FuelEvent.car_id == car_id).order_by(FuelEvent.date.desc()).limit(limit).all()
    result = []
    events_asc = sorted(events, key=lambda x: x.date)
    for i, ev in enumerate(events_asc):
        consumption = None
        if i > 0:
            prev = events_asc[i-1]
            if ev.mileage and prev.mileage and ev.mileage > prev.mileage:
                distance = ev.mileage - prev.mileage
                consumption = (float(ev.liters) / distance) * 100
        result.append({
            "date": ev.date.strftime('%d.%m.%Y'),
            "liters": float(ev.liters),
            "cost": float(ev.cost),
            "mileage": ev.mileage,
            "price_per_liter": float(ev.cost) / float(ev.liters) if ev.liters else 0,
            "consumption": consumption
        })
    return list(reversed(result))

def get_upcoming_parts(db, car_id):
    today = datetime.utcnow().date()
    parts = db.query(Part).filter(Part.car_id == car_id).all()
    upcoming = []
    for part in parts:
        reasons = []
        if part.interval_mileage and part.last_mileage is not None:
            next_mileage = part.last_mileage + part.interval_mileage
            remaining_km = next_mileage - part.car.current_mileage
            if remaining_km <= 0:
                reasons.append("⚠️ пора менять")
            elif remaining_km <= 10000:
                reasons.append(f"осталось {remaining_km:,.0f} км")
        if part.interval_months and part.last_date is not None:
            next_date = part.last_date + timedelta(days=30 * part.interval_months)
            days_left = (next_date.date() - today).days
            if days_left <= 0:
                reasons.append("⚠️ пора менять")
            elif days_left <= 90:
                reasons.append(f"осталось {days_left} дн.")
        if reasons:
            upcoming.append(f"• {part.name}: {', '.join(reasons)}")
    return upcoming

def get_insurance_info(db, car_id):
    ins = db.query(Insurance).filter(Insurance.car_id == car_id).order_by(Insurance.end_date.desc()).first()
    if not ins:
        return "не оформлена"
    today = datetime.utcnow().date()
    days_left = (ins.end_date.date() - today).days
    status = "⚠️ истекла" if days_left < 0 else f"✅ {days_left} дн."
    return f"{ins.company} (до {ins.end_date.strftime('%d.%m.%Y')}) – {status}"

def get_detailed_stats(db, user_id):
    cars = db.query(Car).filter(Car.user_id == user_id, Car.is_active == True).all()
    result = []
    for car in cars:
        total_fuel = db.query(func.sum(FuelEvent.cost)).filter(FuelEvent.car_id == car.id).scalar() or 0
        total_maint = db.query(func.sum(MaintenanceEvent.cost)).filter(MaintenanceEvent.car_id == car.id).scalar() or 0
        total_fuel = float(total_fuel) if isinstance(total_fuel, Decimal) else total_fuel
        total_maint = float(total_maint) if isinstance(total_maint, Decimal) else total_maint
        total_expenses = total_fuel + total_maint

        fuel_events = db.query(FuelEvent).filter(FuelEvent.car_id == car.id).order_by(FuelEvent.date.desc()).limit(10).all()
        avg_consumption = None
        if len(fuel_events) >= 2:
            sorted_events = sorted(fuel_events, key=lambda x: x.date)
            total_liters = 0
            total_distance = 0
            prev = None
            for ev in sorted_events:
                if prev and ev.mileage and prev.mileage and ev.mileage > prev.mileage:
                    total_distance += ev.mileage - prev.mileage
                    total_liters += ev.liters
                prev = ev
            if total_distance > 0:
                avg_consumption = (float(total_liters) / total_distance) * 100

        last_fuel = get_last_fuel_events(db, car.id)
        upcoming_parts = get_upcoming_parts(db, car.id)
        insurance_info = get_insurance_info(db, car.id)

        result.append({
            "car": f"{car.brand} {car.model} ({car.year})",
            "mileage": car.current_mileage,
            "total_fuel": total_fuel,
            "total_maint": total_maint,
            "total_expenses": total_expenses,
            "avg_consumption": avg_consumption,
            "last_fuel": last_fuel,
            "upcoming_parts": upcoming_parts,
            "insurance": insurance_info
        })
    return result

# ------------------- Обработчик статистики -------------------
@router.message(F.text == "📊 Статистика")
async def show_stats(message: types.Message):
    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь, отправив /start")
            return
        stats = get_detailed_stats(db, user.id)
        if not stats:
            await message.answer("У вас нет автомобилей.", reply_markup=get_stats_submenu())
            return
        text = "📊 *Статистика*\n\n"
        for car in stats:
            text += f"🚗 *{car['car']}*\n"
            text += f"📏 Пробег: {car['mileage']:,.0f} км\n"
            text += f"⛽ Всего топлива: {car['total_fuel']:,.2f} ₽\n"
            text += f"🔧 Всего обслуживания: {car['total_maint']:,.2f} ₽\n"
            text += f"💰 Всего расходов: {car['total_expenses']:,.2f} ₽\n"
            if car['avg_consumption']:
                text += f"📈 Средний расход: {car['avg_consumption']:.1f} л/100км\n"
            else:
                text += f"📈 Средний расход: недостаточно данных\n"

            if car['last_fuel']:
                text += f"\n*📝 Последние заправки:*\n"
                for ev in car['last_fuel']:
                    text += f"• {ev['date']}: {ev['liters']:.2f} л, {ev['cost']:.2f} ₽ (цена {ev['price_per_liter']:.2f} ₽/л)"
                    if ev['mileage']:
                        text += f", пробег {ev['mileage']:,.0f} км"
                    if ev['consumption']:
                        text += f", расход {ev['consumption']:.1f} л/100км"
                    text += "\n"
            else:
                text += f"\n*📝 Заправок пока нет.*\n"

            if car['upcoming_parts']:
                text += f"\n*🔧 Ближайшие замены:*\n"
                for item in car['upcoming_parts']:
                    text += f"{item}\n"
            else:
                text += f"\n*🔧 Ближайших замен нет.*\n"

            text += f"\n*📄 Страховка:* {car['insurance']}\n"
            text += "\n" + "─"*20 + "\n"

        await message.answer(text, parse_mode="Markdown", reply_markup=get_stats_submenu())
