import logging
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import func

from states.car_states import AddCarStates, MileageUpdateStates
from keyboards.main_menu import get_main_menu, get_cancel_keyboard, get_fuel_types_keyboard
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

# ------------------- Просмотр автомобилей (с информацией о страховке и ТО) -------------------
@router.message(F.text == "🚗 Мои автомобили")
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
                reply_markup=get_main_menu()
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
                f"{insurance_info}"
                f"{next_to_info}"
                f"ID: {car.id}\n"
            )
            if car.name:
                response += f"Имя: {car.name}\n"
            response += "────────────\n\n"
        await message.answer(response, reply_markup=get_main_menu())

# ------------------- Добавление автомобиля (с проверкой лимита) -------------------
@router.message(F.text == "➕ Добавить авто")
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
        
        # Проверяем, является ли пользователь администратором
        is_admin = message.from_user.id in config.ADMIN_IDS
        
        if car_count >= 1 and not user.is_premium and not is_admin:
            await message.answer(
                "❌ *Добавление второго автомобиля* – платная функция.\n\n"
                "Сейчас вы можете добавить только один автомобиль. "
                "Чтобы добавить больше, приобретите подписку. Функция подписки находится в разработке и будет доступна позже.",
                parse_mode="Markdown",
                reply_markup=get_main_menu()
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
    await callback.message.answer("Главное меню:", reply_markup=get_main_menu())
    await callback.answer()

# Выбор марки (callback)
@router.callback_query(F.data.startswith("brand:"))
async def process_brand_callback(callback: types.CallbackQuery, state: FSMContext):
    brand = callback.data.split(":", 1)[1]
    if brand == "manual":
        await state.set_state(AddCarStates.waiting_for_brand_manual)
        await callback.message.edit_text("Введите марку автомобиля вручную:")
        await callback.answer()
        return

    await state.update_data(brand=brand)
    models = get_models_for_brand(brand)
    if models:
        keyboard = make_inline_keyboard(models, f"model:{brand}")
        await callback.message.edit_text(
            f"Выбрана марка: {brand}\nТеперь выберите модель или введите вручную:",
            reply_markup=keyboard
        )
        await state.set_state(AddCarStates.waiting_for_model)
    else:
        await state.set_state(AddCarStates.waiting_for_model_manual)
        await callback.message.edit_text(
            f"Выбрана марка: {brand}\nВведите модель автомобиля вручную:"
        )
    await callback.answer()

# Ручной ввод марки
@router.message(AddCarStates.waiting_for_brand_manual)
async def process_brand_manual(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_main_menu())
        return
    brand = message.text.strip()
    await state.update_data(brand=brand)
    await state.set_state(AddCarStates.waiting_for_model_manual)
    await message.answer(
        f"Марка: {brand}\nВведите модель автомобиля:",
        reply_markup=get_cancel_keyboard()
    )

# Выбор модели (callback)
@router.callback_query(F.data.startswith("model:"))
async def process_model_callback(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split(":", 2)
    brand = parts[1]
    model = parts[2] if len(parts) > 2 else None

    if model == "manual":
        await state.set_state(AddCarStates.waiting_for_model_manual)
        await callback.message.edit_text(f"Марка: {brand}\nВведите модель автомобиля вручную:")
        await callback.answer()
        return

    await state.update_data(brand=brand, model=model)
    await state.set_state(AddCarStates.waiting_for_year)
    await callback.message.edit_text(
        f"Марка: {brand}\nМодель: {model}\n\nТеперь введите год выпуска (например, 2015):"
    )
    await callback.answer()

# Ручной ввод модели
@router.message(AddCarStates.waiting_for_model_manual)
async def process_model_manual(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_main_menu())
        return
    model = message.text.strip()
    data = await state.get_data()
    brand = data.get('brand', '')
    await state.update_data(model=model)
    await state.set_state(AddCarStates.waiting_for_year)
    await message.answer(
        f"Марка: {brand}\nМодель: {model}\n\nВведите год выпуска (например, 2015):",
        reply_markup=get_cancel_keyboard()
    )

# Ввод года
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
        await message.answer("❌ Пожалуйста, введите число (например, 2015)")

# Ввод имени (опционально)
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

# Ввод пробега
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
        await message.answer("❌ Пожалуйста, введите число (например, 150000)")

# Выбор типа топлива (callback) с защитой от KeyError
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

# Подтверждение добавления
@router.message(AddCarStates.waiting_for_fuel_type, F.text.in_(["✅ Да, добавить", "❌ Нет, исправить"]))
async def confirm_car_addition(message: types.Message, state: FSMContext):
    if message.text == "❌ Нет, исправить":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_main_menu())
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

# ------------------- Обновление пробега -------------------
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
        await message.answer("❌ Пожалуйста, введите число (например, 150500)")

# ------------------- Удаление автомобиля -------------------
class DeleteCarStates(StatesGroup):
    waiting_for_confirmation = State()

@router.message(F.text == "🗑 Удалить авто")
@router.message(Command("delete_car"))
async def delete_car_start(message: types.Message, state: FSMContext):
    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь, отправив /start")
            return
        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("🚫 У вас нет активных автомобилей для удаления.", reply_markup=get_main_menu())
            return

        if len(cars) == 1:
            await state.update_data(car_id=cars[0].id, car_name=f"{cars[0].brand} {cars[0].model}")
            await state.set_state(DeleteCarStates.waiting_for_confirmation)
            await message.answer(
                f"⚠️ Вы действительно хотите удалить автомобиль *{cars[0].brand} {cars[0].model}*?\n"
                "Все данные о заправках, обслуживании и страховках останутся в базе, но авто исчезнет из списков.\n\n"
                "Подтвердите удаление:",
                reply_markup=types.ReplyKeyboardMarkup(
                    keyboard=[
                        [types.KeyboardButton(text="✅ Да, удалить")],
                        [types.KeyboardButton(text="❌ Нет, отмена")]
                    ],
                    resize_keyboard=True
                ),
                parse_mode="Markdown"
            )
        else:
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[])
            for car in cars:
                keyboard.inline_keyboard.append([
                    types.InlineKeyboardButton(
                        text=f"{car.brand} {car.model} - {car.current_mileage:,.0f} км",
                        callback_data=f"delete_car_{car.id}"
                    )
                ])
            await message.answer(
                "Выберите автомобиль для удаления:",
                reply_markup=keyboard
            )

