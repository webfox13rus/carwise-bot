import logging
import asyncio
import aiohttp
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import get_db, User, Car
from config import config
from keyboards.main_menu import get_more_submenu

router = Router()
logger = logging.getLogger(__name__)

class VinSearch(StatesGroup):
    waiting_for_vin = State()
    waiting_for_part_search = State()
    waiting_for_car_selection = State()   # новое состояние для выбора авто

AUTODOC_API_KEY = config.AUTODOC_API_KEY
AUTODOC_BASE_URL = "https://api.autodoc.ru/v1"  # уточнить при получении ключа

HEADERS = {
    "Authorization": f"Bearer {AUTODOC_API_KEY}",
    "Accept": "application/json",
    "User-Agent": "CarWiseBot/1.0"
}

vin_cache = {}
CACHE_TTL = timedelta(hours=24)

async def decode_vin(vin: str) -> dict | None:
    if vin in vin_cache and datetime.now() - vin_cache[vin]["timestamp"] < CACHE_TTL:
        return vin_cache[vin]["data"]
    url = f"{AUTODOC_BASE_URL}/vin/{vin}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    vin_cache[vin] = {"data": data, "timestamp": datetime.now()}
                    return data
                else:
                    logger.error(f"VIN decode error {resp.status}: {await resp.text()}")
                    return None
    except Exception as e:
        logger.error(f"Exception in decode_vin: {e}")
        return None

async def search_parts(vehicle_id: str, query: str = "", page: int = 1) -> list:
    url = f"{AUTODOC_BASE_URL}/parts/search"
    params = {"vehicleId": vehicle_id, "page": page, "pageSize": 20}
    if query:
        params["query"] = query
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS, params=params, timeout=15) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("parts", [])
                else:
                    return []
    except Exception as e:
        logger.error(f"Search parts error: {e}")
        return []

def format_part(part: dict) -> str:
    return (
        f"🔹 *{part.get('name', 'Без названия')}*\n"
        f"Артикул: `{part.get('article', 'N/A')}`\n"
        f"Цена: {part.get('price', '?')} ₽\n"
        f"[Перейти к заказу]({part.get('url', '#')})"
    )

@router.message(F.text == "🔍 Поиск по VIN")
@router.message(Command("vin"))
async def vin_start(message: types.Message, state: FSMContext):
    if not AUTODOC_API_KEY:
        await message.answer("❌ Функция поиска по VIN временно недоступна.")
        return

    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь, отправив /start")
            return
        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        cars_with_vin = [c for c in cars if c.vin]

        if cars_with_vin:
            # Показываем список авто с VIN
            keyboard = InlineKeyboardMarkup(inline_keyboard=[])
            for car in cars_with_vin:
                keyboard.inline_keyboard.append([
                    InlineKeyboardButton(
                        text=f"{car.brand} {car.model} ({car.year})",
                        callback_data=f"vincar_{car.id}"
                    )
                ])
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="✏️ Ввести другой VIN", callback_data="vin_manual")
            ])
            await state.set_state(VinSearch.waiting_for_car_selection)
            await message.answer(
                "🔍 Выберите автомобиль из списка или введите VIN вручную:",
                reply_markup=keyboard
            )
        else:
            # Нет сохранённых VIN, сразу ввод
            await message.answer(
                "🔍 У ваших автомобилей не указан VIN.\n"
                "Введите VIN-номер вручную (17 символов):"
            )
            await state.set_state(VinSearch.waiting_for_vin)

@router.callback_query(F.data.startswith("vincar_"))
async def select_car_with_vin(callback: types.CallbackQuery, state: FSMContext):
    car_id = int(callback.data.split("_")[1])
    with next(get_db()) as db:
        car = db.query(Car).filter(Car.id == car_id).first()
        if car and car.vin:
            # Декодируем VIN
            await callback.message.edit_text("⏳ Декодируем VIN...")
            car_info = await decode_vin(car.vin)
            if not car_info:
                await callback.message.edit_text("❌ Не удалось распознать VIN.")
                await state.clear()
                return
            # Сохраняем vehicle_id и переходим к действиям
            await state.update_data(vehicle_id=car_info["vehicleId"], car_name=f"{car.brand} {car.model}")
            await show_car_menu(callback.message, state, car_info, car.brand, car.model)
        else:
            await callback.message.edit_text("❌ Автомобиль не найден или не указан VIN.")
            await state.clear()
    await callback.answer()

