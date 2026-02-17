from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import get_db, Car, MaintenanceEvent, User
from keyboards.main_menu import get_main_menu, get_cancel_keyboard

router = Router()

class AddMaintenance(StatesGroup):
    waiting_for_car = State()
    waiting_for_description = State()
    waiting_for_cost = State()
    waiting_for_mileage = State()

@router.message(F.text == "🔧 Обслуживание")
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
            await state.set_state(AddMaintenance.waiting_for_description)
            await message.answer(
                f"🔧 {cars[0].brand} {cars[0].model}\n"
                f"Текущий пробег: {cars[0].current_mileage:,.0f} км\n\n"
                "Введите, что сделали (например: замена масла):",
                reply_markup=get_cancel_keyboard()
            )
        else:
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[])
            for car in cars:
                keyboard.inline_keyboard.append([
                    types.InlineKeyboardButton(
                        text=f"{car.brand} {car.model} - {car.current_mileage:,.0f} км",
                        callback_data=f"maint_car_{car.id}"
                    )
                ])
            await state.set_state(AddMaintenance.waiting_for_car)
            await message.answer("Выберите автомобиль:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("maint_car_"))
async def process_car_choice(callback: types.CallbackQuery, state: FSMContext):
    car_id = int(callback.data.split("_")[-1])
    await state.update_data(car_id=car_id)
    await state.set_state(AddMaintenance.waiting_for_description)
    with next(get_db()) as db:
        car = db.query(Car).filter(Car.id == car_id).first()
        await callback.message.edit_text(
            f"🔧 {car.brand} {car.model}\n"
            f"Текущий пробег: {car.current_mileage:,.0f} км\n\n"
            "Введите, что сделали (например: замена масла):"
        )
    await callback.answer()

@router.message(AddMaintenance.waiting_for_description)
async def process_description(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_main_menu())
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
        await message.answer("❌ Добавление отменено", reply_markup=get_main_menu())
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
        await message.answer("❌ Введите число (например: 2500)")

@router.message(AddMaintenance.waiting_for_mileage)
async def process_mileage(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_main_menu())
        return
    try:
        mileage = float(message.text.replace(',', '.'))
        data = await state.get_data()
        car_id = data['car_id']
        description = data['description']
        cost = data['cost']

        with next(get_db()) as db:
            maint_event = MaintenanceEvent(
                car_id=car_id,
                description=description,
                cost=cost,
                mileage=mileage
            )
            db.add(maint_event)
            car = db.query(Car).filter(Car.id == car_id).first()
            if car and mileage > car.current_mileage:
                car.current_mileage = mileage
            db.commit()

        await message.answer(
            f"✅ Обслуживание добавлено!\n\n"
            f"{description}\n"
            f"Стоимость: {cost:.2f} ₽\n"
            f"Пробег: {mileage:,.0f} км",
            reply_markup=get_main_menu()
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите число (например: 150000)")
