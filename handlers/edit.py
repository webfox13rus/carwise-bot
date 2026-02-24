import logging
from datetime import datetime
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import func

from database import get_db, Car, User, FuelEvent, MaintenanceEvent, Insurance
from keyboards.main_menu import get_main_menu, get_cancel_keyboard, get_fuel_types_keyboard
from config import config

router = Router()
logger = logging.getLogger(__name__)

# ------------------- Состояния для редактирования -------------------
class EditFuel(StatesGroup):
    waiting_for_car = State()
    waiting_for_event = State()
    waiting_for_amount = State()
    waiting_for_cost = State()
    waiting_for_mileage = State()
    waiting_for_fuel_type = State()
    waiting_for_photo = State()

class EditMaintenance(StatesGroup):
    waiting_for_car = State()
    waiting_for_event = State()
    waiting_for_category = State()
    waiting_for_description = State()
    waiting_for_cost = State()
    waiting_for_mileage = State()
    waiting_for_photo = State()

class EditInsurance(StatesGroup):
    waiting_for_car = State()
    waiting_for_event = State()
    waiting_for_end_date = State()
    waiting_for_cost = State()
    waiting_for_policy = State()
    waiting_for_company = State()
    waiting_for_notes = State()
    waiting_for_photo = State()

# ------------------- Вспомогательные функции -------------------
def make_car_keyboard(cars, action_prefix):
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[])
    for car in cars:
        keyboard.inline_keyboard.append([
            types.InlineKeyboardButton(
                text=f"{car.brand} {car.model}",
                callback_data=f"{action_prefix}_car_{car.id}"
            )
        ])
    return keyboard

def make_events_keyboard(events, action_prefix, event_type):
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[])
    for ev in events:
        if event_type == 'fuel':
            text = f"{ev.date.strftime('%d.%m.%Y')} – {ev.liters} л, {ev.cost} ₽"
        elif event_type == 'maint':
            cat = config.MAINTENANCE_CATEGORIES.get(ev.category, ev.category)
            text = f"{ev.date.strftime('%d.%m.%Y')} – {cat}: {ev.description[:20]}..."
        elif event_type == 'ins':
            text = f"{ev.end_date.strftime('%d.%m.%Y')} – {ev.cost} ₽"
        keyboard.inline_keyboard.append([
            types.InlineKeyboardButton(
                text=text,
                callback_data=f"{action_prefix}_ev_{ev.id}"
            )
        ])
    return keyboard

def get_category_keyboard():
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[])
    for code, name in config.MAINTENANCE_CATEGORIES.items():
        keyboard.inline_keyboard.append([
            types.InlineKeyboardButton(text=name, callback_data=f"edit_maint_cat_{code}")
        ])
    return keyboard

# ------------------- Главное меню редактирования -------------------
@router.message(F.text == "✏️ Редактировать запись")
@router.message(Command("edit"))
async def edit_main_menu(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="⛽ Заправка")],
            [types.KeyboardButton(text="🔧 Обслуживание")],
            [types.KeyboardButton(text="📄 Страховка")],
            [types.KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )
    await message.answer("Выберите тип записи для редактирования:", reply_markup=keyboard)

# ------------------- Редактирование заправок -------------------
@router.message(F.text == "⛽ Заправка")
async def edit_fuel_start(message: types.Message, state: FSMContext):
    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь, отправив /start")
            return
        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("У вас нет автомобилей.")
            return
        if len(cars) == 1:
            await state.update_data(car_id=cars[0].id)
            await show_fuel_events(message, state, cars[0].id)
        else:
            await state.set_state(EditFuel.waiting_for_car)
            await message.answer(
                "Выберите автомобиль:",
                reply_markup=make_car_keyboard(cars, "edit_fuel")
            )

async def show_fuel_events(message: types.Message, state: FSMContext, car_id: int):
    with next(get_db()) as db:
        events = db.query(FuelEvent).filter(FuelEvent.car_id == car_id).order_by(FuelEvent.date.desc()).limit(10).all()
        if not events:
            await message.answer("Нет заправок для этого авто.")
            await state.clear()
            return
        await state.set_state(EditFuel.waiting_for_event)
        await message.answer(
            "Выберите заправку для редактирования:",
            reply_markup=make_events_keyboard(events, "edit_fuel", "fuel")
        )

