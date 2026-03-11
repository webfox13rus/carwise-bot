import logging
from datetime import datetime
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import func

rom database import SessionLocal, Car, User, Insurance
from keyboards.main_menu import get_main_menu, get_insurance_submenu, get_cancel_keyboard
from config import config

router = Router()
logger = logging.getLogger(__name__)

class AddInsurance(StatesGroup):
    waiting_for_car = State()
    waiting_for_end_date = State()
    waiting_for_cost = State()
    waiting_for_policy = State()
    waiting_for_company = State()
    waiting_for_notes = State()
    waiting_for_photo = State()

def make_car_keyboard(cars):
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[])
    for car in cars:
        keyboard.inline_keyboard.append([
            types.InlineKeyboardButton(
                text=f"{car.brand} {car.model} - {car.current_mileage:,.0f} км",
                callback_data=f"ins_car_{car.id}"
            )
        ])
    return keyboard

@router.message(F.text == "📄 Страховки")
async def insurance_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Управление страховками:", reply_markup=get_insurance_submenu())

@router.message(F.text == "📄 Добавить страховку")
@router.message(Command("add_insurance"))
async def add_insurance_start(message: types.Message, state: FSMContext):
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
            await state.set_state(AddInsurance.waiting_for_end_date)
            await message.answer(
                f"📄 Добавление страховки для {cars[0].brand} {cars[0].model}\n\n"
                "Введите дату окончания страховки в формате ДД.ММ.ГГГГ (например, 31.12.2026):",
                reply_markup=get_cancel_keyboard()
            )
        else:
            await state.set_state(AddInsurance.waiting_for_car)
            await message.answer(
                "Выберите автомобиль:",
                reply_markup=make_car_keyboard(cars)
            )

@router.callback_query(F.data.startswith("ins_car_"))
async def process_car_choice(callback: types.CallbackQuery, state: FSMContext):
    car_id = int(callback.data.split("_")[-1])
    await state.update_data(car_id=car_id)
    await state.set_state(AddInsurance.waiting_for_end_date)
    with next(get_db()) as db:
        car = db.query(Car).filter(Car.id == car_id).first()
        await callback.message.edit_text(
            f"📄 Добавление страховки для {car.brand} {car.model}\n\n"
            "Введите дату окончания страховки в формате ДД.ММ.ГГГГ (например, 31.12.2026):"
        )
    await callback.answer()

@router.message(AddInsurance.waiting_for_end_date)
async def process_end_date(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_insurance_submenu())
        return
    try:
        end_date = datetime.strptime(message.text.strip(), "%d.%m.%Y")
        if end_date.date() < datetime.now().date():
            await message.answer("❌ Дата окончания не может быть в прошлом. Введите будущую дату:")
            return
        await state.update_data(end_date=end_date)
        await state.set_state(AddInsurance.waiting_for_cost)
        await message.answer(
            "Введите стоимость страховки в рублях:",
            reply_markup=get_cancel_keyboard()
        )
    except ValueError:
        await message.answer("❌ Неверный формат. Введите дату в формате ДД.ММ.ГГГГ (например, 31.12.2026)")

@router.message(AddInsurance.waiting_for_cost)
async def process_cost(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_insurance_submenu())
        return
    try:
        cost = float(message.text.replace(',', '.'))
        await state.update_data(cost=cost)
        await state.set_state(AddInsurance.waiting_for_policy)
        await message.answer(
            "Введите номер полиса (или отправьте '-', чтобы пропустить):",
            reply_markup=get_cancel_keyboard()
        )
    except ValueError:
        await message.answer("❌ Введите число (например, 25000)")

@router.message(AddInsurance.waiting_for_policy)
async def process_policy(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_insurance_submenu())
        return
    policy = message.text if message.text != "-" else None
    await state.update_data(policy=policy)
    await state.set_state(AddInsurance.waiting_for_company)
    await message.answer(
        "Введите название страховой компании (или отправьте '-', чтобы пропустить):",
        reply_markup=get_cancel_keyboard()
    )

@router.message(AddInsurance.waiting_for_company)
async def process_company(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_insurance_submenu())
        return
    company = message.text if message.text != "-" else None
    await state.update_data(company=company)
    await state.set_state(AddInsurance.waiting_for_notes)
    await message.answer(
        "Введите примечания (или отправьте '-', чтобы пропустить):",
        reply_markup=get_cancel_keyboard()
    )

@router.message(AddInsurance.waiting_for_notes)
async def process_notes(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_insurance_submenu())
        return
    notes = message.text if message.text != "-" else None
    await state.update_data(notes=notes)
    await state.set_state(AddInsurance.waiting_for_photo)
    await message.answer(
        "Теперь вы можете прикрепить фото чека или полиса (необязательно).",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="⏭ Пропустить")]],
            resize_keyboard=True
        )
    )

@router.message(AddInsurance.waiting_for_photo, F.photo)
async def process_insurance_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    await save_insurance(message, state)

@router.message(AddInsurance.waiting_for_photo, F.text == "⏭ Пропустить")
async def skip_insurance_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo_id=None)
    await save_insurance(message, state)

async def save_insurance(message: types.Message, state: FSMContext):
    data = await state.get_data()
    car_id = data['car_id']
    end_date = data['end_date']
    cost = data['cost']
    policy = data.get('policy')
    company = data.get('company')
    notes = data.get('notes')
    photo_id = data.get('photo_id')

    with next(get_db()) as db:
        insurance = Insurance(
            car_id=car_id,
            policy_number=policy,
            company=company,
            start_date=datetime.now(),
            end_date=end_date,
            cost=cost,
            notes=notes,
            photo_id=photo_id,
            notified_7d=False,
            notified_3d=False,
            notified_expired=False
        )
        db.add(insurance)
        db.commit()

        car = db.query(Car).filter(Car.id == car_id).first()

    await message.answer(
        f"✅ Страховка добавлена!\n\n"
        f"Автомобиль: {car.brand} {car.model}\n"
        f"Действует до: {end_date.strftime('%d.%m.%Y')}\n"
        f"Стоимость: {cost:.2f} ₽\n"
        f"Номер полиса: {policy or 'не указан'}\n"
        f"Компания: {company or 'не указана'}",
        reply_markup=get_insurance_submenu()
    )
    await state.clear()

@router.message(F.text == "📄 Список страховок")
@router.message(Command("my_insurances"))
async def show_insurances(message: types.Message):
    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь", reply_markup=get_insurance_submenu())
            return
        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("У вас нет автомобилей.", reply_markup=get_insurance_submenu())
            return

        response = "📄 Ваши страховки:\n\n"
        found = False
        for car in cars:
            insurances = db.query(Insurance).filter(Insurance.car_id == car.id).all()
            if insurances:
                found = True
                response += f"🚗 {car.brand} {car.model}:\n"
                for ins in insurances:
                    days_left = (ins.end_date.date() - datetime.now().date()).days
                    if days_left < 0:
                        status = "❗️ Истекла"
                    elif days_left <= 7:
                        status = f"⚠️ Истекает через {days_left} дн."
                    else:
                        status = "✅ Активна"
                    response += (
                        f"  • До {ins.end_date.strftime('%d.%m.%Y')} "
                        f"– {ins.cost:.0f} ₽ {status}\n"
                    )
                response += "\n"
        if not found:
            response = "У вас пока нет добавленных страховок."
        await message.answer(response, reply_markup=get_insurance_submenu())
