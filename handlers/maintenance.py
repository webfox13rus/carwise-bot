import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta

from database import SessionLocal, Car, MaintenanceEvent, User, Part
from keyboards.main_menu import get_maintenance_submenu, get_cancel_keyboard
from config import config

router = Router()
logger = logging.getLogger(__name__)

class MaintenanceStates(StatesGroup):
    waiting_for_car = State()
    waiting_for_category = State()
    waiting_for_description = State()
    waiting_for_cost = State()
    waiting_for_mileage = State()
    waiting_for_part_name = State()
    waiting_for_part_interval_mileage = State()
    waiting_for_part_interval_months = State()
    waiting_for_photo = State()

@router.message(F.text == "🔧 Добавить событие")
async def add_maintenance_start(message: types.Message, state: FSMContext):
    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь, отправив /start")
            return
        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("У вас нет автомобилей. Сначала добавьте авто.", reply_markup=get_maintenance_submenu())
            return
        # Сохраняем список авто в состоянии
        await state.update_data(cars=[(car.id, f"{car.brand} {car.model} {car.year}") for car in cars])
        await state.set_state(MaintenanceStates.waiting_for_car)
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=name, callback_data=f"car_{car_id}")] for car_id, name in cars
        ])
        await message.answer("Выберите автомобиль:", reply_markup=keyboard)

@router.callback_query(MaintenanceStates.waiting_for_car, F.data.startswith("car_"))
async def car_selected(callback: types.CallbackQuery, state: FSMContext):
    car_id = int(callback.data.split("_")[1])
    await state.update_data(car_id=car_id)
    await state.set_state(MaintenanceStates.waiting_for_category)
    await callback.message.edit_text(
        "Выберите категорию обслуживания:",
        reply_markup=get_maintenance_categories_keyboard()
    )
    await callback.answer()

def get_maintenance_categories_keyboard():
    from config import config
    buttons = []
    for key, value in config.MAINTENANCE_CATEGORIES.items():
        buttons.append([types.InlineKeyboardButton(text=value, callback_data=f"cat_{key}")])
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)

@router.callback_query(MaintenanceStates.waiting_for_category, F.data.startswith("cat_"))
async def category_chosen(callback: types.CallbackQuery, state: FSMContext):
    category_key = callback.data.split("_", 1)[1]
    from config import config
    category = config.MAINTENANCE_CATEGORIES.get(category_key, category_key)
    await state.update_data(category=category, category_key=category_key)

    if category_key == "parts":
        await state.set_state(MaintenanceStates.waiting_for_part_name)
        await callback.message.edit_text("Введите название детали (например, 'Тормозные колодки'):")
    else:
        await state.set_state(MaintenanceStates.waiting_for_description)
        await callback.message.edit_text("Введите описание события (можно кратко):")
    await callback.answer()

@router.message(MaintenanceStates.waiting_for_part_name)
async def part_name_entered(message: types.Message, state: FSMContext):
    part_name = message.text.strip()
    await state.update_data(part_name=part_name)
    await state.set_state(MaintenanceStates.waiting_for_part_interval_mileage)
    await message.answer(
        "Введите интервал замены по пробегу (в км) или отправьте /skip, если не нужен:",
        reply_markup=get_cancel_keyboard()
    )

@router.message(MaintenanceStates.waiting_for_part_interval_mileage)
async def part_interval_mileage_entered(message: types.Message, state: FSMContext):
    if message.text != "/skip":
        try:
            interval_mileage = float(message.text.strip().replace(",", ""))
            if interval_mileage <= 0:
                raise ValueError
        except ValueError:
            await message.answer("❌ Введите положительное число (км).")
            return
        await state.update_data(part_interval_mileage=interval_mileage)
    await state.set_state(MaintenanceStates.waiting_for_part_interval_months)
    await message.answer(
        "Введите интервал замены по времени (в месяцах) или отправьте /skip, если не нужен:"
    )

@router.message(MaintenanceStates.waiting_for_part_interval_months)
async def part_interval_months_entered(message: types.Message, state: FSMContext):
    if message.text != "/skip":
        try:
            interval_months = int(message.text.strip())
            if interval_months <= 0:
                raise ValueError
        except ValueError:
            await message.answer("❌ Введите целое положительное число (месяцы).")
            return
        await state.update_data(part_interval_months=interval_months)
    # Переходим к описанию (для детали описание может быть автоматическим)
    await state.update_data(description=f"Замена {message.text}")  # упростим
    await state.set_state(MaintenanceStates.waiting_for_cost)
    await message.answer("Введите стоимость (в рублях):")

@router.message(MaintenanceStates.waiting_for_description)
async def description_entered(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await state.set_state(MaintenanceStates.waiting_for_cost)
    await message.answer("Введите стоимость (в рублях):", reply_markup=get_cancel_keyboard())

@router.message(MaintenanceStates.waiting_for_cost)
async def cost_entered(message: types.Message, state: FSMContext):
    try:
        cost = float(message.text.strip().replace(",", ""))
        if cost <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректную стоимость (число больше 0).")
        return
    await state.update_data(cost=cost)
    await state.set_state(MaintenanceStates.waiting_for_mileage)
    await message.answer(
        "Введите пробег (в км) или отправьте /skip, чтобы пропустить:",
        reply_markup=get_cancel_keyboard()
    )

@router.message(MaintenanceStates.waiting_for_mileage)
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
    # Предложение добавить фото
    await state.set_state(MaintenanceStates.waiting_for_photo)
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Да, добавить фото", callback_data="photo_yes")],
        [types.InlineKeyboardButton(text="❌ Нет, сохранить без фото", callback_data="photo_no")]
    ])
    await message.answer("Хотите прикрепить фото чека?", reply_markup=keyboard)