@router.callback_query(F.data.startswith("delete_car_"))
async def delete_car_callback(callback: types.CallbackQuery, state: FSMContext):
    car_id = int(callback.data.split("_")[-1])
    with next(get_db()) as db:
        car = db.query(Car).filter(Car.id == car_id).first()
        if not car:
            await callback.message.edit_text("❌ Автомобиль не найден.")
            await callback.answer()
            return
        await state.update_data(car_id=car_id, car_name=f"{car.brand} {car.model}")
        await state.set_state(DeleteCarStates.waiting_for_confirmation)
        await callback.message.edit_text(
            f"⚠️ Вы действительно хотите удалить автомобиль *{car.brand} {car.model}*?\n"
            "Все данные о заправках, обслуживании и страховках останутся в базе, но авто исчезнет из списков.\n\n"
            "Подтвердите удаление:",
            reply_markup=types.ReplyKeyboardMarkup(
                keyboard=[
                    [types.KeyboardButton(text="✅ Да, удалить")],
                    [types.KeyboardButton(text="❌ Нет, отмена")]
                ],
                resize_keyboard=True
            ),
            parse_mode="Markdown"
        )
    await callback.answer()

@router.message(DeleteCarStates.waiting_for_confirmation, F.text.in_(["✅ Да, удалить", "❌ Нет, отмена"]))
async def delete_car_confirm(message: types.Message, state: FSMContext):
    if message.text == "❌ Нет, отмена":
        await state.clear()
        await message.answer("❌ Удаление отменено", reply_markup=get_main_menu())
        return

    data = await state.get_data()
    car_id = data.get('car_id')
    car_name = data.get('car_name', 'Автомобиль')

    with next(get_db()) as db:
        car = db.query(Car).filter(Car.id == car_id).first()
        if car:
            car.is_active = False
            db.commit()
            await message.answer(
                f"✅ Автомобиль *{car_name}* успешно удалён из списка.\n"
                "Все связанные данные сохранены в истории.",
                reply_markup=get_main_menu(),
                parse_mode="Markdown"
            )
        else:
            await message.answer("❌ Ошибка: автомобиль не найден.", reply_markup=get_main_menu())

    await state.clear()
