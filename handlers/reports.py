from aiogram import Router, types, F
from aiogram.filters import Command
from sqlalchemy import func
from datetime import datetime, timedelta
from database import get_db, Car, FuelEvent, MaintenanceEvent, User, Insurance, Part
from keyboards.main_menu import get_stats_submenu
from config import config

router = Router()

# ------------------- Краткая статистика -------------------
@router.message(F.text == "📊 Краткая статистика")
async def show_quick_stats(message: types.Message):
    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь, отправив /start")
            return

        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("У вас нет автомобилей.", reply_markup=get_stats_submenu())
            return

        total_fuel = 0
        total_maintenance = 0
        response_lines = ["📊 *Краткая статистика*\n"]

        for car in cars:
            fuel_sum = db.query(FuelEvent).filter(FuelEvent.car_id == car.id).with_entities(func.sum(FuelEvent.cost)).scalar() or 0
            maint_sum = db.query(MaintenanceEvent).filter(MaintenanceEvent.car_id == car.id).with_entities(func.sum(MaintenanceEvent.cost)).scalar() or 0
            total_fuel += fuel_sum
            total_maintenance += maint_sum
            response_lines.append(
                f"🚗 {car.brand} {car.model} ({car.year}):\n"
                f"  Пробег: {car.current_mileage:,.0f} км\n"
                f"  Топливо: {fuel_sum:,.2f} ₽\n"
                f"  Обслуживание: {maint_sum:,.2f} ₽"
            )

        response_lines.append(f"\n💰 *ИТОГО:*")
        response_lines.append(f"⛽ Топливо: {total_fuel:,.2f} ₽")
        response_lines.append(f"🔧 Обслуживание: {total_maintenance:,.2f} ₽")
        response_lines.append(f"💵 Всего: {total_fuel + total_maintenance:,.2f} ₽")

        await message.answer("\n".join(response_lines), parse_mode="Markdown", reply_markup=get_stats_submenu())

