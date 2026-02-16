from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.orm import Session
from datetime import datetime

from states.car_states import AddCarStates, MileageUpdateStates
from keyboards.main_menu import get_main_menu, get_cancel_keyboard, get_fuel_types_keyboard
from database import get_db, Car, User, FuelEvent, MaintenanceEvent
from config import config

router = Router()

@router.message(F.text == "🚗 Мои автомобили")
@router.message(Command("my_cars"))
async def show_my_cars(message: types.Message):
    """Показать список автомобилей пользователя"""
    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        
        if not user:
            await message.answer("Сначала зарегистрируйтесь, отправив /start")
            return
        
        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        
        if not cars:
            await message.answer(
                "🚫 У вас пока нет автомобилей.\n"
                "Нажмите '➕ Добавить авто' чтобы добавить первый.",
                reply_markup=get_main_menu()
            )
            return
        
        response = "🚗 *Ваши автомобили:*\n\n"
        
        for car in cars:
            # Считаем общие расходы через отдельные запросы (более надёжно, чем relationship)
            fuel_total = db.query(FuelEvent).filter(FuelEvent.car_id == car.id).with_entities(func.sum(FuelEvent.cost)).scalar() or 0
            maint_total = db.query(MaintenanceEvent).filter(MaintenanceEvent.car_id == car.id).with_entities(func.sum(MaintenanceEvent.cost)).scalar() or 0
            total_spent = fuel_total + maint_total
            
            response += (
                f"*{car.brand} {car.model} ({car.year})*\n"
                f"Пробег: *{car.current_mileage:,.0f} км*\n"
                f"Тип топлива: {config.DEFAULT_FUEL_TYPES.get(car.fuel_type, car.fuel_type)}\n"
                f"Общие расходы: *{total_spent:,.2f} ₽*\n"
                f"ID: `{car.id}`\n"
            )
            
            if car.name:
                response += f"Имя: {car.name}\n"
            
            response += "────────────\n\n"
        
        await message.answer(response, parse_mode="Markdown", reply_markup=get_main_menu())

@router.message(F.text == "➕ Добавить авто")
@router.message(Command("add_car"))
async def add_car_start(message: types.Message, state: FSMContext):
    """Начать процесс добавления автомобиля"""
    await state.set_state(AddCarStates.waiting_for_brand)
    await message.answer(
        "🚗 *Добавление нового автомобиля*\n\n"
        "Введите *марку* автомобиля:\n"
        "(Например: Toyota, BMW, Lada)",
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard()
    )

# ... (остальные функции без изменений, только убедитесь, что везде используется user.id, а не user.telegram_id для связи с автомобилями)
