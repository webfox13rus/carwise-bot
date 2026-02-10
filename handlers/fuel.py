from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy.orm import Session
from datetime import datetime

from states.fuel_states import AddFuelStates
from keyboards.main_menu import get_main_menu, get_cancel_keyboard, get_fuel_types_keyboard
from database import get_db, Car, User, Event, FuelPrice
from config import config

router = Router()

@router.message(F.text == "⛽ Добавить заправку")
async def add_fuel_start(message: types.Message, state: FSMContext):
    """Начать добавление заправки"""
    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        
        if not user:
            await message.answer("Сначала добавьте автомобиль!")
            return
        
        cars = db.query(Car).filter(Car.user_id == user.telegram_id, Car.is_active == True).all()
        
        if not cars:
            await message.answer("🚫 У вас нет автомобилей")
            return
        
        if len(cars) == 1:
            # Если один авто, сразу переходим к выбору типа топлива
            await state.update_data(car_id=cars[0].id, car_name=f"{cars[0].brand} {cars[0].model}")
            await state.set_state(AddFuelStates.waiting_for_fuel_type)
            
            await message.answer(
                f"🚗 *{cars[0].brand} {cars[0].model}*\n"
                f"Текущий пробег: *{cars[0].current_mileage:,} км*\n"
                f"Тип топлива: {config.DEFAULT_FUEL_TYPES.get(cars[0].fuel_type, cars[0].fuel_type)}\n\n"
                f"Выберите тип заправляемого топлива:",
                parse_mode="Markdown",
                reply_markup=get_fuel_types_keyboard()
            )
        else:
            # Если несколько авто, создаем список для выбора
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[])
            
            for car in cars:
                keyboard.inline_keyboard.append([
                    types.InlineKeyboardButton(
                        text=f"{car.brand} {car.model} ({car.current_mileage:,} км)",
                        callback_data=f"fuel_car_{car.id}"
                    )
                ])
            
            await state.set_state(AddFuelStates.waiting_for_car_choice)
            await message.answer(
                "Выберите автомобиль для заправки:",
                reply_markup=keyboard
            )

@router.callback_query(F.data.startswith("fuel_car_"))
async def select_car_for_fuel(callback: types.CallbackQuery, state: FSMContext):
    """Выбор авто для заправки"""
    car_id = int(callback.data.split("_")[-1])
    
    with next(get_db()) as db:
        car = db.query(Car).filter(Car.id == car_id).first()
        
        if car:
            await state.update_data(car_id=car_id, car_name=f"{car.brand} {car.model}")
            await state.set_state(AddFuelStates.waiting_for_fuel_type)
            
            await callback.message.edit_text(
                f"🚗 *{car.brand} {car.model}*\n"
                f"Текущий пробег: *{car.current_mileage:,} км*\n"
                f"Тип топлива: {config.DEFAULT_FUEL_TYPES.get(car.fuel_type, car.fuel_type)}\n\n"
                f"Выберите тип заправляемого топлива:",
                parse_mode="Markdown",
                reply_markup=get_fuel_types_keyboard()
            )
    
    await callback.answer()

