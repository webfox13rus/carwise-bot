import logging
from datetime import datetime
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import func

from database import get_db, Car, User, Insurance
from keyboards.main_menu import get_main_menu, get_cancel_keyboard
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

# Вспомогательная клавиатура выбора автомобиля
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

# Главное меню страховок (подменю)
@router.message(F.text == "📄 Страховка")
@router.message(Command("insurance"))
async def insurance_menu(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="➕ Добавить страховку")],
            [types.KeyboardButton(text="📄 Мои страховки")],
            [types.KeyboardButton(text="◀️ Назад в меню")]
        ],
        resize_keyboard=True
    )
    await message.answer("Управление страховками:", reply_markup=keyboard)

# Возврат в главное меню
@router.message(F.text == "◀️ Назад в меню")
async def back_to_main(message: types.Message):
    await message.answer("Главное меню:", reply_markup=get_main_menu())

# Начало добавления страховки
@router.message(F.text == "➕ Добавить страховку")
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

# Обработка выбора автомобиля через callback
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

# Ввод даты окончания
@router.message(AddInsurance.waiting_for_end_date)
async def process_end_date(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_main_menu())
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

# Ввод стоимости
@router.message(AddInsurance.waiting_for_cost)
async def process_cost(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_main_menu())
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

# Ввод номера полиса
@router.message(AddInsurance.waiting_for_policy)
async def process_policy(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_main_menu())
        return
    policy = message.text if message.text != "-" else None
    await state.update_data(policy=policy)
    await state.set_state(AddInsurance.waiting_for_company)
    await message.answer(
        "Введите название страховой компании (или отправьте '-', чтобы пропустить):",
        reply_markup=get_cancel_keyboard()
    )

# Ввод компании
@router.message(AddInsurance.waiting_for_company)
async def process_company(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_main_menu())
        return
    company = message.text if message.text != "-" else None
    await state.update_data(company=company)
    await state.set_state(AddInsurance.waiting_for_notes)
    await message.answer(
        "Введите примечания (или отправьте '-', чтобы пропустить):",
        reply_markup=get_cancel_keyboard()
    )

# Ввод примечаний и сохранение
@router.message(AddInsurance.waiting_for_notes)
async def process_notes(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_main_menu())
        return
    notes = message.text if message.text != "-" else None
    data = await state.get_data()

    with next(get_db()) as db:
        insurance = Insurance(
            car_id=data['car_id'],
            policy_number=data.get('policy'),
            company=data.get('company'),
            start_date=datetime.now(),  # можно позже добавить поле start_date
            end_date=data['end_date'],
            cost=data['cost'],
            notes=notes,
            notified_7d=False,
            notified_3d=False,
            notified_expired=False
        )
        db.add(insurance)
        db.commit()

        car = db.query(Car).filter(Car.id == data['car_id']).first()

        await message.answer(
            f"✅ Страховка добавлена!\n\n"
            f"Автомобиль: {car.brand} {car.model}\n"
            f"Действует до: {data['end_date'].strftime('%d.%m.%Y')}\n"
            f"Стоимость: {data['cost']:.2f} ₽\n"
            f"Номер полиса: {data.get('policy', 'не указан')}\n"
            f"Компания: {data.get('company', 'не указана')}",
            reply_markup=get_main_menu()  # возвращаем главное меню
        )
    await state.clear()

# Просмотр списка страховок
@router.message(F.text == "📄 Мои страховки")
@router.message(Command("my_insurances"))
async def show_insurances(message: types.Message):
    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь", reply_markup=get_main_menu())
            return
        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("У вас нет автомобилей.", reply_markup=get_main_menu())
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

        await message.answer(response, reply_markup=get_main_menu())  # после списка возвращаем главное меню
