import logging
from datetime import datetime
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import get_db, Car, User, FuelEvent, MaintenanceEvent, Insurance
from keyboards.main_menu import (
    get_main_menu, get_fuel_submenu, get_maintenance_submenu,
    get_insurance_submenu, get_more_submenu, get_cancel_keyboard
)
from config import config

router = Router()
logger = logging.getLogger(__name__)

class ViewPhoto(StatesGroup):
    waiting_for_car = State()
    waiting_for_event = State()

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

def make_events_keyboard(events, action_prefix):
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[])
    for ev in events:
        if action_prefix.startswith('fuel'):
            text = f"{ev.date.strftime('%d.%m.%Y')} – {ev.liters} л, {ev.cost} ₽"
        elif action_prefix.startswith('maint'):
            cat = config.MAINTENANCE_CATEGORIES.get(ev.category, ev.category)
            text = f"{ev.date.strftime('%d.%m.%Y')} – {cat}: {ev.description[:20]}..."
        elif action_prefix.startswith('ins'):
            text = f"{ev.end_date.strftime('%d.%m.%Y')} – {ev.cost} ₽"
        else:
            if hasattr(ev, 'liters'):
                text = f"⛽ {ev.date.strftime('%d.%m.%Y')} – {ev.liters} л, {ev.cost} ₽"
            elif hasattr(ev, 'category'):
                cat = config.MAINTENANCE_CATEGORIES.get(ev.category, ev.category)
                text = f"🔧 {ev.date.strftime('%d.%m.%Y')} – {cat}: {ev.description[:20]}..."
            else:
                text = f"📄 {ev.end_date.strftime('%d.%m.%Y')} – {ev.cost} ₽"
        keyboard.inline_keyboard.append([
            types.InlineKeyboardButton(
                text=text,
                callback_data=f"{action_prefix}_ev_{ev.id}"
            )
        ])
    return keyboard

@router.message(F.text == "📸 Мои чеки заправок")
async def view_fuel_photos(message: types.Message, state: FSMContext):
    await state.update_data(event_type='fuel', category='fuel')
    await start_car_selection(message, state, get_fuel_submenu)

@router.message(F.text == "📸 Мои чеки обслуживания")
async def view_maint_photos(message: types.Message, state: FSMContext):
    await state.update_data(event_type='maint', category='maintenance')
    await start_car_selection(message, state, get_maintenance_submenu)

@router.message(F.text == "📸 Мои чеки страховок")
async def view_ins_photos(message: types.Message, state: FSMContext):
    await state.update_data(event_type='ins', category='insurance')
    await start_car_selection(message, state, get_insurance_submenu)

@router.message(F.text == "📸 Все чеки")
async def view_all_photos(message: types.Message, state: FSMContext):
    await state.update_data(event_type='all', category='all')
    await start_car_selection(message, state, get_more_submenu)

async def start_car_selection(message: types.Message, state: FSMContext, submenu_func):
    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь, отправив /start")
            await state.clear()
            return
        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("У вас нет автомобилей.")
            await state.clear()
            return

        if len(cars) == 1:
            await state.update_data(car_id=cars[0].id)
            await show_events(message, state, cars[0].id, submenu_func)
        else:
            await state.set_state(ViewPhoto.waiting_for_car)
            await message.answer(
                "Выберите автомобиль:",
                reply_markup=make_car_keyboard(cars, "view")
            )

@router.callback_query(F.data.startswith("view_car_"))
async def car_callback(callback: types.CallbackQuery, state: FSMContext):
    car_id = int(callback.data.split("_")[-1])
    await state.update_data(car_id=car_id)
    data = await state.get_data()
    event_type = data.get('event_type')
    if event_type == 'fuel':
        submenu_func = get_fuel_submenu
    elif event_type == 'maint':
        submenu_func = get_maintenance_submenu
    elif event_type == 'ins':
        submenu_func = get_insurance_submenu
    else:
        submenu_func = get_more_submenu
    await show_events(callback.message, state, car_id, submenu_func)
    await callback.answer()

