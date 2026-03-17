import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta

from database import SessionLocal, Car, User, Insurance
from keyboards.main_menu import get_insurance_submenu, get_cancel_keyboard, get_skip_keyboard
from config import config

router = Router()
logger = logging.getLogger(__name__)

class InsuranceStates(StatesGroup):
    waiting_for_car = State()
    waiting_for_policy = State()
    waiting_for_company = State()
    waiting_for_start_date = State()
    waiting_for_end_date = State()
    waiting_for_cost = State()
    waiting_for_notes = State()
    waiting_for_photo = State()
    waiting_for_delete = State()

@router.message(F.text == "📄 Добавить страховку")
async def add_insurance_start(message: types.Message, state: FSMContext):
    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь, отправив /start")
            return
        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("У вас нет автомобилей.", reply_markup=get_insurance_submenu())
            return
        cars_list = [(car.id, f"{car.brand} {car.model}") for car in cars]
        await state.update_data(cars=cars_list)
        await state.set_state(InsuranceStates.waiting_for_car)
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=name, callback_data=f"car_{car_id}")] for car_id, name in cars_list
        ])
        await message.answer("Выберите автомобиль:", reply_markup=keyboard)

@router.callback_query(InsuranceStates.waiting_for_car, F.data.startswith("car_"))
async def car_selected(callback: types.CallbackQuery, state: FSMContext):
    car_id = int(callback.data.split("_")[1])
    await state.update_data(car_id=car_id)
    await state.set_state(InsuranceStates.waiting_for_policy)
    await callback.message.edit_text("Введите номер полиса:")
    await callback.answer()

@router.message(InsuranceStates.waiting_for_policy)
async def policy_entered(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_insurance_submenu())
        return
    await state.update_data(policy=message.text.strip())
    await state.set_state(InsuranceStates.waiting_for_company)
    await message.answer("Введите страховую компанию:", reply_markup=get_cancel_keyboard())

@router.message(InsuranceStates.waiting_for_company)
async def company_entered(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_insurance_submenu())
        return
    await state.update_data(company=message.text.strip())
    await state.set_state(InsuranceStates.waiting_for_start_date)
    await message.answer("Введите дату начала действия полиса в формате ДД.ММ.ГГГГ:", reply_markup=get_cancel_keyboard())

@router.message(InsuranceStates.waiting_for_start_date)
async def start_date_entered(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_insurance_submenu())
        return
    try:
        start_date = datetime.strptime(message.text.strip(), "%d.%m.%Y")
        await state.update_data(start_date=start_date)
        await state.set_state(InsuranceStates.waiting_for_end_date)
        await message.answer("Введите дату окончания действия полиса в формате ДД.ММ.ГГГГ:", reply_markup=get_cancel_keyboard())
    except ValueError:
        await message.answer("❌ Неверный формат. Введите дату в формате ДД.ММ.ГГГГ")

@router.message(InsuranceStates.waiting_for_end_date)
async def end_date_entered(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_insurance_submenu())
        return
    try:
        end_date = datetime.strptime(message.text.strip(), "%d.%m.%Y")
        await state.update_data(end_date=end_date)
        await state.set_state(InsuranceStates.waiting_for_cost)
        await message.answer("Введите стоимость полиса (в рублях):", reply_markup=get_cancel_keyboard())
    except ValueError:
        await message.answer("❌ Неверный формат. Введите дату в формате ДД.ММ.ГГГГ")

@router.message(InsuranceStates.waiting_for_cost)
async def cost_entered(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_insurance_submenu())
        return
    try:
        cost = float(message.text.strip().replace(",", ""))
        if cost <= 0:
            raise ValueError
        await state.update_data(cost=cost)
        await state.set_state(InsuranceStates.waiting_for_notes)
        await message.answer("Введите примечания или нажмите 'Пропустить':", reply_markup=get_skip_keyboard())
    except ValueError:
        await message.answer("❌ Введите корректную стоимость (число больше 0).")

