from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import func
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
        response = "🚗 Ваши автомобили:\n\n"
        for car in cars:
            fuel_total = db.query(FuelEvent).filter(FuelEvent.car_id == car.id).with_entities(func.sum(FuelEvent.cost)).scalar() or 0
            maint_total = db.query(MaintenanceEvent).filter(MaintenanceEvent.car_id == car.id).with_entities(func.sum(MaintenanceEvent.cost)).scalar() or 0
            total_spent = fuel_total + maint_total
            response += (
                f"{car.brand} {car.model} ({car.year})\n"
                f"Пробег: {car.current_mileage:,.0f} км\n"
                f"Тип топлива: {config.DEFAULT_FUEL_TYPES.get(car.fuel_type, car.fuel_type)}\n"
                f"Общие расходы: {total_spent:,.2f} ₽\n"
                f"ID: {car.id}\n"
            )
            if car.name:
                response += f"Имя: {car.name}\n"
            response += "────────────\n\n"
        await message.answer(response, reply_markup=get_main_menu())

@router.message(F.text == "➕ Добавить авто")
@router.message(Command("add_car"))
async def add_car_start(message: types.Message, state: FSMContext):
    await state.set_state(AddCarStates.waiting_for_brand)
    await message.answer(
        "🚗 Добавление нового автомобиля\n\n"
        "Введите марку автомобиля:\n"
        "(Например: Toyota, BMW, Lada)",
        reply_markup=get_cancel_keyboard()
    )

@router.message(AddCarStates.waiting_for_brand)
async def process_brand(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_main_menu())
        return
    await state.update_data(brand=message.text)
    await state.set_state(AddCarStates.waiting_for_model)
    await message.answer(
        "Введите модель автомобиля:\n"
        "(Например: Camry, X5, Vesta)",
        reply_markup=get_cancel_keyboard()
    )

@router.message(AddCarStates.waiting_for_model)
async def process_model(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_main_menu())
        return
    await state.update_data(model=message.text)
    await state.set_state(AddCarStates.waiting_for_year)
    await message.answer(
        "Введите год выпуска:\n"
        "(Например: 2015)",
        reply_markup=get_cancel_keyboard()
    )

@router.message(AddCarStates.waiting_for_year)
async def process_year(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_main_menu())
        return
    try:
        year = int(message.text)
        current_year = datetime.now().year
        if year < 1900 or year > current_year + 1:
            await message.answer(f"❌ Пожалуйста, введите корректный год (1900-{current_year+1})")
            return
        await state.update_data(year=year)
        await state.set_state(AddCarStates.waiting_for_name)
        await message.answer(
            "💡 Хотите дать автомобилю имя (псевдоним)?\n"
            "(Например: 'Рабочая тачка', 'Семейный автомобиль')\n\n"
            "Или отправьте '-' чтобы пропустить:",
            reply_markup=get_cancel_keyboard()
        )
    except ValueError:
        await message.answer("❌ Пожалуйста, введите число (например: 2015)")

@router.message(AddCarStates.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_main_menu())
        return
    name = message.text if message.text != "-" else None
    await state.update_data(name=name)
    await state.set_state(AddCarStates.waiting_for_mileage)
    await message.answer(
        "📏 Введите текущий пробег в километрах:\n"
        "(Например: 150000 или 75.5 для тысяч)",
        reply_markup=get_cancel_keyboard()
    )

@router.message(AddCarStates.waiting_for_mileage)
async def process_mileage(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_main_menu())
        return
    try:
        mileage = float(message.text.replace(',', '.'))
        if mileage < 0 or mileage > 5000000:
            await message.answer("❌ Пожалуйста, введите корректный пробег (0-5,000,000 км)")
            return
        await state.update_data(mileage=mileage)
        await state.set_state(AddCarStates.waiting_for_fuel_type)
        await message.answer(
            "⛽ Выберите тип топлива:",
            reply_markup=get_fuel_types_keyboard()
        )
    except ValueError:
        await message.answer("❌ Пожалуйста, введите число (например: 150000)")

@router.callback_query(F.data.startswith("fuel_type_"))
async def process_fuel_type(callback: types.CallbackQuery, state: FSMContext):
    fuel_type = callback.data.split("_")[-1]
    await state.update_data(fuel_type=fuel_type)
    data = await state.get_data()
    fuel_name = config.DEFAULT_FUEL_TYPES.get(fuel_type, fuel_type)
    confirmation_text = (
        "✅ Проверьте данные автомобиля:\n\n"
        f"Марка: {data['brand']}\n"
        f"Модель: {data['model']}\n"
        f"Год: {data['year']}\n"
        f"Пробег: {data['mileage']:,.0f} км\n"
        f"Тип топлива: {fuel_name}\n"
    )
    if data.get('name'):
        confirmation_text += f"Имя: {data['name']}\n"
    confirmation_text += "\nВсё верно?"
    await callback.message.edit_text(confirmation_text)  # убрали parse_mode
    await callback.message.answer(
        "Подтвердите добавление автомобиля:",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="✅ Да, добавить")],
                [types.KeyboardButton(text="❌ Нет, исправить")]
            ],
            resize_keyboard=True
        )
    )
    await callback.answer()

