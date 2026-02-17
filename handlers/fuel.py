from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import get_db, Car, FuelEvent, User
from keyboards.main_menu import get_main_menu, get_cancel_keyboard

router = Router()

class AddFuel(StatesGroup):
    waiting_for_car = State()
    waiting_for_amount = State()
    waiting_for_cost = State()
    waiting_for_mileage = State()

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
            # Создаём инлайн-клавиатуру для выбора авто
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[])
            for car in cars:
                keyboard.inline_keyboard.append([
                    types.InlineKeyboardButton(
                        text=f"{car.brand} {car.model} - {car.current_mileage:,.0f} км",
                        callback_data=f"fuel_car_{car.id}"
                    )
                ])
            await state.set_state(AddFuel.waiting_for_car)
            await message.answer("Выберите автомобиль:", reply_markup=keyboard)

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
        data = await state.get_data()
        car_id = data['car_id']
        amount = data['amount']
        cost = data['cost']
        price_per_liter = cost / amount

        with next(get_db()) as db:
            # Создаём событие заправки
            fuel_event = FuelEvent(
                car_id=car_id,
                liters=amount,
                cost=cost,
                mileage=mileage
            )
            db.add(fuel_event)
            # Обновляем пробег автомобиля, если новый пробег больше текущего
            car = db.query(Car).filter(Car.id == car_id).first()
            if car and mileage > car.current_mileage:
                car.current_mileage = mileage
            db.commit()

        await message.answer(
            f"✅ Заправка добавлена!\n\n"
            f"Количество: {amount:.2f} л\n"
            f"Сумма: {cost:.2f} ₽\n"
            f"Цена за литр: {price_per_liter:.2f} ₽\n"
            f"Пробег: {mileage:,.0f} км",
            reply_markup=get_main_menu()
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите число (например: 150000)")
