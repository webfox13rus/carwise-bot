import logging
import asyncio
import aiohttp
import ssl
import httpx
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.filters import Command
from sqlalchemy import func
from openai import AsyncOpenAI

from database import get_db, User, Car, FuelEvent, MaintenanceEvent, Insurance, Part
from keyboards.main_menu import get_stats_submenu
from config import config

router = Router()
logger = logging.getLogger(__name__)

GIGACHAT_AUTH_KEY = config.GIGACHAT_AUTH_KEY
GIGACHAT_API_URL = "https://gigachat.devices.sberbank.ru/api/v1"

# Создаём кастомный httpx клиент с отключенной проверкой SSL
# (для работы в РФ, где могут отсутствовать корневые сертификаты)
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

http_client = httpx.AsyncClient(verify=False)  # полностью отключаем проверку SSL

async def get_gigachat_access_token() -> str | None:
    """Получает access token для GigaChat."""
    url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "RqUID": "6f0b1291-c7f3-43c6-bb2e-9f3efb2dc98e",
        "Authorization": f"Basic {GIGACHAT_AUTH_KEY}"
    }
    payload = "scope=GIGACHAT_API_PERS"

    try:
        # Используем aiohttp с отключенным SSL для запроса токена
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, headers=headers, data=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info("GigaChat access token получен успешно")
                    return data.get("access_token")
                else:
                    error_text = await resp.text()
                    logger.error(f"Ошибка получения токена GigaChat: {resp.status} - {error_text}")
                    return None
    except Exception as e:
        logger.error(f"Исключение при получении токена GigaChat: {e}")
        return None

async def get_ai_advice(car_data: dict) -> str:
    if not GIGACHAT_AUTH_KEY:
        return "❌ AI-советы временно недоступны (не настроен ключ GigaChat)."

    access_token = await get_gigachat_access_token()
    if not access_token:
        return "❌ Не удалось авторизоваться в GigaChat. Попробуйте позже."

    # Создаём клиент OpenAI с отключенной проверкой SSL
    openai_client = AsyncOpenAI(
        base_url=GIGACHAT_API_URL,
        api_key=access_token,
        http_client=http_client  # используем наш кастомный клиент
    )

    prompt = (
        "Ты – опытный автомеханик с 20-летним стажем. Проанализируй данные автомобиля и дай подробные, практические рекомендации по его обслуживанию. "
        "Учитывай пробег, возраст, расход топлива, историю ТО, страховки, предстоящие замены деталей. Если какие-то данные отсутствуют – отметь это. "
        "Пиши дружелюбно, профессионально, но понятно для обычного водителя. Не выдумывай несуществующие проблемы, но укажи на возможные риски. "
        "Ответ должен быть полезным и конкретным.\n\n"
        f"Данные автомобиля:\n"
        f"- Марка: {car_data['brand']}\n"
        f"- Модель: {car_data['model']}\n"
        f"- Год выпуска: {car_data['year']}\n"
        f"- Текущий пробег: {car_data['mileage']} км\n"
        f"- Средний расход топлива: {car_data['consumption']} л/100км\n"
        f"- Последнее ТО: пробег {car_data['last_to_mileage']}, дата {car_data['last_to_date']}\n"
        f"- Интервалы ТО: по пробегу {car_data['to_mileage_interval']}, по времени {car_data['to_months_interval']}\n"
        f"- Страховка: действует до {car_data['insurance_date']}, дней осталось {car_data['insurance_days']}\n"
        f"- Детали к замене (ближайшие): {car_data['parts_list']}\n\n"
        "Дай советы по дальнейшей эксплуатации и обслуживанию."
    )

    try:
        response = await openai_client.chat.completions.create(
            model="GigaChat-2-Lite",
            messages=[
                {"role": "system", "content": "Ты – опытный автомеханик, дающий полезные советы."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        advice = response.choices[0].message.content
        return advice.strip() if advice else "❌ Не удалось получить совет от GigaChat."
    except Exception as e:
        logger.error(f"Ошибка при запросе к GigaChat: {e}")
        return "❌ Произошла ошибка при генерации совета. Попробуйте позже."

# Функция premium_stats (без изменений, остаётся как в предыдущем ответе)
# ... (скопируйте её из предыдущего сообщения)