# ------------------- Детальная статистика -------------------
@router.message(F.text == "📈 Детальная статистика")
@router.message(Command("stats"))
async def show_detailed_stats(message: types.Message):
    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь, отправив /start")
            return

        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("У вас нет автомобилей.", reply_markup=get_stats_submenu())
            return

        total_all_fuel = 0
        total_all_maintenance = 0
        response_lines = ["📈 *Детальная статистика*\n"]

        for car in cars:
            response_lines.append(f"🚗 *{car.brand} {car.model} ({car.year})*")
            response_lines.append(f"Пробег: {car.current_mileage:,.0f} км")

            # Заправки по типам топлива
            fuel_stats = db.query(
                FuelEvent.fuel_type,
                func.sum(FuelEvent.liters).label('total_liters'),
                func.sum(FuelEvent.cost).label('total_cost')
            ).filter(FuelEvent.car_id == car.id).group_by(FuelEvent.fuel_type).all()

            car_fuel_total = 0
            if fuel_stats:
                response_lines.append("⛽ *Заправки по типам топлива:*")
                for fuel_type, liters, cost in fuel_stats:
                    if fuel_type is None:
                        type_name = "Не указан"
                    else:
                        type_name = config.DEFAULT_FUEL_TYPES.get(fuel_type, fuel_type)
                    response_lines.append(f"  • {type_name}: {liters:.2f} л – {cost:,.2f} ₽")
                    car_fuel_total += cost
                response_lines.append(f"  *Всего на топливо:* {car_fuel_total:,.2f} ₽")
            else:
                response_lines.append("⛽ *Нет заправок*")
            total_all_fuel += car_fuel_total

            # Обслуживание по категориям
            maint_stats = db.query(
                MaintenanceEvent.category,
                func.count(MaintenanceEvent.id).label('count'),
                func.sum(MaintenanceEvent.cost).label('total_cost')
            ).filter(MaintenanceEvent.car_id == car.id).group_by(MaintenanceEvent.category).all()

            car_maint_total = 0
            if maint_stats:
                response_lines.append("🔧 *Обслуживание по категориям:*")
                for category, count, cost in maint_stats:
                    cat_name = config.MAINTENANCE_CATEGORIES.get(category, category)
                    response_lines.append(f"  • {cat_name}: {count} раз(а) – {cost:,.2f} ₽")
                    car_maint_total += cost
                response_lines.append(f"  *Всего на обслуживание:* {car_maint_total:,.2f} ₽")
            else:
                response_lines.append("🔧 *Нет обслуживания*")
            total_all_maintenance += car_maint_total

            # Информация о страховке (ближайшая)
            insurances = db.query(Insurance).filter(Insurance.car_id == car.id).all()
            if insurances:
                sorted_ins = sorted(insurances, key=lambda x: x.end_date)
                nearest = sorted_ins[0]
                days_left = (nearest.end_date.date() - datetime.now().date()).days
                if days_left < 0:
                    status = "❗️Истекла"
                elif days_left <= 7:
                    status = f"⚠️Истекает через {days_left} дн."
                else:
                    status = f"✅Активна (осталось {days_left} дн.)"
                response_lines.append(f"📄 *Страховка:* до {nearest.end_date.strftime('%d.%m.%Y')} – {status}")
            else:
                response_lines.append("📄 *Страховка:* не добавлена")

            # Информация о следующем ТО
            next_to_parts = []
            if car.to_mileage_interval and car.last_maintenance_mileage is not None:
                next_mileage = car.last_maintenance_mileage + car.to_mileage_interval
                if car.current_mileage >= next_mileage:
                    next_to_parts.append("⚠️ по пробегу (нужно ТО!)")
                else:
                    remaining_km = next_mileage - car.current_mileage
                    next_to_parts.append(f"по пробегу через {remaining_km:,.0f} км")
            if car.to_months_interval and car.last_maintenance_date is not None:
                next_date = car.last_maintenance_date + timedelta(days=30 * car.to_months_interval)
                days_left = (next_date.date() - datetime.now().date()).days
                if days_left <= 0:
                    next_to_parts.append("⚠️ по дате (нужно ТО!)")
                else:
                    next_to_parts.append(f"по дате через {days_left} дн.")
            if next_to_parts:
                response_lines.append(f"⏰ *Следующее ТО:* {', '.join(next_to_parts)}")
            else:
                response_lines.append("⏰ *Следующее ТО:* не настроено")

            # Детали к замене (ближайшие)
            parts = db.query(Part).filter(Part.car_id == car.id).all()
            upcoming_parts = []
            for part in parts:
                reasons = []
                if part.interval_mileage and part.last_mileage is not None:
                    next_mileage = part.last_mileage + part.interval_mileage
                    if car.current_mileage >= next_mileage:
                        reasons.append("⚠️ пробег (пора!)")
                    else:
                        remaining = next_mileage - car.current_mileage
                        if remaining < 1000:  # если осталось меньше 1000 км
                            reasons.append(f"осталось {remaining:,.0f} км")
                if part.interval_months and part.last_date is not None:
                    next_date = part.last_date + timedelta(days=30 * part.interval_months)
                    days_left = (next_date.date() - datetime.now().date()).days
                    if days_left <= 0:
                        reasons.append("⚠️ время (пора!)")
                    else:
                        if days_left < 30:  # если осталось меньше 30 дней
                            reasons.append(f"осталось {days_left} дн.")
                if reasons:
                    upcoming_parts.append(f"  • {part.name}: {', '.join(reasons)}")
            if upcoming_parts:
                response_lines.append("🔧 *Детали к замене:*")
                response_lines.extend(upcoming_parts)
            else:
                response_lines.append("🔧 *Детали к замене:* все в порядке")

            response_lines.append("────────────")
            response_lines.append("")

        response_lines.append(f"💰 *ИТОГО по всем авто:*")
        response_lines.append(f"⛽ Топливо: {total_all_fuel:,.2f} ₽")
        response_lines.append(f"🔧 Обслуживание: {total_all_maintenance:,.2f} ₽")
        response_lines.append(f"💵 Всего: {total_all_fuel + total_all_maintenance:,.2f} ₽")

        full_response = "\n".join(response_lines)
        await message.answer(full_response, parse_mode="Markdown", reply_markup=get_stats_submenu())
