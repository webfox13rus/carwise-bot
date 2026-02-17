from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import func
from datetime import datetime

from states.car_states import AddCarStates, MileageUpdateStates
from keyboards.main_menu import get_main_menu, get_cancel_keyboard, get_fuel_types_keyboard
from database import get_db, Car, User, FuelEvent, MaintenanceEvent
from config import config
from car_data import CAR_BRANDS, get_models_for_brand  # новый импорт

router = Router()

# Вспомогательная функция для создания инлайн-клавиатуры из списка
def make_inline_keyboard(items: list, callback_prefix: str, columns: int = 2) -> types.InlineKeyboardMarkup:
    keyboard = []
    row = []
    for i, item in enumerate(items):
        row.append(types.InlineKeyboardButton(text=item, callback_data=f"{callback_prefix}:{item}"))
        if (i + 1) % columns == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    # Добавляем кнопку "Ввести вручную"
    keyboard.append([types.InlineKeyboardButton(text="✏️ Ввести вручную", callback_data=f"{callback_prefix}:manual")])
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

@router.message(F.text == "🚗 Мои автомобили")
@router.message(Command("my_cars"))
async def show_my_cars(message: types.Message):
    # ... (код без изменений, как в предыдущих версиях) ...
    pass  # здесь должен быть полный код из предыдущих ответов, я его не копирую для краткости, но вы его оставляете как есть

@router.message(F.text == "➕ Добавить авто")
@router.message(Command("add_car"))
async def add_car_start(message: types.Message, state: FSMContext):
    # Показываем список марок
    await state.set_state(AddCarStates.waiting_for_brand)
    keyboard = make_inline_keyboard(CAR_BRANDS, "brand")
    await message.answer(
        "🚗 Выберите марку автомобиля из списка или введите вручную:",
        reply_markup=keyboard
    )

# Обработка выбора марки через callback
@router.callback_query(F.data.startswith("brand:"))
async def process_brand_callback(callback: types.CallbackQuery, state: FSMContext):
    brand = callback.data.split(":", 1)[1]
    if brand == "manual":
        # Переходим в режим ручного ввода
        await state.set_state(AddCarStates.waiting_for_brand_manual)
        await callback.message.edit_text("Введите марку автомобиля вручную:")
        await callback.answer()
        return

    await state.update_data(brand=brand)
    # Проверяем, есть ли модели для этой марки
    models = get_models_for_brand(brand)
    if models:
        # Показываем список моделей
        keyboard = make_inline_keyboard(models, f"model:{brand}")
        await callback.message.edit_text(
            f"Выбрана марка: {brand}\nТеперь выберите модель или введите вручную:",
            reply_markup=keyboard
        )
        await state.set_state(AddCarStates.waiting_for_model)
    else:
        # Если моделей нет, сразу переходим к вводу модели вручную
        await state.set_state(AddCarStates.waiting_for_model_manual)
        await callback.message.edit_text(
            f"Выбрана марка: {brand}\nВведите модель автомобиля вручную:"
        )
    await callback.answer()

# Ручной ввод марки (если нажали "Ввести вручную")
@router.message(AddCarStates.waiting_for_brand_manual)
async def process_brand_manual(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_main_menu())
        return
    brand = message.text.strip()
    await state.update_data(brand=brand)
    await state.set_state(AddCarStates.waiting_for_model_manual)
    await message.answer(
        f"Марка: {brand}\nВведите модель автомобиля:",
        reply_markup=get_cancel_keyboard()
    )

# Обработка выбора модели через callback
@router.callback_query(F.data.startswith("model:"))
async def process_model_callback(callback: types.CallbackQuery, state: FSMContext):
    # В callback_data хранится model:brand:model_name или model:brand:manual
    parts = callback.data.split(":", 2)
    brand = parts[1]
    model = parts[2] if len(parts) > 2 else None

    if model == "manual":
        # Ручной ввод модели
        await state.set_state(AddCarStates.waiting_for_model_manual)
        await callback.message.edit_text(f"Марка: {brand}\nВведите модель автомобиля вручную:")
        await callback.answer()
        return

    await state.update_data(brand=brand, model=model)
    await state.set_state(AddCarStates.waiting_for_year)
    await callback.message.edit_text(
        f"Марка: {brand}\nМодель: {model}\n\nТеперь введите год выпуска (например, 2015):"
    )
    await callback.answer()

# Ручной ввод модели (если нажали "Ввести вручную" или моделей нет)
@router.message(AddCarStates.waiting_for_model_manual)
async def process_model_manual(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=get_main_menu())
        return
    model = message.text.strip()
    data = await state.get_data()
    brand = data.get('brand', '')
    await state.update_data(model=model)
    await state.set_state(AddCarStates.waiting_for_year)
    await message.answer(
        f"Марка: {brand}\nМодель: {model}\n\nВведите год выпуска (например, 2015):",
        reply_markup=get_cancel_keyboard()
    )

# Остальные этапы (год, имя, пробег, тип топлива) остаются без изменений
# Они уже есть в вашем текущем cars.py, просто продолжаем с waiting_for_year

# Далее идут функции process_year, process_name, process_mileage, process_fuel_type, confirm_car_addition, update_mileage...
# Их код остаётся точно таким же, как в предыдущих версиях. Не забудьте их скопировать из старого файла.
