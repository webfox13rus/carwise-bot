from aiogram import Router, types, F
from aiogram.filters import Command
from sqlalchemy import func
from database import get_db, Car, FuelEvent, MaintenanceEvent, User
from keyboards.main_menu import get_main_menu

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

        total_fuel = 0
        total_maintenance = 0
        response = "📊 Общая статистика\n\n"

        for car in cars:
            fuel_sum = db.query(FuelEvent).filter(FuelEvent.car_id == car.id).with_entities(func.sum(FuelEvent.cost)).scalar() or 0
            maint_sum = db.query(MaintenanceEvent).filter(MaintenanceEvent.car_id == car.id).with_entities(func.sum(MaintenanceEvent.cost)).scalar() or 0
            total_fuel += fuel_sum
            total_maintenance += maint_sum

            # Расчёт среднего расхода по последним заправкам
            fuel_events = db.query(FuelEvent).filter(FuelEvent.car_id == car.id).order_by(FuelEvent.mileage).all()
            consumption_info = ""
            if len(fuel_events) >= 2:
                total_liters = 0
                total_distance = 0
                prev = None
                for event in fuel_events:
                    if prev is not None and event.mileage and prev.mileage and event.mileage > prev.mileage:
                        total_liters += event.liters
                        total_distance += event.mileage - prev.mileage
                    prev = event
                if total_distance > 0:
                    avg_consumption = (total_liters / total_distance) * 100
                    consumption_info = f"Средний расход: {avg_consumption:.2f} л/100км"
                else:
                    consumption_info = "Недостаточно данных для расхода"
            else:
                consumption_info = "Нужно минимум 2 заправки"

            response += (
                f"🚗 {car.brand} {car.model} ({car.year})\n"
                f"Пробег: {car.current_mileage:,.0f} км\n"
                f"Расходы: всего {fuel_sum + maint_sum:,.2f} ₽\n"
                f"⛽ Заправки: {fuel_sum:,.2f} ₽\n"
                f"🔧 Обслуживание: {maint_sum:,.2f} ₽\n"
                f"{consumption_info}\n\n"
            )

        total = total_fuel + total_maintenance
        response += f"💰 Итого по всем авто: {total:,.2f} ₽"

        await message.answer(response, reply_markup=get_main_menu())
