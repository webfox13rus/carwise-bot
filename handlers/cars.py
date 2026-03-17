import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
from config import config

from database import SessionLocal, Car, User
from keyboards.main_menu import get_cars_submenu, get_cancel_keyboard, get_skip_keyboard
from car_data import BRANDS, MODELS_BY_BRAND

router = Router()
logger = logging.getLogger(__name__)

class CarStates(StatesGroup):
    waiting_for_brand = State()
    waiting_for_model = State()
    waiting_for_year = State()
    waiting_for_name = State()
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
            text += "\n"
        await message.answer(text, parse_mode="Markdown", reply_markup=get_cars_submenu())

@router.message(F.text == "➕ Добавить авто")
async def add_car_start(message: types.Message, state: FSMContext):
    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь, отправив /start")
            return
        if not user.is_premium and message.from_user.id not in config.ADMIN_IDS:
            car_count = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).count()
            if car_count >= 1:
                await message.answer(
                    "❌ В бесплатной версии можно добавить только один автомобиль.\n"
                    "Чтобы добавить больше, оформите Premium-подписку.",
                    reply_markup=get_cars_submenu()
                )
                return
    await state.set_state(CarStates.waiting_for_brand)
    await message.answer("Выберите марку автомобиля:", reply_markup=get_brands_keyboard())

def get_brands_keyboard():
    buttons = []
    for brand in BRANDS[:10]:
        buttons.append([types.InlineKeyboardButton(text=brand, callback_data=f"brand_{brand}")])
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)

@router.callback_query(F.data.startswith("brand_"))
async def brand_chosen(callback: types.CallbackQuery, state: FSMContext):
    brand = callback.data.split("_", 1)[1]
    await state.update_data(brand=brand)
    models = MODELS_BY_BRAND.get(brand, [])
    if models:
        await state.set_state(CarStates.waiting_for_model)
        await callback.message.edit_text(f"Выберите модель {brand}:", reply_markup=get_models_keyboard(models))
    else:
        await state.update_data(model="")
        await state.set_state(CarStates.waiting_for_year)
        await callback.message.edit_text("Введите год выпуска (например, 2020):")
    await callback.answer()

def get_models_keyboard(models):
    buttons = []
    for model in models[:10]:
        buttons.append([types.InlineKeyboardButton(text=model, callback_data=f"model_{model}")])
    buttons.append([types.InlineKeyboardButton(text="Другая (ввести вручную)", callback_data="model_other")])
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)

@router.callback_query(F.data.startswith("model_"))
async def model_chosen(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "model_other":
        await state.set_state(CarStates.waiting_for_model)
        await callback.message.edit_text("Введите название модели вручную:")
    else:
        model = callback.data.split("_", 1)[1]
        await state.update_data(model=model)
        await state.set_state(CarStates.waiting_for_year)
        await callback.message.edit_text("Введите год выпуска (например, 2020):")
    await callback.answer()

@router.message(CarStates.waiting_for_model)
async def model_entered(message: types.Message, state: FSMContext):
    await state.update_data(model=message.text.strip())
    await state.set_state(CarStates.waiting_for_year)
    await message.answer("Введите год выпуска (например, 2020):", reply_markup=get_cancel_keyboard())

@router.message(CarStates.waiting_for_year)
async def year_entered(message: types.Message, state: FSMContext):
    try:
        year = int(message.text.strip())
        current_year = datetime.now().year
        if year < 1900 or year > current_year + 1:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректный год (например, 2020).")
        return
    await state.update_data(year=year)
    await state.set_state(CarStates.waiting_for_name)
    await message.answer(
        "Введите название или прозвище автомобиля (например, 'Моя ласточка') или нажмите 'Пропустить':",
        reply_markup=get_skip_keyboard()
    )

@router.message(CarStates.waiting_for_name)
async def name_entered(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_cars_submenu())
        return
    if message.text != "⏭ Пропустить":
        await state.update_data(name=message.text.strip())
    await state.set_state(CarStates.waiting_for_mileage)
    await message.answer(
        "Введите текущий пробег (в км):",
        reply_markup=get_cancel_keyboard()
    )

@router.message(CarStates.waiting_for_mileage)
async def mileage_entered(message: types.Message, state: FSMContext):
    try:
        mileage = float(message.text.strip().replace(",", ""))
        if mileage < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите число (пробег в км).")
        return
    await state.update_data(mileage=mileage)
    await state.set_state(CarStates.waiting_for_fuel_type)
    await message.answer(
        "Выберите тип топлива:",
        reply_markup=get_fuel_type_keyboard()
    )

def get_fuel_type_keyboard():
    from config import config
    buttons = []
    for key, value in config.DEFAULT_FUEL_TYPES.items():
        buttons.append([types.InlineKeyboardButton(text=value, callback_data=f"fuel_{key}")])
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)