@router.callback_query(F.data.startswith("fuel_type_"))
async def process_fuel_type_for_refuel(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора типа топлива для заправки"""
    fuel_type = callback.data.split("_")[-1]
    
    await state.update_data(fuel_type=fuel_type)
    await state.set_state(AddFuelStates.waiting_for_amount)
    
    fuel_name = config.DEFAULT_FUEL_TYPES.get(fuel_type, fuel_type)
    
    await callback.message.edit_text(
        f"⛽ *{fuel_name}*\n\n"
        f"Введите *количество литров*:\n"
        f"(Например: 45.5)",
        parse_mode="Markdown"
    )
    
    await callback.message.answer(
        "Или отправьте отмена для отмены:",
        reply_markup=get_cancel_keyboard()
    )
    
    await callback.answer()

@router.message(AddFuelStates.waiting_for_amount)
async def process_fuel_amount(message: types.Message, state: FSMContext):
    """Обработка количества топлива"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Заправка отменена", reply_markup=get_main_menu())
        return
    
    try:
        amount = float(message.text.replace(',', '.'))
        
        if amount <= 0 or amount > 500:
            await message.answer("❌ Пожалуйста, введите корректное количество (0-500 литров)")
            return
        
        await state.update_data(amount=amount)
        await state.set_state(AddFuelStates.waiting_for_cost)
        
        await message.answer(
            f"⛽ *{amount} литров*\n\n"
            f"Введите *сумму* в рублях:\n"
            f"(Например: 2500.50)",
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard()
        )
        
    except ValueError:
        await message.answer("❌ Пожалуйста, введите число (например: 45.5)")

@router.message(AddFuelStates.waiting_for_cost)
async def process_fuel_cost(message: types.Message, state: FSMContext):
    """Обработка стоимости заправки"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Заправка отменена", reply_markup=get_main_menu())
        return
    
    try:
        cost = float(message.text.replace(',', '.'))
        
        if cost <= 0 or cost > 100000:
            await message.answer("❌ Пожалуйста, введите корректную сумму (0-100,000 ₽)")
            return
        
        data = await state.get_data()
        amount = data['amount']
        
        # Рассчитываем цену за литр
        price_per_liter = cost / amount if amount > 0 else 0
        
        await state.update_data(cost=cost, price_per_liter=price_per_liter)
        await state.set_state(AddFuelStates.waiting_for_mileage)
        
        with next(get_db()) as db:
            car = db.query(Car).filter(Car.id == data['car_id']).first()
            
            if car:
                await message.answer(
                    f"🚗 *{car.brand} {car.model}*\n"
                    f"Текущий пробег: *{car.current_mileage:,} км*\n\n"
                    f"Введите *пробег на момент заправки*:\n"
                    f"(Оставьте пустым, чтобы использовать текущий: {car.current_mileage:,} км)",
                    parse_mode="Markdown",
                    reply_markup=types.ReplyKeyboardMarkup(
                        keyboard=[
                            [types.KeyboardButton(text=f"Использовать {car.current_mileage:,} км")],
                            [types.KeyboardButton(text="❌ Отмена")]
                        ],
                        resize_keyboard=True
                    )
                )
        
    except ValueError:
        await message.answer("❌ Пожалуйста, введите число (например: 2500.50)")

@router.message(AddFuelStates.waiting_for_mileage)
async def process_fuel_mileage(message: types.Message, state: FSMContext):
    """Обработка пробега при заправке"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Заправка отменена", reply_markup=get_main_menu())
        return
    
    data = await state.get_data()
    
    with next(get_db()) as db:
        car = db.query(Car).filter(Car.id == data['car_id']).first()
        
        if not car:
            await state.clear()
            await message.answer("❌ Автомобиль не найден", reply_markup=get_main_menu())
            return
        
        # Определяем пробег
        if message.text == f"Использовать {car.current_mileage:,} км":
            mileage = car.current_mileage
        else:
            try:
                mileage = float(message.text.replace(',', '.'))
            except ValueError:
                await message.answer("❌ Пожалуйста, введите число")
                return
        
        await state.update_data(mileage=mileage)
        await state.set_state(AddFuelStates.waiting_for_location)
        
        await message.answer(
            "📍 Введите *название АЗС* или место заправки:\n"
            "(Например: 'Лукойл на Ленина 12' или 'Shell')\n\n"
            "Или отправьте '-' чтобы пропустить:",
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard()
        )