@router.message(InsuranceStates.waiting_for_notes)
async def notes_entered(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_insurance_submenu())
        return
    notes = message.text if message.text != "⏭ Пропустить" else None
    await state.update_data(notes=notes)
    await state.set_state(InsuranceStates.waiting_for_photo)
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Да, добавить фото", callback_data="photo_yes")],
        [types.InlineKeyboardButton(text="❌ Нет, сохранить без фото", callback_data="photo_no")]
    ])
    await message.answer("Хотите прикрепить фото полиса?", reply_markup=keyboard)

@router.callback_query(InsuranceStates.waiting_for_photo, F.data.in_({"photo_yes", "photo_no"}))
async def photo_decision(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "photo_yes":
        await state.set_state(InsuranceStates.waiting_for_photo)
        await callback.message.edit_text("Отправьте фото полиса.")
    else:
        await save_insurance(callback.message, state, photo_id=None)
    await callback.answer()

@router.message(InsuranceStates.waiting_for_photo, F.photo)
async def photo_received(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await save_insurance(message, state, photo_id)

async def save_insurance(message: types.Message, state: FSMContext, photo_id=None):
    data = await state.get_data()
    car_id = data.get("car_id")
    policy = data.get("policy")
    company = data.get("company")
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    cost = data.get("cost")
    notes = data.get("notes")

    with SessionLocal() as db:
        insurance = Insurance(
            car_id=car_id,
            policy_number=policy,
            company=company,
            start_date=start_date,
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
        logger.info(f"Страховка добавлена для авто {car_id}")

    await message.answer(
        f"✅ Страховка добавлена!\n"
        f"Номер: {policy}\n"
        f"Компания: {company}\n"
        f"Действует до: {end_date.strftime('%d.%m.%Y')}\n"
        f"Стоимость: {cost:.2f} руб.",
        reply_markup=get_insurance_submenu()
    )
    await state.clear()

@router.message(F.text == "📄 Список страховок")
async def list_insurances(message: types.Message):
    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь.")
            return
        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("У вас нет автомобилей.", reply_markup=get_insurance_submenu())
            return
        car_ids = [car.id for car in cars]
        insurances = db.query(Insurance).filter(Insurance.car_id.in_(car_ids)).order_by(Insurance.end_date).all()
        if not insurances:
            await message.answer("У вас нет страховок.", reply_markup=get_insurance_submenu())
            return
        text = "📄 *Ваши страховки:*\n\n"
        today = datetime.utcnow().date()
        for ins in insurances:
            car = ins.car
            days_left = (ins.end_date.date() - today).days
            status = "⚠️ Истекла" if days_left < 0 else f"✅ {days_left} дн."
            text += f"🚗 {car.brand} {car.model}\n"
            text += f"  Полис: {ins.policy_number}\n"
            text += f"  Компания: {ins.company}\n"
            text += f"  Действует до: {ins.end_date.strftime('%d.%m.%Y')} ({status})\n"
            text += f"  Стоимость: {ins.cost:.2f} руб.\n\n"
        await message.answer(text, parse_mode="Markdown", reply_markup=get_insurance_submenu())

@router.message(F.text == "📸 Мои чеки страховок")
async def my_insurance_photos(message: types.Message):
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
        insurances = db.query(Insurance).filter(Insurance.car_id.in_(car_ids), Insurance.photo_id != None).order_by(Insurance.end_date.desc()).limit(10).all()
        if not insurances:
            await message.answer("У вас нет сохранённых фото страховок.", reply_markup=get_insurance_submenu())
            return
        for ins in insurances:
            caption = f"Страховка {ins.policy_number} от {ins.company}\nДействует до {ins.end_date.strftime('%d.%m.%Y')}"
            await message.answer_photo(photo=ins.photo_id, caption=caption)
        await message.answer("Это последние 10 фото.", reply_markup=get_insurance_submenu())
