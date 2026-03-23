import logging
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.filters import Command

from database import SessionLocal, Car, Part, User
from keyboards.main_menu import get_main_menu, get_maintenance_submenu

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text == "🔧 Плановые замены")
@router.message(Command("parts"))
async def show_parts(message: types.Message):
    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь", reply_markup=get_maintenance_submenu())
            return
        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("У вас нет автомобилей.", reply_markup=get_maintenance_submenu())
            return

        lines = ["🔧 *Плановые замены деталей и жидкостей*\n"]
        found = False
        today = datetime.utcnow().date()
        for car in cars:
            parts = db.query(Part).filter(Part.car_id == car.id).all()
            car_has_items = False
            for part in parts:
                reasons = []
                # Проверка по пробегу
                if part.interval_mileage and part.last_mileage is not None:
                    next_mileage = part.last_mileage + part.interval_mileage
                    if car.current_mileage >= next_mileage:
                        reasons.append("⚠️ пора менять")
                    else:
                        remaining = next_mileage - car.current_mileage
                        reasons.append(f"осталось {remaining:,.0f} км")
                # Проверка по дате
                if part.interval_months and part.last_date is not None:
                    next_date = part.last_date + timedelta(days=30 * part.interval_months)
                    days_left = (next_date.date() - today).days
                    if days_left <= 0:
                        reasons.append("⚠️ пора менять")
                    else:
                        reasons.append(f"осталось {days_left} дн.")
                if reasons:
                    if not car_has_items:
                        lines.append(f"🚗 *{car.brand} {car.model}*:")
                        car_has_items = True
                    lines.append(f"  • {part.name}: {', '.join(reasons)}")
                    found = True
            if car_has_items:
                lines.append("")  # пустая строка между авто

        if not found:
            lines.append("Все детали и жидкости в порядке, напоминаний нет.")
        await message.answer("\n".join(lines), parse_mode="Markdown", reply_markup=get_maintenance_submenu())
