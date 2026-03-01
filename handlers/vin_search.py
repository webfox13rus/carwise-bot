import logging
import asyncio
import aiohttp
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import get_db, User
from config import config
from keyboards.main_menu import get_more_submenu

router = Router()
logger = logging.getLogger(__name__)

# Кэш для результатов VIN-декодирования (чтобы не долбить API одинаковыми запросами)
vin_cache = {}
CACHE_TTL = timedelta(hours=24)

class VinSearch(StatesGroup):
    waiting_for_vin = State()
    waiting_for_part_search = State()

# ---------- Конфигурация Autodoc API ----------
AUTODOC_API_KEY = config.AUTODOC_API_KEY
AUTODOC_BASE_URL = "https://api.autodoc.ru/v1"  # замените на реальный URL

HEADERS = {
    "Authorization": f"Bearer {AUTODOC_API_KEY}",
    "Accept": "application/json",
    "User-Agent": "CarWiseBot/1.0 (Telegram bot)"
}

# ---------- Вспомогательные функции ----------
async def decode_vin(vin: str) -> dict | None:
    """Запрос к API для расшифровки VIN"""
    if vin in vin_cache:
        cached = vin_cache[vin]
        if datetime.now() - cached["timestamp"] < CACHE_TTL:
            logger.info(f"VIN {vin} взят из кэша")
            return cached["data"]

    url = f"{AUTODOC_BASE_URL}/vin/{vin}"
    for attempt in range(3):  # 3 попытки при ошибках
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=HEADERS, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        vin_cache[vin] = {
                            "data": data,
                            "timestamp": datetime.now()
                        }
                        return data
                    elif resp.status == 404:
                        return None
                    elif resp.status in (429, 500):
                        logger.warning(f"Ошибка {resp.status}, попытка {attempt+1}/3")
                        await asyncio.sleep(2 ** attempt)  # экспоненциальная задержка
                        continue
                    else:
                        logger.error(f"VIN decode error: {resp.status} - {await resp.text()}")
                        return None
        except asyncio.TimeoutError:
            logger.warning(f"Таймаут, попытка {attempt+1}/3")
            await asyncio.sleep(2 ** attempt)
        except Exception as e:
            logger.error(f"Исключение при декодировании VIN: {e}")
            return None
    return None

async def search_parts(vehicle_id: str, query: str = "", page: int = 1) -> list:
    """
    Поиск запчастей по ID автомобиля.
    Параметры: vehicle_id, query (необязательно), page (для пагинации).
    """
    url = f"{AUTODOC_BASE_URL}/parts/search"
    params = {
        "vehicleId": vehicle_id,
        "page": page,
        "pageSize": 20  # безопасный размер страницы
    }
    if query:
        params["query"] = query

    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=HEADERS, params=params, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("parts", [])
                    elif resp.status == 429:
                        logger.warning("Rate limit, ждём...")
                        await asyncio.sleep(5)
                        continue
                    elif resp.status == 500:
                        logger.warning(f"Ошибка сервера 500, попытка {attempt+1}/3")
                        await asyncio.sleep(2 ** attempt)
                        continue
                    else:
                        logger.error(f"Search parts error: {resp.status}")
                        return []
        except Exception as e:
            logger.error(f"Exception in search_parts: {e}")
            return []
    return []

def format_part(part: dict) -> str:
    """Форматирует одну запчасть для вывода"""
    return (
        f"🔹 *{part.get('name', 'Без названия')}*\n"
        f"Артикул: `{part.get('article', 'N/A')}`\n"
        f"Цена: {part.get('price', '?')} ₽\n"
        f"[Перейти к заказу]({part.get('url', '#')})"
    )

# ---------- Обработчики ----------
@router.message(F.text == "🔍 Поиск по VIN")
@router.message(Command("vin"))
async def vin_start(message: types.Message, state: FSMContext):
    if not AUTODOC_API_KEY:
        await message.answer(
            "❌ Функция поиска по VIN временно недоступна.\n"
            "Ведутся технические работы."
        )
        return
    await message.answer(
        "🔍 Введите 17-значный VIN-номер автомобиля (латиница, цифры):"
    )
    await state.set_state(VinSearch.waiting_for_vin)

@router.message(VinSearch.waiting_for_vin)
async def process_vin(message: types.Message, state: FSMContext):
    vin = message.text.upper().replace(" ", "")
    if len(vin) != 17:
        await message.answer("❌ VIN должен содержать ровно 17 символов. Попробуйте снова.")
        return

    wait_msg = await message.answer("⏳ Декодируем VIN...")

    car_info = await decode_vin(vin)
    if not car_info:
        await wait_msg.delete()
        await message.answer(
            "❌ Не удалось распознать VIN.\n"
            "Проверьте правильность ввода или попробуйте позже."
        )
        return

    # Сохраняем данные в состояние
    await state.update_data(
        vehicle_id=car_info["vehicleId"],  # предположим, что API возвращает vehicleId
        car_name=f"{car_info['brand']} {car_info['model']} {car_info['year']}"
    )

    await wait_msg.delete()

    # Клавиатура выбора действия
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛞 Запчасти для ТО", callback_data="vin_to")],
        [InlineKeyboardButton(text="🔍 Поиск по названию", callback_data="vin_search_parts")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="vin_cancel")]
    ])

    await message.answer(
        f"🚗 *{car_info['brand']} {car_info['model']}*\n"
        f"📅 Год: {car_info['year']}\n"
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
        await callback.message.edit_text("❌ Данные автомобиля устарели. Начните заново.")
        await state.clear()
        return

    if callback.data == "vin_cancel":
        await callback.message.edit_text("❌ Поиск отменён.")
        await state.clear()
        return

    elif callback.data == "vin_to":
        # Запчасти для ТО (масло, фильтры)
        parts = await search_parts(vehicle_id, query="то")
        if not parts:
            await callback.message.edit_text("❌ Не удалось найти запчасти для ТО.")
            return

        response = "🛞 *Запчасти для ТО*\n\n"
        for part in parts[:5]:  # первые 5
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
        await message.answer("❌ Ошибка: данные автомобиля потеряны. Начните заново.")
        await state.clear()
        return

    wait_msg = await message.answer("⏳ Ищем запчасти...")

    parts = await search_parts(vehicle_id, query=query)
    if not parts:
        await wait_msg.delete()
        await message.answer("❌ Ничего не найдено. Попробуйте другой запрос.")
        return

    response = f"🔍 *Результаты поиска: {query}*\n\n"
    for part in parts[:5]:  # первые 5
        response += format_part(part) + "\n\n"

    if len(parts) > 5:
        response += f"\n... и ещё {len(parts)-5} запчастей.\n"

    await wait_msg.delete()
    await message.answer(response, parse_mode="Markdown", disable_web_page_preview=True)
    await state.clear()
