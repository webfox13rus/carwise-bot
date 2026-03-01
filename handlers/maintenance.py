import logging
from datetime import datetime
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import func

from database import get_db, Car, MaintenanceEvent, User, Part
from keyboards.main_menu import get_main_menu, get_maintenance_submenu, get_cancel_keyboard
from config import config

router = Router()
logger = logging.getLogger(__name__)

class AddMaintenance(StatesGroup):
    waiting_for_car = State()
    waiting_for_category = State()
    waiting_for_description = State()
    waiting_for_cost = State()
    waiting_for_mileage = State()
    waiting_for_part_interval_mileage = State()
    waiting_for_part_interval_months = State()
    waiting_for_photo = State()

def make_car_keyboard(cars):
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[])
    for car in cars:
        keyboard.inline_keyboard.append([
            types.InlineKeyboardButton(
                text=f"{car.brand} {car.model} - {car.current_mileage:,.0f} км",
                callback_data=f"maint_car_{car.id}"
            )
        ])
    return keyboard

def get_category_keyboard():
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[])
    for code, name in config.MAINTENANCE_CATEGORIES.items():
        keyboard.inline_keyboard.append([
            types.InlineKeyboardButton(text=name, callback_data=f"maint_cat_{code}")
        ])
    return keyboard

@router.message(F.text == "🔧 Добавить событие")
@router.message(Command("add_maintenance"))
async def add_maintenance_start(message: types.Message, state: FSMContext):
    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала добавьте автомобиль через /add_car")
            return
        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("У вас нет автомобилей. Сначала добавьте через /add_car")
            return

        if len(cars) == 1:
            await state.update_data(car_id=cars[0].id)
            await state.set_state(AddMaintenance.waiting_for_category)
            await message.answer(
                f"🔧 {cars[0].brand} {cars[0].model}\n"
                f"Текущий пробег: {cars[0].current_mileage:,.0f} км\n\n"
                "Выберите категорию обслуживания:",
                reply_markup=get_category_keyboard()
            )
        else:
            await state.set_state(AddMaintenance.waiting_for_car)
            await message.answer(
                "Выберите автомобиль:",
                reply_markup=make_car_keyboard(cars)
            )

@router.callback_query(F.data.startswith("maint_car_"))
async def process_car_choice(callback: types.CallbackQuery, state: FSMContext):
    car_id = int(callback.data.split("_")[-1])
    await state.update_data(car_id=car_id)
    await state.set_state(AddMaintenance.waiting_for_category)
    with next(get_db()) as db:
        car = db.query(Car).filter(Car.id == car_id).first()
        await callback.message.edit_text(
            f"🔧 {car.brand} {car.model}\n"
            f"Текущий пробег: {car.current_mileage:,.0f} км\n\n"
            "Выберите категорию обслуживания:",
            reply_markup=get_category_keyboard()
        )
    await callback.answer()

@router.callback_query(AddMaintenance.waiting_for_category, F.data.startswith("maint_cat_"))
async def process_category(callback: types.CallbackQuery, state: FSMContext):
    category = callback.data.split("_")[-1]
    await state.update_data(category=category)
    
    if category == "to":
        # Для ТО описание фиксированное
        await state.update_data(description="Плановое ТО")
        await state.set_state(AddMaintenance.waiting_for_cost)
        await callback.message.edit_text(
            f"Категория: {config.MAINTENANCE_CATEGORIES.get(category, category)}\n"
            "Описание: Плановое ТО (автоматически)\n\n"
            "Введите стоимость в рублях:"
        )
        await callback.message.answer(
            "Введите стоимость:",
            reply_markup=get_cancel_keyboard()
        )
    
    else:
        # Для остальных категорий запрашиваем описание с примером, зависящим от категории
        await state.set_state(AddMaintenance.waiting_for_description)
        
        # Выбираем пример в зависимости от категории
        if category == "parts":
            example = "например: тормозные колодки, свечи зажигания"
        elif category == "fluids":
            example = "например: масло моторное, антифриз"
        elif category == "tires":
            example = "например: шиномонтаж, балансировка"
        elif category == "wash":
            example = "например: мойка кузова, химчистка"
        elif category == "repair":
            example = "например: ремонт подвески, диагностика"
        else:
            example = "например: замена масла, шиномонтаж"  # для других категорий (другое)
        
        await callback.message.edit_text(
            f"Категория: {config.MAINTENANCE_CATEGORIES.get(category, category)}\n\n"
            f"Введите, что сделали ({example}):"
        )
        await callback.message.answer(
            "Для отмены нажмите кнопку ниже:",
            reply_markup=get_cancel_keyboard()
        )
    
    await callback.answer()

@router.message(AddMaintenance.waiting_for_description)
async def process_description(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_maintenance_submenu())
        return
    await state.update_data(description=message.text)
    await state.set_state(AddMaintenance.waiting_for_cost)
    await message.answer(
        "Введите стоимость в рублях:",
        reply_markup=get_cancel_keyboard()
    )

