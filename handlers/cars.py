import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
from config import config

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
    # VIN удалён
    waiting_for_mileage = State()
    waiting_for_fuel_type = State()
    waiting_for_car_to_delete = State()
    waiting_for_car_to_update_mileage = State()
    waiting_for_new_mileage = State()

# ... остальные функции (list_cars, add_car_start, brand_chosen и т.д.) без изменений ...

@router.message(CarStates.waiting_for_name)
async def name_entered(message: types.Message, state: FSMContext):
    if message.text != "/skip":  # оставляем /skip для совместимости, но позже заменим на кнопку
        await state.update_data(name=message.text.strip())
    # Пропускаем VIN, сразу переходим к пробегу
    await state.set_state(CarStates.waiting_for_mileage)
    await message.answer(
        "Введите текущий пробег (в км):",
        reply_markup=get_cancel_keyboard()
    )

# ... остальные функции (mileage_entered, fuel_chosen и т.д.) без изменений ...
