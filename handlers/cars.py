import logging
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import func

from states.car_states import AddCarStates, MileageUpdateStates, DeleteCarStates
from keyboards.main_menu import (
    get_main_menu, get_cars_submenu, get_cancel_keyboard,
    get_fuel_types_keyboard
)
from database import get_db, Car, User, FuelEvent, MaintenanceEvent, Insurance
from config import config
from car_data import CAR_BRANDS, get_models_for_brand

router = Router()
logger = logging.getLogger(__name__)

# ------------------- Вспомогательная функция для инлайн-клавиатур -------------------
def make_inline_keyboard(items: list, callback_prefix: str, columns: int = 2) -> types.InlineKeyboardMarkup:
    keyboard = []
    row = []
    for i, item in enumerate(items):
        row.append(types.InlineKeyboardButton(text=item, callback_data=f"{callback_prefix}:{item}"))
        if (i + 1) % columns == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([types.InlineKeyboardButton(text="✏️ Ввести вручную", callback_data=f"{callback_prefix}:manual")])
    keyboard.append([types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

# ------------------- Просмотр списка автомобилей -------------------
@router.message(F.text.in_(["🚗 Список авто", "🚗 Мои автомобили"]))
@router.message(Command("my_cars"))
async def show_my_cars(message: types.Message):
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
                reply_markup=get_cars_submenu()
            )
            return
        response = "🚗 Ваши автомобили:\n\n"
        for car in cars:
            fuel_total = db.query(FuelEvent).filter(FuelEvent.car_id == car.id).with_entities(func.sum(FuelEvent.cost)).scalar() or 0
            maint_total = db.query(MaintenanceEvent).filter(MaintenanceEvent.car_id == car.id).with_entities(func.sum(MaintenanceEvent.cost)).scalar() or 0
            total_spent = fuel_total + maint_total
            
            # Информация о страховке
            insurances = db.query(Insurance).filter(Insurance.car_id == car.id).all()
            insurance_info = ""
            if insurances:
                sorted_ins = sorted(insurances, key=lambda x: x.end_date)
                nearest = sorted_ins[0]
                days_left = (nearest.end_date.date() - datetime.now().date()).days
                if days_left < 0:
                    status = "❗️Истекла"
                elif days_left <= 7:
                    status = f"⚠️Истекает через {days_left} дн."
                else:
                    status = "✅Активна"
                insurance_info = f"Страховка: до {nearest.end_date.strftime('%d.%m.%Y')} {status}\n"
            else:
                insurance_info = "Страховка: не добавлена\n"

            # Информация о VIN
            vin_info = f"🔍 VIN: {car.vin}\n" if car.vin else "🔍 VIN: не указан\n"

            # Информация о следующем ТО
            next_to_info = ""
            if car.to_mileage_interval or car.to_months_interval:
                next_to_parts = []
                if car.to_mileage_interval and car.last_maintenance_mileage is not None:
                    next_mileage = car.last_maintenance_mileage + car.to_mileage_interval
                    if car.current_mileage >= next_mileage:
                        next_to_parts.append("⚠️ по пробегу (нужно ТО!)")
                    else:
                        remaining_km = next_mileage - car.current_mileage
                        next_to_parts.append(f"по пробегу через {remaining_km:,.0f} км")
                if car.to_months_interval and car.last_maintenance_date is not None:
                    next_date = car.last_maintenance_date + timedelta(days=30 * car.to_months_interval)
                    days_left = (next_date.date() - datetime.now().date()).days
                    if days_left <= 0:
                        next_to_parts.append("⚠️ по дате (нужно ТО!)")
                    else:
                        next_to_parts.append(f"по дате через {days_left} дн.")
                if next_to_parts:
                    next_to_info = "Следующее ТО: " + ", ".join(next_to_parts) + "\n"
                else:
                    next_to_info = "Следующее ТО: данные неполные\n"
            else:
                next_to_info = "Следующее ТО: не настроено\n"

            response += (
                f"{car.brand} {car.model} ({car.year})\n"
                f"Пробег: {car.current_mileage:,.0f} км\n"
                f"Тип топлива: {config.DEFAULT_FUEL_TYPES.get(car.fuel_type, car.fuel_type)}\n"
                f"Общие расходы: {total_spent:,.2f} ₽\n"
                f"{vin_info}"
                f"{insurance_info}"
                f"{next_to_info}"
                f"ID: {car.id}\n"
            )
            if car.name:
                response += f"Имя: {car.name}\n"
            response += "────────────\n\n"
        await message.answer(response, reply_markup=get_cars_submenu())

# ------------------- Добавление автомобиля -------------------
@router.message(F.text.in_(["➕ Добавить авто"]))
@router.message(Command("add_car"))
async def add_car_start(message: types.Message, state: FSMContext):
    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                is_premium=False
            )
            db.add(user)
            db.commit()

        car_count = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).count()
        is_admin = message.from_user.id in config.ADMIN_IDS
        if car_count >= 1 and not user.is_premium and not is_admin:
            await message.answer(
                "❌ *Добавление второго автомобиля* – платная функция.\n\n"
                "Сейчас вы можете добавить только один автомобиль. "
                "Чтобы добавить больше, приобретите подписку. Функция подписки находится в разработке.",
                parse_mode="Markdown",
                reply_markup=get_cars_submenu()
            )
            return

        await state.set_state(AddCarStates.waiting_for_brand)
        keyboard = make_inline_keyboard(CAR_BRANDS, "brand")
        await message.answer(
            "🚗 Выберите марку автомобиля из списка или введите вручную:",
            reply_markup=keyboard
        )