@router.message(AddMaintenance.waiting_for_cost)
async def process_cost(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_maintenance_submenu())
        return
    try:
        cost = float(message.text.replace(',', '.'))
        await state.update_data(cost=cost)
        await state.set_state(AddMaintenance.waiting_for_mileage)
        await message.answer(
            "Введите пробег на момент обслуживания (в км):",
            reply_markup=get_cancel_keyboard()
        )
    except ValueError:
        await message.answer("❌ Введите число (например, 2500)")

@router.message(AddMaintenance.waiting_for_mileage)
async def process_mileage(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_maintenance_submenu())
        return
    try:
        mileage = float(message.text.replace(',', '.'))
        data = await state.get_data()
        car_id = data['car_id']
        category = data['category']
        description = data['description']
        cost = data['cost']

        with next(get_db()) as db:
            car = db.query(Car).filter(Car.id == car_id).first()
            if car and mileage > car.current_mileage:
                car.current_mileage = mileage

            if category == "to":
                car.last_maintenance_mileage = mileage
                car.last_maintenance_date = datetime.utcnow()
                car.notified_to_mileage = False
                car.notified_to_date = False
                db.commit()
            elif category == "parts" or category == "fluids":
                await state.update_data(part_mileage=mileage, part_date=datetime.utcnow())
                db.commit()
                await state.set_state(AddMaintenance.waiting_for_part_interval_mileage)
                await message.answer(
                    "Укажите интервал замены этого элемента по пробегу (в км).\n"
                    "Если интервал не нужен, отправьте 0:",
                    reply_markup=get_cancel_keyboard()
                )
                return
            else:
                db.commit()

        category_name = config.MAINTENANCE_CATEGORIES.get(category, category)
        await message.answer(
            f"✅ Обслуживание добавлено!\n\n"
            f"Категория: {category_name}\n"
            f"{description}\n"
            f"Стоимость: {cost:.2f} ₽\n"
            f"Пробег: {mileage:,.0f} км",
            reply_markup=get_maintenance_submenu()
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите число (например, 150000)")

@router.message(AddMaintenance.waiting_for_part_interval_mileage)
async def process_part_interval_mileage(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_maintenance_submenu())
        return
    try:
        interval_mileage = float(message.text.replace(',', '.'))
        if interval_mileage < 0:
            await message.answer("❌ Интервал не может быть отрицательным. Введите число >=0:")
            return
        await state.update_data(part_interval_mileage=interval_mileage if interval_mileage > 0 else None)
        await state.set_state(AddMaintenance.waiting_for_part_interval_months)
        await message.answer(
            "Укажите интервал замены по времени (в месяцах).\n"
            "Если интервал не нужен, отправьте 0:",
            reply_markup=get_cancel_keyboard()
        )
    except ValueError:
        await message.answer("❌ Введите число (например, 10000)")

@router.message(AddMaintenance.waiting_for_part_interval_months)
async def process_part_interval_months(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_maintenance_submenu())
        return
    try:
        interval_months = int(message.text)
        if interval_months < 0:
            await message.answer("❌ Интервал не может быть отрицательным. Введите целое число >=0:")
            return
        data = await state.get_data()
        car_id = data['car_id']
        description = data['description']
        part_mileage = data['part_mileage']
        part_date = data['part_date']
        interval_mileage = data.get('part_interval_mileage')
        interval_months = interval_months if interval_months > 0 else None

        with next(get_db()) as db:
            part = db.query(Part).filter(
                Part.car_id == car_id,
                Part.name == description
            ).first()
            if part:
                part.last_mileage = part_mileage
                part.last_date = part_date
                part.interval_mileage = interval_mileage
                part.interval_months = interval_months
                part.notified = False
            else:
                part = Part(
                    car_id=car_id,
                    name=description,
                    last_mileage=part_mileage,
                    last_date=part_date,
                    interval_mileage=interval_mileage,
                    interval_months=interval_months,
                    notified=False
                )
                db.add(part)
            db.commit()

        await state.set_state(AddMaintenance.waiting_for_photo)
        await message.answer(
            "Теперь вы можете прикрепить фото чека (необязательно).",
            reply_markup=types.ReplyKeyboardMarkup(
                keyboard=[[types.KeyboardButton(text="⏭ Пропустить")]],
                resize_keyboard=True
            )
        )
    except ValueError:
        await message.answer("❌ Введите целое число (например, 12)")

@router.message(AddMaintenance.waiting_for_photo, F.photo)
async def process_maintenance_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    await save_maintenance_event(message, state)

@router.message(AddMaintenance.waiting_for_photo, F.text == "⏭ Пропустить")
async def skip_maintenance_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo_id=None)
    await save_maintenance_event(message, state)

async def save_maintenance_event(message: types.Message, state: FSMContext):
    data = await state.get_data()
    car_id = data['car_id']
    category = data['category']
    description = data['description']
    cost = data['cost']
    mileage = data.get('mileage') or data.get('part_mileage')
    photo_id = data.get('photo_id')

    with next(get_db()) as db:
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

    category_name = config.MAINTENANCE_CATEGORIES.get(category, category)
    await message.answer(
        f"✅ Обслуживание добавлено!\n\n"
        f"Категория: {category_name}\n"
        f"{description}\n"
        f"Стоимость: {cost:.2f} ₽\n"
        f"Пробег: {mileage:,.0f} км",
        reply_markup=get_maintenance_submenu()
    )
    await state.clear()
