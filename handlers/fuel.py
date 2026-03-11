import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime

from database import SessionLocal, Car, FuelEvent, User
from keyboards.main_menu import get_fuel_submenu, get_cancel_keyboard
from config import config

router = Router()
logger = logging.getLogger(__name__)

class FuelStates(StatesGroup):
    waiting_for_car = State()
    waiting_for_liters_cost = State()
    waiting_for_mileage = State()
    waiting_for_fuel_type = State()
    waiting_for_photo = State()

@router.message(F.text == "⛽ Добавить заправку")
async def add_fuel_start(message: types.Message, state: FSMContext):
    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь, отправив /start")
            return
        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("У вас нет автомобилей. Сначала добавьте авто.", reply_markup=get_fuel_submenu())
            return
        # ... логика выбора авто ...