# Обработка отмены через инлайн-кнопку
@router.callback_query(F.data == "cancel")
async def cancel_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Добавление отменено")
    await callback.message.answer("Управление автомобилями:", reply_markup=get_cars_submenu())
    await callback.answer()

# ... (здесь идут функции выбора марки/модели, года, имени – без изменений, до момента после имени)

@router.message(AddCarStates.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_cars_submenu())
        return
    name = message.text if message.text != "-" else None
    await state.update_data(name=name)
    # Переходим к вводу VIN
    await state.set_state(AddCarStates.waiting_for_vin)
    await message.answer(
        "🔍 Введите VIN-номер автомобиля (17 символов).\n"
        "Это поможет при поиске запчастей.\n"
        "Если не хотите указывать, отправьте '-'.",
        reply_markup=get_cancel_keyboard()
    )

@router.message(AddCarStates.waiting_for_vin)
async def process_vin(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_cars_submenu())
        return

    vin = message.text.upper().replace(" ", "")
    if vin != "-" and len(vin) != 17:
        await message.answer("❌ VIN должен содержать 17 символов. Попробуйте ещё раз или отправьте '-' чтобы пропустить.")
        return

    await state.update_data(vin=vin if vin != "-" else None)
    await state.set_state(AddCarStates.waiting_for_mileage)
    await message.answer(
        "📏 Введите текущий пробег в километрах:\n"
        "(Например: 150000 или 75.5 для тысяч)",
        reply_markup=get_cancel_keyboard()
    )

# ... (дальше функция process_mileage, process_fuel_type, confirm_car_addition без изменений, но в confirm нужно добавить vin)

@router.message(AddCarStates.waiting_for_mileage)
async def process_mileage(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_cars_submenu())
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
        await message.answer("❌ Пожалуйста, введите число (например, 150000)")

# ... (функции process_fuel_type, confirm_car_addition – без изменений, но в confirm нужно добавить поле vin)

@router.callback_query(AddCarStates.waiting_for_fuel_type, F.data.startswith("fuel_type_"))
async def process_fuel_type(callback: types.CallbackQuery, state: FSMContext):
    fuel_type = callback.data.split("_")[-1]
    await state.update_data(fuel_type=fuel_type)
    data = await state.get_data()

    required_keys = ['brand', 'model', 'year', 'mileage']
    missing_keys = [key for key in required_keys if key not in data]
    if missing_keys:
        await callback.message.edit_text(
            "❌ Ошибка: данные об автомобиле повреждены. Начните добавление заново."
        )
        await state.clear()
        await callback.answer()
        return

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
    if data.get('vin'):
        confirmation_text += f"VIN: {data['vin']}\n"
    confirmation_text += "\nВсё верно?"

    await callback.message.edit_text(confirmation_text)
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
        await message.answer("❌ Добавление отменено", reply_markup=get_cars_submenu())
        return

    data = await state.get_data()
    required_keys = ['brand', 'model', 'year', 'mileage', 'fuel_type']
    if not all(key in data for key in required_keys):
        await message.answer("❌ Ошибка: не все данные заполнены. Начните заново.")
        await state.clear()
        return

    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                is_premium=False
            )
            db.add(user)
            db.commit()

        car = Car(
            user_id=user.id,
            brand=data['brand'],
            model=data['model'],
            year=data['year'],
            name=data.get('name'),
            vin=data.get('vin'),            # сохраняем VIN
            current_mileage=data['mileage'],
            fuel_type=data['fuel_type']
        )
        db.add(car)
        db.commit()

        await message.answer(
            f"🚗 Автомобиль успешно добавлен!\n\n"
            f"{data['brand']} {data['model']} ({data['year']})\n"
            f"Текущий пробег: {data['mileage']:,.0f} км\n"
            f"VIN: {data.get('vin', 'не указан')}\n"
            f"ID автомобиля: {car.id}\n\n"
            f"Теперь вы можете добавлять заправки, обслуживание и отслеживать расходы.",
            reply_markup=get_cars_submenu()
        )
    await state.clear()

# ... (остальные функции update_mileage, delete_car остаются без изменений)
