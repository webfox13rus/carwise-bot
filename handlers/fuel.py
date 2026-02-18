import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import func

from database import get_db, Car, FuelEvent, User
from keyboards.main_menu import get_main_menu, get_cancel_keyboard, get_fuel_types_keyboard
from config import config

router = Router()
logger = logging.getLogger(__name__)

class AddFuel(StatesGroup):
    waiting_for_car = State()
    waiting_for_amount = State()
    waiting_for_cost = State()
    waiting_for_mileage = State()
    waiting_for_fuel_type = State()  # новое состояние

# Вспомогательная клавиатура выбора автомобиля
def make_car_keyboard(cars):
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[])
    for car in cars:
        keyboard.inline_keyboard.append([
            types.InlineKeyboardButton(
                text=f"{car.brand} {car.model} - {car.current_mileage:,.0f} км",
                callback_data=f"fuel_car_{car.id}"
            )
        ])
    return keyboard

@router.message(F.text == "⛽ Заправка")
@router.message(Command("fuel"))
async def add_fuel_start(message: types.Message, state: FSMContext):
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
            await state.set_state(AddFuel.waiting_for_amount)
            await message.answer(
                f"⛽ {cars[0].brand} {cars[0].model}\n"
                f"Текущий пробег: {cars[0].current_mileage:,.0f} км\n\n"
                "Введите количество литров (например: 45.5):",
                reply_markup=get_cancel_keyboard()
            )
        else:
            await state.set_state(AddFuel.waiting_for_car)
            await message.answer(
                "Выберите автомобиль:",
                reply_markup=make_car_keyboard(cars)
            )

@router.callback_query(F.data.startswith("fuel_car_"))
async def process_car_choice(callback: types.CallbackQuery, state: FSMContext):
    car_id = int(callback.data.split("_")[-1])
    await state.update_data(car_id=car_id)
    await state.set_state(AddFuel.waiting_for_amount)
    with next(get_db()) as db:
        car = db.query(Car).filter(Car.id == car_id).first()
        await callback.message.edit_text(
            f"⛽ {car.brand} {car.model}\n"
            f"Текущий пробег: {car.current_mileage:,.0f} км\n\n"
            "Введите количество литров (например: 45.5):"
        )
    await callback.answer()

@router.message(AddFuel.waiting_for_amount)
async def process_fuel_amount(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_main_menu())
        return
    try:
        amount = float(message.text.replace(',', '.'))
        await state.update_data(amount=amount)
        await state.set_state(AddFuel.waiting_for_cost)
        await message.answer(
            f"⛽ {amount} литров\n\n"
            "Введите сумму в рублях (например: 2500):",
            reply_markup=get_cancel_keyboard()
        )
    except ValueError:
        await message.answer("❌ Введите число (например: 45.5)")

@router.message(AddFuel.waiting_for_cost)
async def process_fuel_cost(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_main_menu())
        return
    try:
        cost = float(message.text.replace(',', '.'))
        await state.update_data(cost=cost)
        await state.set_state(AddFuel.waiting_for_mileage)
        await message.answer(
            "Введите пробег на момент заправки (в км):",
            reply_markup=get_cancel_keyboard()
        )
    except ValueError:
        await message.answer("❌ Введите число (например: 2500)")

@router.message(AddFuel.waiting_for_mileage)
async def process_fuel_mileage(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_main_menu())
        return
    try:
        mileage = float(message.text.replace(',', '.'))
        await state.update_data(mileage=mileage)
        await state.set_state(AddFuel.waiting_for_fuel_type)
        await message.answer(
            "⛽ Выберите тип топлива:",
            reply_markup=get_fuel_types_keyboard()
        )
    except ValueError:
        await message.answer("❌ Введите число (например: 150000)")

@router.callback_query(AddFuel.waiting_for_fuel_type, F.data.startswith("fuel_type_"))
async def process_fuel_type(callback: types.CallbackQuery, state: FSMContext):
    fuel_type = callback.data.split("_")[-1]
    await state.update_data(fuel_type=fuel_type)
    data = await state.get_data()
    car_id = data['car_id']
    amount = data['amount']
    cost = data['cost']
    mileage = data['mileage']
    price_per_liter = cost / amount

    # Получаем название типа топлива для вывода
    fuel_name = config.DEFAULT_FUEL_TYPES.get(fuel_type, fuel_type)

    with next(get_db()) as db:
        # Создаём событие заправки
        fuel_event = FuelEvent(
            car_id=car_id,
            liters=amount,
            cost=cost,
            mileage=mileage,
            fuel_type=fuel_type
        )
        db.add(fuel_event)
        # Обновляем пробег автомобиля, если новый пробег больше текущего
        car = db.query(Car).filter(Car.id == car_id).first()
        if car and mileage > car.current_mileage:
            car.current_mileage = mileage
        db.commit()

        # Расчёт расхода между последними двумя заправками
        consumption_info = ""
        if car:
            # Находим две последние заправки для этого авто (включая только что добавленную)
            last_two = db.query(FuelEvent).filter(FuelEvent.car_id == car_id).order_by(FuelEvent.date.desc()).limit(2).all()
            if len(last_two) == 2:
                # Сортировка по возрастанию даты: старая первая
                older, newer = sorted(last_two, key=lambda x: x.date)
                if newer.mileage and older.mileage and newer.mileage > older.mileage:
                    distance = newer.mileage - older.mileage
                    if distance > 0:
                        # Сумма литров между ними – это литры старой заправки? Нет, берём литры новой?
                        # Правильнее: расход = (литры новой заправки) * 100 / пройденный путь
                        # Но литры новой заправки были залиты после пробега, поэтому расход считается по последней заправке и пройденному пути с предыдущей.
                        # Обычно формула: (литры / пробег) * 100, где пробег – разница между текущей и предыдущей заправками.
                        consumption = (newer.liters / distance) * 100
                        consumption_info = f"\n\n📊 Расход после предыдущей заправки: {consumption:.2f} л/100км"

        await callback.message.edit_text(
            f"✅ Заправка добавлена!\n\n"
            f"Количество: {amount:.2f} л\n"
            f"Сумма: {cost:.2f} ₽\n"
            f"Цена за литр: {price_per_liter:.2f} ₽\n"
            f"Пробег: {mileage:,.0f} км\n"
            f"Тип топлива: {fuel_name}"
            f"{consumption_info}"
        )
        await callback.message.answer(
            "Главное меню:",
            reply_markup=get_main_menu()
        )
    await state.clear()
    await callback.answer()