@router.callback_query(F.data.startswith("edit_fuel_car_"))
async def edit_fuel_car_callback(callback: types.CallbackQuery, state: FSMContext):
    car_id = int(callback.data.split("_")[-1])
    await state.update_data(car_id=car_id)
    await show_fuel_events(callback.message, state, car_id)
    await callback.answer()

# ИСПРАВЛЕНО
@router.callback_query(F.data.startswith("edit_fuel_ev_"))
async def edit_fuel_event_callback(callback: types.CallbackQuery, state: FSMContext):
    event_id = int(callback.data.split("_")[-1])
    await state.update_data(event_id=event_id)
    await state.set_state(EditFuel.waiting_for_amount)
    await callback.message.edit_text(
        "Введите новое количество литров (или отправьте '0' для пропуска):",
        reply_markup=None  # убираем клавиатуру
    )
    await callback.message.answer(
        "Введите число:",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()

@router.message(EditFuel.waiting_for_amount)
async def edit_fuel_amount(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Редактирование отменено", reply_markup=get_main_menu())
        return
    try:
        amount = float(message.text.replace(',', '.'))
        await state.update_data(amount=amount)
        await state.set_state(EditFuel.waiting_for_cost)
        await message.answer(
            "Введите новую сумму в рублях (или '0' для пропуска):",
            reply_markup=get_cancel_keyboard()
        )
    except ValueError:
        await message.answer("❌ Введите число (например, 45.5)")

@router.message(EditFuel.waiting_for_cost)
async def edit_fuel_cost(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Редактирование отменено", reply_markup=get_main_menu())
        return
    try:
        cost = float(message.text.replace(',', '.'))
        await state.update_data(cost=cost)
        await state.set_state(EditFuel.waiting_for_mileage)
        await message.answer(
            "Введите новый пробег (или '0' для пропуска):",
            reply_markup=get_cancel_keyboard()
        )
    except ValueError:
        await message.answer("❌ Введите число (например, 2500)")

@router.message(EditFuel.waiting_for_mileage)
async def edit_fuel_mileage(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Редактирование отменено", reply_markup=get_main_menu())
        return
    try:
        mileage = float(message.text.replace(',', '.'))
        await state.update_data(mileage=mileage)
        await state.set_state(EditFuel.waiting_for_fuel_type)
        await message.answer(
            "Выберите новый тип топлива:",
            reply_markup=get_fuel_types_keyboard()
        )
    except ValueError:
        await message.answer("❌ Введите число (например, 150000)")

@router.callback_query(EditFuel.waiting_for_fuel_type, F.data.startswith("fuel_type_"))
async def edit_fuel_type(callback: types.CallbackQuery, state: FSMContext):
    fuel_type = callback.data.split("_")[-1]
    await state.update_data(fuel_type=fuel_type)
    await state.set_state(EditFuel.waiting_for_photo)
    await callback.message.delete()
    await callback.message.answer(
        "Отправьте новое фото чека (или нажмите кнопку 'Пропустить'):",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="⏭ Пропустить")]],
            resize_keyboard=True
        )
    )
    await callback.answer()

@router.message(EditFuel.waiting_for_photo, F.photo)
async def edit_fuel_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    await save_edited_fuel(message, state)

@router.message(EditFuel.waiting_for_photo, F.text == "⏭ Пропустить")
async def edit_fuel_skip_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo_id=None)
    await save_edited_fuel(message, state)