@router.callback_query(F.data == "vin_manual")
async def manual_vin_input(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(VinSearch.waiting_for_vin)
    await callback.message.edit_text(
        "🔍 Введите VIN-номер вручную (17 символов):"
    )
    await callback.answer()

@router.message(VinSearch.waiting_for_vin)
async def process_manual_vin(message: types.Message, state: FSMContext):
    vin = message.text.upper().replace(" ", "")
    if len(vin) != 17:
        await message.answer("❌ VIN должен содержать 17 символов. Попробуйте снова.")
        return
    wait_msg = await message.answer("⏳ Декодируем VIN...")
    car_info = await decode_vin(vin)
    await wait_msg.delete()
    if not car_info:
        await message.answer("❌ Не удалось распознать VIN. Проверьте правильность.")
        return
    await state.update_data(vehicle_id=car_info["vehicleId"], car_name=f"{car_info['brand']} {car_info['model']}")
    await show_car_menu(message, state, car_info, car_info['brand'], car_info['model'])

async def show_car_menu(message: types.Message, state: FSMContext, car_info: dict, brand: str, model: str):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛞 Запчасти для ТО", callback_data="vin_to")],
        [InlineKeyboardButton(text="🔍 Поиск по названию", callback_data="vin_search_parts")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="vin_cancel")]
    ])
    await message.answer(
        f"🚗 *{brand} {model}*\n"
        f"📅 Год: {car_info.get('year', 'неизвестно')}\n"
        f"🔧 Двигатель: {car_info.get('engine', 'неизвестно')}\n\n"
        f"Выберите действие:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("vin_"))
async def vin_actions(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    vehicle_id = data.get("vehicle_id")
    if not vehicle_id:
        await callback.message.edit_text("❌ Данные устарели. Начните заново.")
        await state.clear()
        return

    if callback.data == "vin_cancel":
        await callback.message.edit_text("❌ Поиск отменён.")
        await state.clear()
        return
    elif callback.data == "vin_to":
        parts = await search_parts(vehicle_id, query="то")
        if not parts:
            await callback.message.edit_text("❌ Не удалось найти запчасти для ТО.")
            return
        response = "🛞 *Запчасти для ТО*\n\n"
        for part in parts[:5]:
            response += format_part(part) + "\n\n"
        await callback.message.edit_text(response, parse_mode="Markdown")
    elif callback.data == "vin_search_parts":
        await state.set_state(VinSearch.waiting_for_part_search)
        await callback.message.edit_text(
            "🔍 Введите название запчасти (например: 'масло моторное'):"
        )
    await callback.answer()

@router.message(VinSearch.waiting_for_part_search)
async def process_part_search(message: types.Message, state: FSMContext):
    query = message.text.strip()
    if not query:
        await message.answer("❌ Введите непустой запрос.")
        return
    data = await state.get_data()
    vehicle_id = data.get("vehicle_id")
    if not vehicle_id:
        await message.answer("❌ Ошибка: данные потеряны. Начните заново.")
        await state.clear()
        return
    wait_msg = await message.answer("⏳ Ищем запчасти...")
    parts = await search_parts(vehicle_id, query=query)
    await wait_msg.delete()
    if not parts:
        await message.answer("❌ Ничего не найдено. Попробуйте другой запрос.")
        return
    response = f"🔍 *Результаты поиска: {query}*\n\n"
    for part in parts[:5]:
        response += format_part(part) + "\n\n"
    if len(parts) > 5:
        response += f"\n... и ещё {len(parts)-5} запчастей.\n"
    await message.answer(response, parse_mode="Markdown", disable_web_page_preview=True)
    await state.clear()
