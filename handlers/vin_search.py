import aiohttp
import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

router = Router()
logger = logging.getLogger(__name__)

class VinSearch(StatesGroup):
    waiting_for_vin = State()
    waiting_for_part_selection = State()

# Конфигурация API (нужно будет добавить в config.py)
AUTODOC_API_KEY = config.AUTODOC_API_KEY
AUTODOC_BASE_URL = "https://api.autodoc.ru/v1"  # пример, нужен реальный URL

async def decode_vin(vin: str) -> dict:
    """Отправляет VIN к API Autodoc и получает информацию об авто"""
    headers = {"Authorization": f"Bearer {AUTODOC_API_KEY}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{AUTODOC_BASE_URL}/vin/{vin}",
            headers=headers
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                logger.error(f"VIN decode error: {await resp.text()}")
                return None

async def search_parts(vehicle_id: str, part_name: str = None) -> list:
    """Ищет запчасти по ID автомобиля"""
    params = {"vehicle_id": vehicle_id}
    if part_name:
        params["query"] = part_name
        
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{AUTODOC_BASE_URL}/parts/search",
            params=params,
            headers={"Authorization": f"Bearer {AUTODOC_API_KEY}"}
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("parts", [])
            return []

@router.message(Command("vin"))
async def vin_start(message: types.Message, state: FSMContext):
    await message.answer(
        "🔍 Введите 17-значный VIN-номер автомобиля:"
    )
    await state.set_state(VinSearch.waiting_for_vin)

@router.message(VinSearch.waiting_for_vin)
async def process_vin(message: types.Message, state: FSMContext):
    vin = message.text.upper().replace(" ", "")
    if len(vin) != 17:
        await message.answer("❌ VIN должен содержать ровно 17 символов")
        return
    
    # Отправляем сообщение о загрузке
    wait_msg = await message.answer("⏳ Декодируем VIN...")
    
    # Получаем данные
    car_info = await decode_vin(vin)
    if not car_info:
        await wait_msg.delete()
        await message.answer("❌ Не удалось распознать VIN. Проверьте правильность ввода.")
        return
    
    # Сохраняем ID авто в состояние
    await state.update_data(
        vehicle_id=car_info["vehicle_id"],
        car_name=f"{car_info['brand']} {car_info['model']} {car_info['year']}"
    )
    
    await wait_msg.delete()
    
    # Показываем информацию и предлагаем выбрать действие
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🛞 Запчасти для ТО", callback_data="parts_to")],
        [types.InlineKeyboardButton(text="🔍 Поиск по названию", callback_data="parts_search")],
        [types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])
    
    await message.answer(
        f"🚗 *{car_info['brand']} {car_info['model']}*\n"
        f"📅 Год: {car_info['year']}\n"
        f"🔧 Двигатель: {car_info.get('engine', 'неизвестно')}\n\n"
        f"Выберите действие:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "parts_to")
async def show_to_parts(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    vehicle_id = data.get("vehicle_id")
    
    if not vehicle_id:
        await callback.message.edit_text("❌ Ошибка: данные автомобиля потеряны. Начните заново.")
        await state.clear()
        return
    
    # Ищем запчасти для ТО (масло, фильтры, свечи)
    parts = await search_parts(vehicle_id, "то")  # или специальный эндпоинт
    
    if not parts:
        await callback.message.edit_text("❌ Не удалось найти запчасти для ТО.")
        return
    
    # Формируем ответ
    response = f"🛞 *Запчасти для ТО*\n\n"
    for part in parts[:10]:  # показываем первые 10
        response += f"• {part['name']}\n  Артикул: `{part['article']}`\n  Цена: {part['price']} ₽\n\n"
    
    await callback.message.edit_text(response, parse_mode="Markdown")
    await callback.answer()

# Добавляем кнопку в подменю "Ещё"
# (нужно обновить keyboards/main_menu.py)