@router.callback_query(F.data.startswith("fuel_"))
async def fuel_chosen(callback: types.CallbackQuery, state: FSMContext):
    fuel_key = callback.data.split("_", 1)[1]
    from config import config
    fuel_type = config.DEFAULT_FUEL_TYPES.get(fuel_key, fuel_key)
    data = await state.get_data()
    
    # Проверяем наличие обязательных полей
    brand = data.get("brand")
    year = data.get("year")
    if not brand or not year:
        await callback.message.answer("❌ Ошибка: не хватает данных об автомобиле. Попробуйте добавить авто заново.")
        await state.clear()
        await callback.answer()
        return
    
    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == callback.from_user.id).first()
        if not user:
            await callback.message.answer("❌ Ошибка: пользователь не найден.")
            await state.clear()
            await callback.answer()
            return
        new_car = Car(
            user_id=user.id,
            brand=brand,
            model=data.get("model", ""),
            year=year,
            name=data.get("name", ""),
            current_mileage=data.get("mileage", 0),
            fuel_type=fuel_type,
            is_active=True
        )
        db.add(new_car)
        db.commit()
        logger.info(f"Добавлен автомобиль {new_car.brand} {new_car.model} для пользователя {user.telegram_id}")
    await state.clear()
    await callback.message.answer(
        f"✅ Автомобиль {brand} {data.get('model', '')} успешно добавлен!",
        reply_markup=get_cars_submenu()
    )
    await callback.answer()

@router.message(F.text == "🔄 Обновить пробег")
async def update_mileage_start(message: types.Message, state: FSMContext):
    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь.")
            return
        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("У вас нет автомобилей.", reply_markup=get_cars_submenu())
            return
        cars_list = [(car.id, f"{car.brand} {car.model} {car.year}") for car in cars]
        await state.update_data(cars=cars_list)
        await state.set_state(CarStates.waiting_for_car_to_update_mileage)
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=name, callback_data=f"car_{car_id}")] for car_id, name in cars_list
        ])
        await message.answer("Выберите автомобиль для обновления пробега:", reply_markup=keyboard)

@router.callback_query(CarStates.waiting_for_car_to_update_mileage, F.data.startswith("car_"))
async def car_selected_for_mileage(callback: types.CallbackQuery, state: FSMContext):
    car_id = int(callback.data.split("_")[1])
    await state.update_data(selected_car_id=car_id)
    await state.set_state(CarStates.waiting_for_new_mileage)
    await callback.message.edit_text("Введите новый пробег (в км):")
    await callback.answer()

@router.message(CarStates.waiting_for_new_mileage)
async def new_mileage_entered(message: types.Message, state: FSMContext):
    try:
        new_mileage = float(message.text.strip().replace(",", ""))
        if new_mileage < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректное число.")
        return
    data = await state.get_data()
    car_id = data.get("selected_car_id")
    with SessionLocal() as db:
        car = db.query(Car).filter(Car.id == car_id).first()
        if car:
            car.current_mileage = new_mileage
            db.commit()
            await message.answer(f"✅ Пробег автомобиля {car.brand} {car.model} обновлён до {new_mileage:,.0f} км.")
        else:
            await message.answer("❌ Автомобиль не найден.")
    await state.clear()
    await message.answer("Меню автомобилей:", reply_markup=get_cars_submenu())

@router.message(F.text == "🗑 Удалить авто")
async def delete_car_start(message: types.Message, state: FSMContext):
    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь.")
            return
        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("У вас нет автомобилей.", reply_markup=get_cars_submenu())
            return
        cars_list = [(car.id, f"{car.brand} {car.model} {car.year}") for car in cars]
        await state.update_data(cars=cars_list)
        await state.set_state(CarStates.waiting_for_car_to_delete)
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=name, callback_data=f"del_{car_id}")] for car_id, name in cars_list
        ])
        await message.answer("Выберите автомобиль для удаления (скрытия):", reply_markup=keyboard)

@router.callback_query(CarStates.waiting_for_car_to_delete, F.data.startswith("del_"))
async def delete_car_confirm(callback: types.CallbackQuery, state: FSMContext):
    car_id = int(callback.data.split("_")[1])
    with SessionLocal() as db:
        car = db.query(Car).filter(Car.id == car_id).first()
        if car:
            car.is_active = False
            db.commit()
            await callback.message.edit_text(f"✅ Автомобиль {car.brand} {car.model} удалён из списка.")
        else:
            await callback.message.edit_text("❌ Автомобиль не найден.")
    await state.clear()
    await callback.message.answer("Меню автомобилей:", reply_markup=get_cars_submenu())
    await callback.answer()