@router.message(AddFuelStates.waiting_for_location)
async def process_fuel_location(message: types.Message, state: FSMContext):
    """Обработка места заправки"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Заправка отменена", reply_markup=get_main_menu())
        return
    
    location = message.text if message.text != "-" else None
    
    await state.update_data(location=location)
    
    # Формируем подтверждение
    data = await state.get_data()
    
    fuel_name = config.DEFAULT_FUEL_TYPES.get(data['fuel_type'], data['fuel_type'])
    price_per_liter = data.get('price_per_liter', 0)
    
    confirmation_text = (
        "⛽ *Проверьте данные заправки:*\n\n"
        f"*Автомобиль:* {data['car_name']}\n"
        f"*Топливо:* {fuel_name}\n"
        f"*Количество:* {data['amount']} литров\n"
        f"*Сумма:* {data['cost']:,.2f} ₽\n"
        f"*Цена за литр:* {price_per_liter:,.2f} ₽\n"
        f"*Пробег:* {data['mileage']:,} км\n"
    )
    
    if data.get('location'):
        confirmation_text += f"*Место:* {data['location']}\n"
    
    confirmation_text += "\nВсё верно?"
    
    await message.answer(
        confirmation_text,
        parse_mode="Markdown",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="✅ Да, добавить")],
                [types.KeyboardButton(text="❌ Нет, исправить")]
            ],
            resize_keyboard=True
        )
    )

@router.message(AddFuelStates.waiting_for_location, F.text.in_(["✅ Да, добавить", "❌ Нет, исправить"]))
async def confirm_fuel_addition(message: types.Message, state: FSMContext):
    """Подтверждение добавления заправки"""
    if message.text == "❌ Нет, исправить":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_main_menu())
        return
    
    data = await state.get_data()
    
    with next(get_db()) as db:
        # Создаем событие заправки
        event = Event(
            car_id=data['car_id'],
            category="fuel",
            type=data['fuel_type'],
            cost=data['cost'],
            amount=data['amount'],
            unit="литры",
            description=f"Заправка {data['amount']}л",
            mileage=data['mileage'],
            location=data.get('location'),
            date=datetime.now()
        )
        
        db.add(event)
        
        # Сохраняем цену на топливо
        fuel_price = FuelPrice(
            user_id=message.from_user.id,
            fuel_type=data['fuel_type'],
            price=data.get('price_per_liter', 0),
            gas_station=data.get('location'),
            date=datetime.now()
        )
        
        db.add(fuel_price)
        db.commit()
        
        # Обновляем средний расход, если есть предыдущая заправка
        car = db.query(Car).filter(Car.id == data['car_id']).first()
        if car:
            # Получаем предыдущую заправку
            prev_fuel = db.query(Event).filter(
                Event.car_id == car.id,
                Event.category == "fuel",
                Event.mileage < data['mileage']
            ).order_by(Event.mileage.desc()).first()
            
            if prev_fuel:
                # Рассчитываем расход
                distance = data['mileage'] - prev_fuel.mileage
                if distance > 0:
                    consumption = (data['amount'] / distance) * 100
                    
                    # Обновляем средний расход (сглаживание)
                    if car.average_fuel_consumption > 0:
                        car.average_fuel_consumption = (car.average_fuel_consumption + consumption) / 2
                    else:
                        car.average_fuel_consumption = consumption
                    
                    db.commit()
        
        await message.answer(
            f"✅ *Заправка добавлена!*\n\n"
            f"*{data['car_name']}*\n"
            f"Топливо: {config.DEFAULT_FUEL_TYPES.get(data['fuel_type'], data['fuel_type'])}\n"
            f"Количество: *{data['amount']} л*\n"
            f"Сумма: *{data['cost']:,.2f} ₽*\n"
            f"Цена за литр: *{data.get('price_per_liter', 0):.2f} ₽*\n"
            f"Пробег: *{data['mileage']:,} км*\n\n"
            f"💡 *Совет:* Теперь вы можете отслеживать расход топлива.",
            parse_mode="Markdown",
            reply_markup=get_main_menu()
        )
    
    await state.clear()