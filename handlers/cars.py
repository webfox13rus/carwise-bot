import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime

from database import SessionLocal, Car, User
from keyboards.main_menu import get_cars_submenu, get_cancel_keyboard
from car_data import BRANDS, MODELS_BY_BRAND

router = Router()
logger = logging.getLogger(__name__)

class CarStates(StatesGroup):
    waiting_for_brand = State()
    waiting_for_model = State()
    waiting_for_year = State()
    waiting_for_name = State()
    waiting_for_vin = State()
    waiting_for_mileage = State()
    waiting_for_fuel_type = State()
    waiting_for_car_to_delete = State()
    waiting_for_car_to_update_mileage = State()
    waiting_for_new_mileage = State()

@router.message(F.text == "🚗 Список авто")
async def list_cars(message: types.Message):
    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь, отправив /start")
            return
        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("У вас нет добавленных автомобилей.", reply_markup=get_cars_submenu())
            return
        text = "🚗 *Ваши автомобили:*\n\n"
        for car in cars:
            text += f"• {car.brand} {car.model} {car.year}г.\n"
            text += f"  Пробег: {car.current_mileage:,.0f} км\n"
            if car.vin:
                text += f"  VIN: `{car.vin}`\n"
            text += "\n"
        await message.answer(text, parse_mode="Markdown", reply_markup=get_cars_submenu())

# ... остальные функции с заменой всех next(get_db()) на with SessionLocal() ...
# Важно: в каждой функции, где есть работа с БД, замените блоки.
