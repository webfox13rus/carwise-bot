import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta

from database import SessionLocal, Car, User, Insurance
from keyboards.main_menu import get_insurance_submenu, get_cancel_keyboard
from config import config

router = Router()
logger = logging.getLogger(__name__)

class InsuranceStates(StatesGroup):
    waiting_for_car = State()
    waiting_for_policy = State()
    waiting_for_company = State()
    waiting_for_start_date = State()
    waiting_for_end_date = State()
    waiting_for_cost = State()
    waiting_for_notes = State()
    waiting_for_photo = State()
    waiting_for_delete = State()

@router.message(F.text == "📄 Добавить страховку")
async def add_insurance_start(message: types.Message, state: FSMContext):
    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь, отправив /start")
            return
        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("У вас нет автомобилей.", reply_markup=get_insurance_submenu())
            return
        # Сохраняем список авто как кортежи (id, название)
        await state.update_data(cars=[(car.id, f"{car.brand} {car.model}") for car in cars])
        await state.set_state(InsuranceStates.waiting_for_car)
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=name, callback_data=f"car_{car_id}")] for car_id, name in cars
        ])
        await message.answer("Выберите автомобиль:", reply_markup=keyboard)

# ... (остальные функции, в которых все `next(get_db())` заменены на `with SessionLocal() as db:`)
