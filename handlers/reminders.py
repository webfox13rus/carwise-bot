import logging
from datetime import datetime
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import get_db, Car, User
from keyboards.main_menu import get_main_menu, get_cancel_keyboard
from config import config

router = Router()
logger = logging.getLogger(__name__)

class SetReminder(StatesGroup):
    waiting_for_car = State()
    waiting_for_mileage_interval = State()
    waiting_for_months_interval = State()

def make_car_keyboard(cars):
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[])
    for car in cars:
        keyboard.inline_keyboard.append([
            types.InlineKeyboardButton(
                text=f"{car.brand} {car.model}",
                callback_data=f"remind_car_{car.id}"
            )
        ])
    return keyboard

@router.message(F.text == "⏰ Напоминания ТО")
@router.message(Command("set_to_reminder"))
async def set_reminder_start(message: types.Message, state: FSMContext):
    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала добавьте автомобиль через /add_car")
            return
        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("У вас нет автомобилей.")
            return

        if len(cars) == 1:
            await state.update_data(car_id=cars[0].id)
            await state.set_state(SetReminder.waiting_for_mileage_interval)
            await message.answer(
                f"⏰ Настройка напоминаний для {cars[0].brand} {cars[0].model}\n\n"
                "Введите интервал ТО по пробегу в километрах (например, 10000).\n"
                "Если не хотите получать напоминания по пробегу, отправьте 0:",
                reply_markup=get_cancel_keyboard()
            )
        else:
            await state.set_state(SetReminder.waiting_for_car)
            await message.answer(
                "Выберите автомобиль:",
                reply_markup=make_car_keyboard(cars)
            )

@router.callback_query(F.data.startswith("remind_car_"))
async def process_car_choice(callback: types.CallbackQuery, state: FSMContext):
    car_id = int(callback.data.split("_")[-1])
    await state.update_data(car_id=car_id)
    await state.set_state(SetReminder.waiting_for_mileage_interval)
    with next(get_db()) as db:
        car = db.query(Car).filter(Car.id == car_id).first()
        if car:
            await callback.message.edit_text(
                f"⏰ Настройка напоминаний для {car.brand} {car.model}\n\n"
                "Введите интервал ТО по пробегу в километрах (например, 10000).\n"
                "Если не хотите получать напоминания по пробегу, отправьте 0:"
            )
        else:
            await callback.message.edit_text("❌ Автомобиль не найден.")
            await state.clear()
    await callback.answer()

@router.message(SetReminder.waiting_for_mileage_interval)
async def process_mileage_interval(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Настройка отменена", reply_markup=get_main_menu())
        return
    try:
        mileage_int = float(message.text.replace(',', '.'))
        if mileage_int < 0:
            await message.answer("❌ Интервал не может быть отрицательным. Введите число больше или равное 0:")
            return
        await state.update_data(mileage_int=mileage_int)
        await state.set_state(SetReminder.waiting_for_months_interval)
        await message.answer(
            "Введите интервал ТО по времени в месяцах (например, 12).\n"
            "Если не хотите получать напоминания по времени, отправьте 0:",
            reply_markup=get_cancel_keyboard()
        )
    except ValueError:
        await message.answer("❌ Введите число (например, 10000)")

# ИСПРАВЛЕННАЯ ФУНКЦИЯ: данные сохраняются до закрытия сессии
@router.message(SetReminder.waiting_for_months_interval)
async def process_months_interval(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Настройка отменена", reply_markup=get_main_menu())
        return
    try:
        months_int = int(message.text)
        if months_int < 0:
            await message.answer("❌ Интервал не может быть отрицательным. Введите целое число больше или равное 0:")
            return
        data = await state.get_data()
        car_id = data['car_id']
        mileage_int = data['mileage_int']

        with next(get_db()) as db:
            car = db.query(Car).filter(Car.id == car_id).first()
            if car:
                car.to_mileage_interval = mileage_int if mileage_int > 0 else None
                car.to_months_interval = months_int if months_int > 0 else None
                car.notified_to_mileage = False
                car.notified_to_date = False
                db.commit()
                # Сохраняем данные для ответа до закрытия сессии
                car_brand = car.brand
                car_model = car.model
                mileage_display = f"{mileage_int} км" if mileage_int > 0 else "не установлен"
                months_display = f"{months_int} мес." if months_int > 0 else "не установлен"
            else:
                await message.answer("❌ Автомобиль не найден.")
                await state.clear()
                return

        await message.answer(
            f"✅ Напоминания настроены!\n\n"
            f"Автомобиль: {car_brand} {car_model}\n"
            f"Интервал по пробегу: {mileage_display}\n"
            f"Интервал по времени: {months_display}",
            reply_markup=get_main_menu()
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите целое число (например, 12)")

# Команда для просмотра текущих настроек (тоже проверена на DetachedInstanceError)
@router.message(Command("show_reminders"))
async def show_reminders(message: types.Message):
    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь")
            return
        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("У вас нет автомобилей.")
            return

        lines = ["⏰ Текущие настройки напоминаний:\n"]
        for car in cars:
            mileage_int = car.to_mileage_interval if car.to_mileage_interval else "не установлен"
            months_int = car.to_months_interval if car.to_months_interval else "не установлен"
            last_mileage = car.last_maintenance_mileage if car.last_maintenance_mileage else "нет данных"
            last_date = car.last_maintenance_date.strftime('%d.%m.%Y') if car.last_maintenance_date else "нет данных"
            lines.append(
                f"🚗 {car.brand} {car.model}:\n"
                f"  Последнее ТО: пробег {last_mileage}, дата {last_date}\n"
                f"  Интервал по пробегу: {mileage_int} км\n"
                f"  Интервал по времени: {months_int} мес."
            )
        await message.answer("\n\n".join(lines), reply_markup=get_main_menu())