async def save_edited_fuel(message: types.Message, state: FSMContext):
    data = await state.get_data()
    event_id = data['event_id']
    new_amount = data.get('amount')
    new_cost = data.get('cost')
    new_mileage = data.get('mileage')
    new_fuel_type = data.get('fuel_type')
    new_photo = data.get('photo_id')

    with next(get_db()) as db:
        event = db.query(FuelEvent).filter(FuelEvent.id == event_id).first()
        if not event:
            await message.answer("❌ Запись не найдена")
            await state.clear()
            return
        if new_amount and new_amount > 0:
            event.liters = new_amount
        if new_cost and new_cost > 0:
            event.cost = new_cost
        if new_mileage and new_mileage > 0:
            event.mileage = new_mileage
        if new_fuel_type:
            event.fuel_type = new_fuel_type
        if new_photo is not None:
            event.photo_id = new_photo if new_photo else None
        db.commit()

    await message.answer("✅ Заправка отредактирована!", reply_markup=get_main_menu())
    await state.clear()

# ------------------- Редактирование обслуживания -------------------
@router.message(F.text == "🔧 Обслуживание")
async def edit_maint_start(message: types.Message, state: FSMContext):
    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь, отправив /start")
            return
        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("У вас нет автомобилей.")
            return
        if len(cars) == 1:
            await state.update_data(car_id=cars[0].id)
            await show_maint_events(message, state, cars[0].id)
        else:
            await state.set_state(EditMaintenance.waiting_for_car)
            await message.answer(
                "Выберите автомобиль:",
                reply_markup=make_car_keyboard(cars, "edit_maint")
            )

async def show_maint_events(message: types.Message, state: FSMContext, car_id: int):
    with next(get_db()) as db:
        events = db.query(MaintenanceEvent).filter(MaintenanceEvent.car_id == car_id).order_by(MaintenanceEvent.date.desc()).limit(10).all()
        if not events:
            await message.answer("Нет событий обслуживания для этого авто.")
            await state.clear()
            return
        await state.set_state(EditMaintenance.waiting_for_event)
        await message.answer(
            "Выберите событие для редактирования:",
            reply_markup=make_events_keyboard(events, "edit_maint", "maint")
        )

@router.callback_query(F.data.startswith("edit_maint_car_"))
async def edit_maint_car_callback(callback: types.CallbackQuery, state: FSMContext):
    car_id = int(callback.data.split("_")[-1])
    await state.update_data(car_id=car_id)
    await show_maint_events(callback.message, state, car_id)
    await callback.answer()

# ИСПРАВЛЕНО
@router.callback_query(F.data.startswith("edit_maint_ev_"))
async def edit_maint_event_callback(callback: types.CallbackQuery, state: FSMContext):
    event_id = int(callback.data.split("_")[-1])
    await state.update_data(event_id=event_id)
    await state.set_state(EditMaintenance.waiting_for_category)
    await callback.message.edit_text(
        "Выберите новую категорию (или отправьте '0' для пропуска):",
        reply_markup=get_category_keyboard()  # это inline-клавиатура, можно оставить
    )
    await callback.message.answer(
        "Выберите категорию:",
        reply_markup=None  # но здесь не нужно дополнительное сообщение
    )
    await callback.answer()

