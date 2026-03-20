import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta

from database import SessionLocal, Car, MaintenanceEvent, User, Part
from keyboards.main_menu import get_maintenance_submenu, get_cancel_keyboard, get_skip_keyboard
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
        cars_list = [(car.id, f"{car.brand} {car.model}") for car in cars]
        await state.update_data(cars=cars_list)
        await state.set_state(MaintenanceStates.waiting_for_car)
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=name, callback_data=f"car_{car_id}")] for car_id, name in cars_list
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
        # Устанавливаем автоматическое описание для некоторых категорий
        if category_key == "to":
            desc = "Техническое обслуживание"
        elif category_key == "wash":
            desc = "Мойка"
        elif category_key == "tires":
            desc = "Шиномонтаж"
        else:
            desc = None

        if desc:
            await state.update_data(description=desc)
            # Для мойки и шиномонтажа сразу переходим к стоимости, пропуская пробег
            if category_key in ("wash", "tires"):
                await state.set_state(MaintenanceStates.waiting_for_cost)
                await callback.message.edit_text("Введите стоимость (в рублях):")
            else:
                await state.set_state(MaintenanceStates.waiting_for_cost)
                await callback.message.edit_text("Введите стоимость (в рублях):")
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
        "Введите интервал замены по пробегу (в км) или нажмите 'Пропустить', если не нужен:",
        reply_markup=get_skip_keyboard()
    )

@router.message(MaintenanceStates.waiting_for_part_interval_mileage)
async def part_interval_mileage_entered(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_maintenance_submenu())
        return
    if message.text != "⏭ Пропустить":
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
        "Введите интервал замены по времени (в месяцах) или нажмите 'Пропустить', если не нужен:",
        reply_markup=get_skip_keyboard()
    )

@router.message(MaintenanceStates.waiting_for_part_interval_months)
async def part_interval_months_entered(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_maintenance_submenu())
        return
    if message.text != "⏭ Пропустить":
        try:
            interval_months = int(message.text.strip())
            if interval_months <= 0:
                raise ValueError
        except ValueError:
            await message.answer("❌ Введите целое положительное число (месяцы).")
            return
        await state.update_data(part_interval_months=interval_months)
    # Получаем part_name из состояния
    data = await state.get_data()
    part_name = data.get("part_name", "")
    await state.update_data(description=f"Замена {part_name}")
    await state.set_state(MaintenanceStates.waiting_for_cost)
    await message.answer("Введите стоимость (в рублях):", reply_markup=get_cancel_keyboard())

@router.message(MaintenanceStates.waiting_for_description)
async def description_entered(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_maintenance_submenu())
        return
    await state.update_data(description=message.text.strip())
    await state.set_state(MaintenanceStates.waiting_for_cost)
    await message.answer("Введите стоимость (в рублях):", reply_markup=get_cancel_keyboard())

@router.message(MaintenanceStates.waiting_for_cost)
async def cost_entered(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_maintenance_submenu())
        return
    try:
        cost = float(message.text.strip().replace(",", ""))
        if cost <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректную стоимость (число больше 0).")
        return
    await state.update_data(cost=cost)
    await state.set_state(MaintenanceStates.waiting_for_mileage)
    # Проверяем категорию: для мойки и шиномонтажа пропускаем пробег
    data = await state.get_data()
    category_key = data.get("category_key")
    if category_key in ("wash", "tires"):
        # Сразу переходим к фото
        await state.set_state(MaintenanceStates.waiting_for_photo)
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="✅ Да, добавить фото", callback_data="photo_yes")],
            [types.InlineKeyboardButton(text="❌ Нет, сохранить без фото", callback_data="photo_no")]
        ])
        await message.answer("Хотите прикрепить фото чека?", reply_markup=keyboard)
    else:
        await message.answer(
            "Введите пробег (в км) или нажмите 'Пропустить', чтобы пропустить:",
            reply_markup=get_skip_keyboard()
        )

@router.message(MaintenanceStates.waiting_for_mileage)
async def mileage_entered(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_maintenance_submenu())
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

    # Отправляем сообщение об успехе
    response = f"✅ Событие '{category}' сохранено!\nСтоимость: {cost:.2f} руб."
    if mileage:
        response += f"\nПробег: {mileage:,.0f} км"
    else:
        response += "\nПробег не указан"
    await message.answer(response, reply_markup=get_maintenance_submenu())

    # Если это ТО, предлагаем настроить интервалы следующего
    if category_key == "to":
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="✅ Да, настроить", callback_data="set_to_reminder")],
            [types.InlineKeyboardButton(text="❌ Нет, спасибо", callback_data="to_done")]
        ])
        await message.answer("Хотите настроить интервалы следующего ТО?", reply_markup=keyboard)

    await state.clear()

@router.callback_query(F.data == "set_to_reminder")
async def set_to_reminder_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Перейдите в раздел '⏰ Напоминания ТО' в меню обслуживания.")
    await callback.answer()
    await callback.message.delete()

@router.callback_query(F.data == "to_done")
async def to_done_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.answer()

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
async def to_reminders_settings(message: types.Message, state: FSMContext):
    # Перенаправляем на reminders
    from handlers.reminders import set_reminder_start
    await set_reminder_start(message, state)

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
