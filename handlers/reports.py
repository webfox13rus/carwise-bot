from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import func
from database import get_db, Car, FuelEvent, MaintenanceEvent, User

router = Router()

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
        for car in cars:
            fuel_sum = db.query(FuelEvent).filter(FuelEvent.car_id == car.id).with_entities(func.sum(FuelEvent.cost)).scalar() or 0
            maint_sum = db.query(MaintenanceEvent).filter(MaintenanceEvent.car_id == car.id).with_entities(func.sum(MaintenanceEvent.cost)).scalar() or 0
            total_fuel += fuel_sum
            total_maintenance += maint_sum
        total = total_fuel + total_maintenance
        await message.answer(
            f"📊 Общая статистика\n\n"
            f"Количество авто: {len(cars)}\n"
            f"💰 Всего потрачено: {total:,.2f} ₽\n"
            f"⛽ Заправки: {total_fuel:,.2f} ₽\n"
            f"🔧 Обслуживание: {total_maintenance:,.2f} ₽"
        )
