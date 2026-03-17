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
        # Создаём список кортежей (id, название) для клавиатуры и состояния
        cars_list = [(car.id, f"{car.brand} {car.model}") for car in cars]
        await state.update_data(cars=cars_list)
        await state.set_state(FuelStates.waiting_for_car)
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=name, callback_data=f"car_{car_id}")] for car_id, name in cars_list
        ])
        await message.answer("Выберите автомобиль:", reply_markup=keyboard)

@router.callback_query(FuelStates.waiting_for_car, F.data.startswith("car_"))
async def car_selected(callback: types.CallbackQuery, state: FSMContext):
    car_id = int(callback.data.split("_")[1])
    await state.update_data(car_id=car_id)
    await state.set_state(FuelStates.waiting_for_liters_cost)
    await callback.message.edit_text(
        "Введите литры и сумму через пробел (например: 45.5 3000)\n"
        "Или отправьте одним числом (сумма) для быстрого ввода."
    )
    await callback.answer()

@router.message(FuelStates.waiting_for_liters_cost)
async def liters_cost_entered(message: types.Message, state: FSMContext):
    text = message.text.strip()
    parts = text.split()
    if len(parts) == 2:
        try:
            liters = float(parts[0].replace(",", "."))
            cost = float(parts[1].replace(",", "."))
            await state.update_data(liters=liters, cost=cost)
            await state.set_state(FuelStates.waiting_for_mileage)
            await message.answer("Введите пробег (в км) или отправьте /skip, чтобы пропустить:", reply_markup=get_cancel_keyboard())
        except ValueError:
            await message.answer("❌ Неверный формат. Введите литры и сумму через пробел (например: 45.5 3000).")
    elif len(parts) == 1:
        await message.answer("❌ Пожалуйста, введите и литры, и сумму через пробел.")
    else:
        await message.answer("❌ Неверный формат. Введите литры и сумму через пробел.")

@router.message(FuelStates.waiting_for_mileage)
async def mileage_entered(message: types.Message, state: FSMContext):
    if message.text != "/skip":
        try:
            mileage = float(message.text.strip().replace(",", ""))
            if mileage < 0:
                raise ValueError
        except ValueError:
            await message.answer("❌ Введите корректный пробег (число).")
            return
        await state.update_data(mileage=mileage)
    await state.set_state(FuelStates.waiting_for_fuel_type)
    await message.answer("Выберите тип топлива:", reply_markup=get_fuel_type_keyboard())

def get_fuel_type_keyboard():
    buttons = []
    for key, value in config.DEFAULT_FUEL_TYPES.items():
        buttons.append([types.InlineKeyboardButton(text=value, callback_data=f"fuel_{key}")])
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)

@router.callback_query(FuelStates.waiting_for_fuel_type, F.data.startswith("fuel_"))
async def fuel_type_chosen(callback: types.CallbackQuery, state: FSMContext):
    fuel_key = callback.data.split("_", 1)[1]
    fuel_type = config.DEFAULT_FUEL_TYPES.get(fuel_key, fuel_key)
    await state.update_data(fuel_type=fuel_type)
    await state.set_state(FuelStates.waiting_for_photo)
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Да, добавить фото", callback_data="photo_yes")],
        [types.InlineKeyboardButton(text="❌ Нет, сохранить без фото", callback_data="photo_no")]
    ])
    await callback.message.edit_text("Хотите прикрепить фото чека?", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(FuelStates.waiting_for_photo, F.data.in_({"photo_yes", "photo_no"}))
async def photo_decision(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "photo_yes":
        await state.set_state(FuelStates.waiting_for_photo)
        await callback.message.edit_text("Отправьте фото чека.")
    else:
        await save_fuel_event(callback.message, state, photo_id=None)
    await callback.answer()

@router.message(FuelStates.waiting_for_photo, F.photo)
async def photo_received(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await save_fuel_event(message, state, photo_id)

async def save_fuel_event(message: types.Message, state: FSMContext, photo_id=None):
    data = await state.get_data()
    car_id = data.get("car_id")
    liters = data.get("liters")
    cost = data.get("cost")
    mileage = data.get("mileage")
    fuel_type = data.get("fuel_type")

    with SessionLocal() as db:
        car = db.query(Car).filter(Car.id == car_id).first()
        if car and mileage:
            car.current_mileage = mileage
        fuel_event = FuelEvent(
            car_id=car_id,
            liters=liters,
            cost=cost,
            mileage=mileage,
            fuel_type=fuel_type,
            photo_id=photo_id
        )
        db.add(fuel_event)
        db.commit()
        logger.info(f"Заправка добавлена для авто {car_id}")

    price_per_liter = cost / liters if liters else 0
    await message.answer(
        f"✅ Заправка сохранена!\n"
        f"Литров: {liters:.2f}\n"
        f"Сумма: {cost:.2f} руб.\n"
        f"Цена за литр: {price_per_liter:.2f} руб.\n"
        f"Пробег: {mileage:,.0f} км" if mileage else "Пробег не указан",
        reply_markup=get_fuel_submenu()
    )
    await state.clear()

@router.message(F.text == "📸 Мои чеки заправок")
async def my_fuel_photos(message: types.Message):
    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь.")
            return
        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("У вас нет автомобилей.")
            return
        car_ids = [car.id for car in cars]
        fuel_events = db.query(FuelEvent).filter(FuelEvent.car_id.in_(car_ids), FuelEvent.photo_id != None).order_by(FuelEvent.date.desc()).limit(10).all()
        if not fuel_events:
            await message.answer("У вас нет сохранённых чеков заправок.", reply_markup=get_fuel_submenu())
            return
        for event in fuel_events:
            caption = f"Заправка {event.date.strftime('%d.%m.%Y')}\n{event.liters:.2f} л, {event.cost:.2f} руб."
            await message.answer_photo(photo=event.photo_id, caption=caption)
        await message.answer("Это последние 10 чеков.", reply_markup=get_fuel_submenu())
