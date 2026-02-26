import logging
import asyncio
import aiohttp
from google import genai
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.filters import Command
from sqlalchemy import func

from database import get_db, User, Car, FuelEvent, MaintenanceEvent, Insurance, Part
from keyboards.main_menu import get_stats_submenu
from config import config

router = Router()
logger = logging.getLogger(__name__)

# Инициализация клиента Gemini
if config.GEMINI_API_KEY:
    client = genai.Client(api_key=config.GEMINI_API_KEY)
else:
    client = None
    logger.warning("GEMINI_API_KEY не задан! AI-советы работать не будут.")

MODEL_NAME = "gemini-1.5-flash"

async def get_ai_advice(car_data: dict) -> str:
    """Синхронный вызов Gemini в отдельном потоке с обработкой ошибок aiohttp."""
    if not client:
        return "❌ AI-советы временно недоступны (не настроен API)."

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

    def sync_call():
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )
            return response.text
        except Exception as e:
            logger.error(f"Ошибка внутри sync_call: {e}")
            raise

    try:
        response_text = await asyncio.to_thread(sync_call)
        return response_text.strip()
    except AttributeError as e:
        if "ClientConnectorDNSError" in str(e):
            logger.error("Обнаружена ошибка ClientConnectorDNSError. Возможно, проблема с сетью или версией aiohttp.")
            return "❌ Ошибка сети при обращении к AI-сервису. Попробуйте позже."
        else:
            logger.error(f"Gemini API error: {e}")
            return "❌ Произошла ошибка при генерации совета."
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return "❌ Произошла ошибка при генерации совета. Попробуйте позже."

# Остальная часть файла без изменений (функция premium_stats)...