@router.callback_query(EditMaintenance.waiting_for_category, F.data.startswith("edit_maint_cat_"))
async def edit_maint_category(callback: types.CallbackQuery, state: FSMContext):
    category = callback.data.split("_")[-1]
    await state.update_data(category=category)
    await state.set_state(EditMaintenance.waiting_for_description)
    await callback.message.edit_text(
        "Введите новое описание (или отправьте '0' для пропуска):",
        reply_markup=None  # убираем клавиатуру
    )
    await callback.message.answer(
        "Введите описание:",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()

@router.message(EditMaintenance.waiting_for_description)
async def edit_maint_description(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Редактирование отменено", reply_markup=get_main_menu())
        return
    desc = message.text if message.text != "0" else None
    await state.update_data(description=desc)
    await state.set_state(EditMaintenance.waiting_for_cost)
    await message.answer(
        "Введите новую стоимость (или '0' для пропуска):",
        reply_markup=get_cancel_keyboard()
    )

@router.message(EditMaintenance.waiting_for_cost)
async def edit_maint_cost(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Редактирование отменено", reply_markup=get_main_menu())
        return
    try:
        cost = float(message.text.replace(',', '.')) if message.text != "0" else None
        await state.update_data(cost=cost)
        await state.set_state(EditMaintenance.waiting_for_mileage)
        await message.answer(
            "Введите новый пробег (или '0' для пропуска):",
            reply_markup=get_cancel_keyboard()
        )
    except ValueError:
        await message.answer("❌ Введите число")

@router.message(EditMaintenance.waiting_for_mileage)
async def edit_maint_mileage(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Редактирование отменено", reply_markup=get_main_menu())
        return
    try:
        mileage = float(message.text.replace(',', '.')) if message.text != "0" else None
        await state.update_data(mileage=mileage)
        await state.set_state(EditMaintenance.waiting_for_photo)
        await message.answer(
            "Отправьте новое фото чека (или нажмите кнопку 'Пропустить'):",
            reply_markup=types.ReplyKeyboardMarkup(
                keyboard=[[types.KeyboardButton(text="⏭ Пропустить")]],
                resize_keyboard=True
            )
        )
    except ValueError:
        await message.answer("❌ Введите число")

@router.message(EditMaintenance.waiting_for_photo, F.photo)
async def edit_maint_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    await save_edited_maint(message, state)

@router.message(EditMaintenance.waiting_for_photo, F.text == "⏭ Пропустить")
async def edit_maint_skip_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo_id=None)
    await save_edited_maint(message, state)

async def save_edited_maint(message: types.Message, state: FSMContext):
    data = await state.get_data()
    event_id = data['event_id']
    new_category = data.get('category')
    new_description = data.get('description')
    new_cost = data.get('cost')
    new_mileage = data.get('mileage')
    new_photo = data.get('photo_id')

    with next(get_db()) as db:
        event = db.query(MaintenanceEvent).filter(MaintenanceEvent.id == event_id).first()
        if not event:
            await message.answer("❌ Запись не найдена")
            await state.clear()
            return
        if new_category:
            event.category = new_category
        if new_description:
            event.description = new_description
        if new_cost is not None:
            event.cost = new_cost
        if new_mileage is not None:
            event.mileage = new_mileage
        if new_photo is not None:
            event.photo_id = new_photo if new_photo else None
        db.commit()

    await message.answer("✅ Обслуживание отредактировано!", reply_markup=get_main_menu())
    await state.clear()

# ------------------- Редактирование страховок -------------------
@router.message(F.text == "📄 Страховка")
async def edit_ins_start(message: types.Message, state: FSMContext):
    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь, отправив /start")
            return
        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("У вас нет автомобилей.")
            return
        if len(cars) == 1:
            await state.update_data(car_id=cars[0].id)
            await show_ins_events(message, state, cars[0].id)
        else:
            await state.set_state(EditInsurance.waiting_for_car)
            await message.answer(
                "Выберите автомобиль:",
                reply_markup=make_car_keyboard(cars, "edit_ins")
            )

async def show_ins_events(message: types.Message, state: FSMContext, car_id: int):
    with next(get_db()) as db:
        events = db.query(Insurance).filter(Insurance.car_id == car_id).order_by(Insurance.end_date.desc()).limit(10).all()
        if not events:
            await message.answer("Нет страховок для этого авто.")
            await state.clear()
            return
        await state.set_state(EditInsurance.waiting_for_event)
        await message.answer(
            "Выберите страховку для редактирования:",
            reply_markup=make_events_keyboard(events, "edit_ins", "ins")
        )

@router.callback_query(F.data.startswith("edit_ins_car_"))
async def edit_ins_car_callback(callback: types.CallbackQuery, state: FSMContext):
    car_id = int(callback.data.split("_")[-1])
    await state.update_data(car_id=car_id)
    await show_ins_events(callback.message, state, car_id)
    await callback.answer()

# ИСПРАВЛЕНО
@router.callback_query(F.data.startswith("edit_ins_ev_"))
async def edit_ins_event_callback(callback: types.CallbackQuery, state: FSMContext):
    event_id = int(callback.data.split("_")[-1])
    await state.update_data(event_id=event_id)
    await state.set_state(EditInsurance.waiting_for_end_date)
    await callback.message.edit_text(
        "Введите новую дату окончания в формате ДД.ММ.ГГГГ (или '0' для пропуска):",
        reply_markup=None
    )
    await callback.message.answer(
        "Введите дату:",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()

@router.message(EditInsurance.waiting_for_end_date)
async def edit_ins_end_date(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Редактирование отменено", reply_markup=get_main_menu())
        return
    try:
        if message.text == "0":
            end_date = None
        else:
            end_date = datetime.strptime(message.text.strip(), "%d.%m.%Y")
        await state.update_data(end_date=end_date)
        await state.set_state(EditInsurance.waiting_for_cost)
        await message.answer(
            "Введите новую стоимость (или '0' для пропуска):",
            reply_markup=get_cancel_keyboard()
        )
    except ValueError:
        await message.answer("❌ Неверный формат. Введите дату в формате ДД.ММ.ГГГГ")

@router.message(EditInsurance.waiting_for_cost)
async def edit_ins_cost(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Редактирование отменено", reply_markup=get_main_menu())
        return
    try:
        cost = float(message.text.replace(',', '.')) if message.text != "0" else None
        await state.update_data(cost=cost)
        await state.set_state(EditInsurance.waiting_for_policy)
        await message.answer(
            "Введите новый номер полиса (или отправьте '0' для пропуска):",
            reply_markup=get_cancel_keyboard()
        )
    except ValueError:
        await message.answer("❌ Введите число")

@router.message(EditInsurance.waiting_for_policy)
async def edit_ins_policy(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Редактирование отменено", reply_markup=get_main_menu())
        return
    policy = message.text if message.text != "0" else None
    await state.update_data(policy=policy)
    await state.set_state(EditInsurance.waiting_for_company)
    await message.answer(
        "Введите новую страховую компанию (или '0' для пропуска):",
        reply_markup=get_cancel_keyboard()
    )

@router.message(EditInsurance.waiting_for_company)
async def edit_ins_company(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Редактирование отменено", reply_markup=get_main_menu())
        return
    company = message.text if message.text != "0" else None
    await state.update_data(company=company)
    await state.set_state(EditInsurance.waiting_for_notes)
    await message.answer(
        "Введите новые примечания (или '0' для пропуска):",
        reply_markup=get_cancel_keyboard()
    )

@router.message(EditInsurance.waiting_for_notes)
async def edit_ins_notes(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Редактирование отменено", reply_markup=get_main_menu())
        return
    notes = message.text if message.text != "0" else None
    await state.update_data(notes=notes)
    await state.set_state(EditInsurance.waiting_for_photo)
    await message.answer(
        "Отправьте новое фото чека (или нажмите кнопку 'Пропустить'):",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="⏭ Пропустить")]],
            resize_keyboard=True
        )
    )

@router.message(EditInsurance.waiting_for_photo, F.photo)
async def edit_ins_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    await save_edited_ins(message, state)

@router.message(EditInsurance.waiting_for_photo, F.text == "⏭ Пропустить")
async def edit_ins_skip_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo_id=None)
    await save_edited_ins(message, state)

async def save_edited_ins(message: types.Message, state: FSMContext):
    data = await state.get_data()
    event_id = data['event_id']
    new_end_date = data.get('end_date')
    new_cost = data.get('cost')
    new_policy = data.get('policy')
    new_company = data.get('company')
    new_notes = data.get('notes')
    new_photo = data.get('photo_id')

    with next(get_db()) as db:
        event = db.query(Insurance).filter(Insurance.id == event_id).first()
        if not event:
            await message.answer("❌ Запись не найдена")
            await state.clear()
            return
        if new_end_date:
            event.end_date = new_end_date
        if new_cost is not None:
            event.cost = new_cost
        if new_policy:
            event.policy_number = new_policy
        if new_company:
            event.company = new_company
        if new_notes:
            event.notes = new_notes
        if new_photo is not None:
            event.photo_id = new_photo if new_photo else None
        db.commit()

    await message.answer("✅ Страховка отредактирована!", reply_markup=get_main_menu())
    await state.clear()
