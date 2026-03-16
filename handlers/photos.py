import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import SessionLocal, Car, User, FuelEvent, MaintenanceEvent, Insurance
from keyboards.main_menu import get_more_submenu

router = Router()
logger = logging.getLogger(__name__)

class PhotoStates(StatesGroup):
    waiting_for_car_selection = State()
    waiting_for_category_selection = State()

async def start_car_selection(message: types.Message, state: FSMContext, back_menu):
    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь, отправив /start")
            return
        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("У вас нет автомобилей.", reply_markup=back_menu)
            return
        # Сохраняем список авто как кортежи (id, название)
        await state.update_data(cars=[(car.id, f"{car.brand} {car.model}") for car in cars])
        await state.set_state(PhotoStates.waiting_for_car_selection)
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=name, callback_data=f"car_{car_id}")] for car_id, name in cars
        ])
        await message.answer("Выберите автомобиль:", reply_markup=keyboard)
        
@router.message(F.text == "📸 Все чеки")
async def view_all_photos(message: types.Message, state: FSMContext):
    await start_car_selection(message, state, get_more_submenu)

@router.callback_query(PhotoStates.waiting_for_car_selection, F.data.startswith("car_"))
async def car_selected_for_photos(callback: types.CallbackQuery, state: FSMContext):
    car_id = int(callback.data.split("_")[1])
    await state.update_data(selected_car_id=car_id)
    # Предлагаем выбрать категорию
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⛽ Заправки", callback_data="cat_fuel")],
        [types.InlineKeyboardButton(text="🔧 Обслуживание", callback_data="cat_maintenance")],
        [types.InlineKeyboardButton(text="📄 Страховки", callback_data="cat_insurance")],
        [types.InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_cars")]
    ])
    await state.set_state(PhotoStates.waiting_for_category_selection)
    await callback.message.edit_text("Выберите категорию чеков:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(PhotoStates.waiting_for_category_selection, F.data.in_(["cat_fuel", "cat_maintenance", "cat_insurance"]))
async def category_selected_for_photos(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    car_id = data.get("selected_car_id")
    category = callback.data.split("_")[1]  # fuel, maintenance, insurance

    with SessionLocal() as db:
        if category == "fuel":
            events = db.query(FuelEvent).filter(FuelEvent.car_id == car_id, FuelEvent.photo_id != None).order_by(FuelEvent.date.desc()).all()
        elif category == "maintenance":
            events = db.query(MaintenanceEvent).filter(MaintenanceEvent.car_id == car_id, MaintenanceEvent.photo_id != None).order_by(MaintenanceEvent.date.desc()).all()
        elif category == "insurance":
            events = db.query(Insurance).filter(Insurance.car_id == car_id, Insurance.photo_id != None).order_by(Insurance.date.desc()).all()
        else:
            events = []

        if not events:
            await callback.message.edit_text("В этой категории нет чеков.", reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[[types.InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_cars")]]
            ))
            await callback.answer()
            return

        for event in events:
            caption = f"{event.date.strftime('%d.%m.%Y')}\n"
            if category == "fuel":
                caption += f"{event.liters:.2f} л, {event.cost:.2f} руб."
            elif category == "maintenance":
                caption += f"{event.category}: {event.description}\nСтоимость: {event.cost:.2f} руб."
            elif category == "insurance":
                caption += f"Полис {event.policy_number}, {event.company}\nДействует до {event.end_date.strftime('%d.%m.%Y')}"
            await callback.message.answer_photo(photo=event.photo_id, caption=caption)

        # Возврат к выбору категории
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="⛽ Заправки", callback_data="cat_fuel")],
            [types.InlineKeyboardButton(text="🔧 Обслуживание", callback_data="cat_maintenance")],
            [types.InlineKeyboardButton(text="📄 Страховки", callback_data="cat_insurance")],
            [types.InlineKeyboardButton(text="◀️ К списку авто", callback_data="back_to_cars")]
        ])
        await callback.message.answer("Выберите категорию для просмотра других чеков:", reply_markup=keyboard)

    await callback.answer()

@router.callback_query(F.data == "back_to_cars")
async def back_to_cars(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cars = data.get("cars", [])
    if cars:
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=name, callback_data=f"car_{car_id}")] for car_id, name in cars
        ])
        await state.set_state(PhotoStates.waiting_for_car_selection)
        await callback.message.edit_text("Выберите автомобиль:", reply_markup=keyboard)
    else:
        await state.clear()
        await callback.message.edit_text("Просмотр чеков завершён.", reply_markup=get_more_submenu(callback.from_user.id))
    await callback.answer()
