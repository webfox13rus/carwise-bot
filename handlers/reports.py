from aiogram import Router, types, F
from aiogram.filters import Command
from sqlalchemy import func
from database import get_db, Car, FuelEvent, MaintenanceEvent, User
from keyboards.main_menu import get_main_menu
from config import config

router = Router()

@router.message(F.text == "📊 Статистика")
@router.message(Command("stats"))
async def show_stats(message: types.Message):
    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь, отправив /start")
            return

        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("У вас нет автомобилей.")
            return

        total_all_fuel = 0
        total_all_maintenance = 0
        response_lines = []

        for car in cars:
            response_lines.append(f"🚗 {car.brand} {car.model} ({car.year}):")
            response_lines.append(f"Пробег: {car.current_mileage:,.0f} км")

            # Расходы на обслуживание (суммарно)
            maint_sum = db.query(MaintenanceEvent).filter(MaintenanceEvent.car_id == car.id).with_entities(func.sum(MaintenanceEvent.cost)).scalar() or 0
            total_all_maintenance += maint_sum
            if maint_sum > 0:
                response_lines.append(f"🔧 Обслуживание: {maint_sum:,.2f} ₽")

            # Заправки с группировкой по типу топлива
            fuel_stats = db.query(
                FuelEvent.fuel_type,
                func.sum(FuelEvent.liters).label('total_liters'),
                func.sum(FuelEvent.cost).label('total_cost')
            ).filter(FuelEvent.car_id == car.id).group_by(FuelEvent.fuel_type).all()

            car_fuel_total = 0
            if fuel_stats:
                response_lines.append("⛽ Заправки по типам топлива:")
                for fuel_type, liters, cost in fuel_stats:
                    if fuel_type is None:
                        type_name = "Не указан"
                    else:
                        type_name = config.DEFAULT_FUEL_TYPES.get(fuel_type, fuel_type)
                    response_lines.append(f"  • {type_name}: {liters:.2f} л – {cost:,.2f} ₽")
                    car_fuel_total += cost
                response_lines.append(f"  Всего на топливо: {car_fuel_total:,.2f} ₽")
            else:
                response_lines.append("⛽ Нет заправок")

            total_all_fuel += car_fuel_total

            # Разделитель
            response_lines.append("────────────")
            response_lines.append("")  # пустая строка для читаемости

        # Итог по всем авто
        response_lines.append(f"💰 ИТОГО по всем авто:")
        response_lines.append(f"⛽ Топливо: {total_all_fuel:,.2f} ₽")
        response_lines.append(f"🔧 Обслуживание: {total_all_maintenance:,.2f} ₽")
        response_lines.append(f"💵 Всего: {total_all_fuel + total_all_maintenance:,.2f} ₽")

        # Отправка ответа (объединяем строки)
        full_response = "\n".join(response_lines)
        await message.answer(full_response, reply_markup=get_main_menu())
