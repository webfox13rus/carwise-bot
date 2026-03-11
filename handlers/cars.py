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

# ... остальной код с заменой всех next(get_db()) на SessionLocal() ...