@router.callback_query(MaintenanceStates.waiting_for_photo, F.data.in_({"photo_yes", "photo_no"}))
async def photo_decision(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "photo_yes":
        await state.set_state(MaintenanceStates.waiting_for_photo)
        await callback.message.edit_text("Отправьте фото чека.")
    else:
        await save_maintenance_event(callback.message, state, photo_id=None)
    await callback.answer()

@router.message(MaintenanceStates.waiting_for_photo, F.photo)
async def photo_received(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await save_maintenance_event(message, state, photo_id)

async def save_maintenance_event(message: types.Message, state: FSMContext, photo_id=None):
    data = await state.get_data()
    car_id = data.get("car_id")
    category = data.get("category")
    category_key = data.get("category_key")
    description = data.get("description", "")
    cost = data.get("cost")
    mileage = data.get("mileage")

    with SessionLocal() as db:
        car = db.query(Car).filter(Car.id == car_id).first()
        if car and mileage:
            car.current_mileage = mileage
            # Обновляем дату последнего ТО, если категория ТО
            if category_key == "to":
                car.last_maintenance_date = datetime.utcnow()
                car.last_maintenance_mileage = mileage
                # Сбрасываем флаги уведомлений
                car.notified_to_mileage = False
                car.notified_to_date = False
            db.commit()

        maint_event = MaintenanceEvent(
            car_id=car_id,
            category=category,
            description=description,
            cost=cost,
            mileage=mileage,
            photo_id=photo_id
        )
        db.add(maint_event)
        db.commit()
        logger.info(f"Событие обслуживания добавлено для авто {car_id}")

        # Если это замена детали (parts), создаём запись в Part
        if category_key == "parts":
            part_name = data.get("part_name")
            interval_mileage = data.get("part_interval_mileage")
            interval_months = data.get("part_interval_months")
            part = Part(
                car_id=car_id,
                name=part_name,
                interval_mileage=interval_mileage,
                interval_months=interval_months,
                last_mileage=mileage,
                last_date=datetime.utcnow(),
                notified=False
            )
            db.add(part)
            db.commit()
            logger.info(f"Деталь {part_name} добавлена в Part")

    await message.answer(
        f"✅ Событие '{category}' сохранено!\n"
        f"Стоимость: {cost:.2f} руб.\n"
        f"Пробег: {mileage:,.0f} км" if mileage else "Пробег не указан",
        reply_markup=get_maintenance_submenu()
    )
    await state.clear()

@router.message(F.text == "🔧 Плановые замены")
async def planned_replacements(message: types.Message):
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
        parts = db.query(Part).filter(Part.car_id.in_(car_ids)).all()
        if not parts:
            await message.answer("Нет данных о плановых заменах.", reply_markup=get_maintenance_submenu())
            return
        text = "🔧 *Плановые замены деталей*\n\n"
        today = datetime.utcnow().date()
        for part in parts:
            car = part.car
            if not car:
                continue
            text += f"• {car.brand} {car.model}:\n"
            text += f"  Деталь: {part.name}\n"
            if part.interval_mileage and part.last_mileage:
                next_mileage = part.last_mileage + part.interval_mileage
                remaining = next_mileage - car.current_mileage
                text += f"  По пробегу: осталось {remaining:,.0f} км (до {next_mileage:,.0f} км)\n"
            if part.interval_months and part.last_date:
                next_date = part.last_date + timedelta(days=30 * part.interval_months)
                days_left = (next_date.date() - today).days
                text += f"  По времени: осталось {days_left} дн. (до {next_date.strftime('%d.%m.%Y')})\n"
            text += "\n"
        await message.answer(text, parse_mode="Markdown", reply_markup=get_maintenance_submenu())

@router.message(F.text == "⏰ Напоминания ТО")
async def to_reminders_settings(message: types.Message):
    # Здесь должна быть логика настройки напоминаний ТО
    await message.answer("Функция настройки напоминаний ТО в разработке.", reply_markup=get_maintenance_submenu())

@router.message(F.text == "📸 Мои чеки обслуживания")
async def my_maintenance_photos(message: types.Message):
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
        events = db.query(MaintenanceEvent).filter(
            MaintenanceEvent.car_id.in_(car_ids),
            MaintenanceEvent.photo_id != None
        ).order_by(MaintenanceEvent.date.desc()).limit(10).all()
        if not events:
            await message.answer("У вас нет сохранённых чеков обслуживания.", reply_markup=get_maintenance_submenu())
            return
        for event in events:
            caption = f"{event.category} от {event.date.strftime('%d.%m.%Y')}\n{event.description}\nСтоимость: {event.cost:.2f} руб."
            await message.answer_photo(photo=event.photo_id, caption=caption)
        await message.answer("Это последние 10 чеков.", reply_markup=get_maintenance_submenu())