async def show_events(message: types.Message, state: FSMContext, car_id: int, submenu_func):
    data = await state.get_data()
    event_type = data.get('event_type')

    with next(get_db()) as db:
        if event_type == 'fuel':
            events = db.query(FuelEvent).filter(FuelEvent.car_id == car_id).order_by(FuelEvent.date.desc()).limit(10).all()
            prefix = "fuel"
        elif event_type == 'maint':
            events = db.query(MaintenanceEvent).filter(MaintenanceEvent.car_id == car_id).order_by(MaintenanceEvent.date.desc()).limit(10).all()
            prefix = "maint"
        elif event_type == 'ins':
            events = db.query(Insurance).filter(Insurance.car_id == car_id).order_by(Insurance.end_date.desc()).limit(10).all()
            prefix = "ins"
        else:
            fuel_events = db.query(FuelEvent).filter(FuelEvent.car_id == car_id).all()
            maint_events = db.query(MaintenanceEvent).filter(MaintenanceEvent.car_id == car_id).all()
            ins_events = db.query(Insurance).filter(Insurance.car_id == car_id).all()
            all_events = []
            for ev in fuel_events:
                ev._type = 'fuel'
                ev._sort_date = ev.date
                all_events.append(ev)
            for ev in maint_events:
                ev._type = 'maint'
                ev._sort_date = ev.date
                all_events.append(ev)
            for ev in ins_events:
                ev._type = 'ins'
                ev._sort_date = ev.end_date
                all_events.append(ev)
            all_events.sort(key=lambda x: x._sort_date, reverse=True)
            events = all_events[:10]
            prefix = "all"

        if not events:
            await message.answer("Нет записей с фото для этого автомобиля.", reply_markup=submenu_func())
            await state.clear()
            return

        await state.set_state(ViewPhoto.waiting_for_event)
        await message.answer(
            "Выберите запись:",
            reply_markup=make_events_keyboard(events, prefix)
        )

@router.callback_query(ViewPhoto.waiting_for_event, F.data.startswith(("fuel_ev_", "maint_ev_", "ins_ev_", "all_ev_")))
async def event_callback(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    prefix = parts[0]
    event_id = int(parts[-1])

    with next(get_db()) as db:
        if prefix in ('fuel', 'all'):
            event = db.query(FuelEvent).filter(FuelEvent.id == event_id).first()
            if not event and prefix == 'all':
                event = db.query(MaintenanceEvent).filter(MaintenanceEvent.id == event_id).first()
            if not event and prefix == 'all':
                event = db.query(Insurance).filter(Insurance.id == event_id).first()
        elif prefix == 'maint':
            event = db.query(MaintenanceEvent).filter(MaintenanceEvent.id == event_id).first()
        elif prefix == 'ins':
            event = db.query(Insurance).filter(Insurance.id == event_id).first()
        else:
            event = None

        if not event:
            await callback.message.edit_text("❌ Запись не найдена.")
            await state.clear()
            await callback.answer()
            return

        if event.photo_id:
            caption = f"📸 Чек"
            if hasattr(event, 'date') and event.date:
                caption += f" от {event.date.strftime('%d.%m.%Y')}"
            elif hasattr(event, 'end_date') and event.end_date:
                caption += f" (окончание {event.end_date.strftime('%d.%m.%Y')})"
            await callback.message.answer_photo(
                photo=event.photo_id,
                caption=caption
            )
        else:
            await callback.message.answer("❌ К этой записи не прикреплено фото.")

    # Определяем, в какое подменю вернуться
    data = await state.get_data()
    event_type = data.get('event_type')
    if event_type == 'fuel':
        submenu_func = get_fuel_submenu
    elif event_type == 'maint':
        submenu_func = get_maintenance_submenu
    elif event_type == 'ins':
        submenu_func = get_insurance_submenu
    else:
        submenu_func = get_more_submenu

    await callback.message.answer("Выберите действие:", reply_markup=submenu_func())
    await state.clear()
    await callback.answer()