@router.message(AddCarStates.waiting_for_fuel_type, F.text.in_(["✅ Да, добавить", "❌ Нет, исправить"]))
async def confirm_car_addition(message: types.Message, state: FSMContext):
    if message.text == "❌ Нет, исправить":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_main_menu())
        return
    data = await state.get_data()
    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )
            db.add(user)
            db.commit()
        car = Car(
            user_id=user.id,
            brand=data['brand'],
            model=data['model'],
            year=data['year'],
            name=data.get('name'),
            current_mileage=data['mileage'],
            fuel_type=data['fuel_type']
        )
        db.add(car)
        db.commit()
        await message.answer(
            f"🚗 Автомобиль успешно добавлен!\n\n"
            f"{data['brand']} {data['model']} ({data['year']})\n"
            f"Текущий пробег: {data['mileage']:,.0f} км\n"
            f"ID автомобиля: {car.id}\n\n"
            f"Теперь вы можете добавлять заправки, обслуживание и отслеживать расходы.",
            reply_markup=get_main_menu()
        )
    await state.clear()

@router.message(F.text == "🔄 Обновить пробег")
async def update_mileage_start(message: types.Message, state: FSMContext):
    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала добавьте автомобиль!")
            return
        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("🚫 У вас нет автомобилей")
            return
        if len(cars) == 1:
            await state.update_data(car_id=cars[0].id)
            await state.set_state(MileageUpdateStates.waiting_for_mileage)
            await message.answer(
                f"🚗 {cars[0].brand} {cars[0].model}\n"
                f"Текущий пробег: {cars[0].current_mileage:,.0f} км\n\n"
                f"Введите новый пробег (в км):",
                reply_markup=get_cancel_keyboard()
            )
        else:
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[])
            for car in cars:
                keyboard.inline_keyboard.append([
                    types.InlineKeyboardButton(
                        text=f"{car.brand} {car.model} - {car.current_mileage:,.0f} км",
                        callback_data=f"update_mileage_{car.id}"
                    )
                ])
            await state.set_state(MileageUpdateStates.waiting_for_car_choice)
            await message.answer(
                "Выберите автомобиль для обновления пробега:",
                reply_markup=keyboard
            )

@router.callback_query(F.data.startswith("update_mileage_"))
async def select_car_for_mileage(callback: types.CallbackQuery, state: FSMContext):
    car_id = int(callback.data.split("_")[-1])
    with next(get_db()) as db:
        car = db.query(Car).filter(Car.id == car_id).first()
        if car:
            await state.update_data(car_id=car_id)
            await state.set_state(MileageUpdateStates.waiting_for_mileage)
            await callback.message.edit_text(
                f"🚗 {car.brand} {car.model}\n"
                f"Текущий пробег: {car.current_mileage:,.0f} км\n\n"
                f"Введите новый пробег (в км):"
            )
    await callback.answer()

@router.message(MileageUpdateStates.waiting_for_mileage)
async def process_new_mileage(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Обновление отменено", reply_markup=get_main_menu())
        return
    try:
        new_mileage = float(message.text.replace(',', '.'))
        data = await state.get_data()
        car_id = data['car_id']
        with next(get_db()) as db:
            car = db.query(Car).filter(Car.id == car_id).first()
            if car:
                old_mileage = car.current_mileage
                if new_mileage < old_mileage:
                    await message.answer(
                        "⚠️ Внимание!\n\n"
                        f"Новый пробег ({new_mileage:,.0f} км) меньше текущего ({old_mileage:,.0f} км).\n"
                        "Это возможно при замене одометра или сбросе пробега.\n\n"
                        "Вы уверены, что хотите обновить?",
                        reply_markup=types.ReplyKeyboardMarkup(
                            keyboard=[
                                [types.KeyboardButton(text="✅ Да, обновить")],
                                [types.KeyboardButton(text="❌ Нет, отменить")]
                            ],
                            resize_keyboard=True
                        )
                    )
                    await state.update_data(new_mileage=new_mileage)
                    return
                car.current_mileage = new_mileage
                db.commit()
                await message.answer(
                    f"✅ Пробег обновлен!\n\n"
                    f"Было: {old_mileage:,.0f} км\n"
                    f"Стало: {new_mileage:,.0f} км\n"
                    f"Пройдено: +{new_mileage - old_mileage:,.1f} км",
                    reply_markup=get_main_menu()
                )
        await state.clear()
    except ValueError:
        await message.answer("❌ Пожалуйста, введите число (например: 150500)")
