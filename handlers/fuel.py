import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime

from database import SessionLocal, Car, FuelEvent, User
from keyboards.main_menu import get_fuel_submenu, get_cancel_keyboard, get_skip_keyboard
from config import config

router = Router()
logger = logging.getLogger(__name__)

class FuelStates(StatesGroup):
    waiting_for_car = State()
    waiting_for_fuel_type = State()
    waiting_for_liters = State()
    waiting_for_cost = State()
    waiting_for_mileage = State()
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
    await state.set_state(FuelStates.waiting_for_fuel_type)
    await callback.message.edit_text(
        "Выберите тип топлива:",
        reply_markup=get_fuel_type_keyboard()
    )
    await callback.answer()

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
    await state.set_state(FuelStates.waiting_for_liters)
    await callback.message.edit_text("Введите количество литров:")
    await callback.answer()

@router.message(FuelStates.waiting_for_liters)
async def liters_entered(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление заправки отменено", reply_markup=get_fuel_submenu())
        return
    try:
        liters = float(message.text.strip().replace(",", "."))
        if liters <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректное число литров (больше 0).")
        return
    await state.update_data(liters=liters)
    await state.set_state(FuelStates.waiting_for_cost)
    await message.answer("Введите сумму (в рублях):", reply_markup=get_cancel_keyboard())

@router.message(FuelStates.waiting_for_cost)
async def cost_entered(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление заправки отменено", reply_markup=get_fuel_submenu())
        return
    try:
        cost = float(message.text.strip().replace(",", ""))
        if cost <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректную сумму (число больше 0).")
        return
    await state.update_data(cost=cost)
    await state.set_state(FuelStates.waiting_for_mileage)
    await message.answer(
        "Введите пробег (в км) или нажмите 'Пропустить', чтобы пропустить:",
        reply_markup=get_skip_keyboard()
    )

@router.message(FuelStates.waiting_for_mileage)
async def mileage_entered(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление заправки отменено", reply_markup=get_fuel_submenu())
        return
    if message.text != "⏭ Пропустить":
        try:
            mileage = float(message.text.strip().replace(",", ""))
            if mileage < 0:
                raise ValueError
            await state.update_data(mileage=mileage)
        except ValueError:
            await message.answer("❌ Введите корректный пробег (число).")
            return
    await state.set_state(FuelStates.waiting_for_photo)
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Да, добавить фото", callback_data="photo_yes")],
        [types.InlineKeyboardButton(text="❌ Нет, сохранить без фото", callback_data="photo_no")]
    ])
    await message.answer("Хотите прикрепить фото чека?", reply_markup=keyboard)

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
    response = f"✅ Заправка сохранена!\nЛитров: {liters:.2f}\nСумма: {cost:.2f} руб.\nЦена за литр: {price_per_liter:.2f} руб."
    if mileage:
        response += f"\nПробег: {mileage:,.0f} км"
    else:
        response += "\nПробег не указан"

    await message.answer(response, reply_markup=get_fuel_submenu())
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
