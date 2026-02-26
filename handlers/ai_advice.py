import logging
import asyncio
import aiohttp
import os
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

# Конфигурация для GigaChat
GIGACHAT_AUTH_KEY = config.GIGACHAT_AUTH_KEY
# Важно: URL для API должен быть именно таким, как в документации [citation:2]
GIGACHAT_API_URL = "https://gigachat.devices.sberbank.ru/api/v1"

# Глобальный клиент OpenAI, который мы будем использовать для запросов
openai_client = None

async def get_gigachat_access_token() -> str | None:
    """
    Получает access token для GigaChat по Client Secret.
    Токен действует 30 минут, поэтому мы будем получать его перед каждым запросом,
    если он не был получен ранее или истек. [citation:2]
    """
    url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "RqUID": "6f0b1291-c7f3-43c6-bb2e-9f3efb2dc98e",  # Это статический UUID, можно оставить
        "Authorization": f"Basic {GIGACHAT_AUTH_KEY}"
    }
    payload = "scope=GIGACHAT_API_PERS"  # Указываем скоуп для физических лиц [citation:1]

    try:
        async with aiohttp.ClientSession() as session:
            # ВАЖНО: Для работы из России может потребоваться отключить проверку SSL.
            # В продакшене лучше этого не делать, но для теста можно использовать:
            # connector = aiohttp.TCPConnector(ssl=False)
            # async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, headers=headers, data=payload, ssl=False) as resp:
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
    """
    Отправляет запрос к GigaChat и возвращает совет.
    """
    global openai_client

    if not GIGACHAT_AUTH_KEY:
        return "❌ AI-советы временно недоступны (не настроен ключ GigaChat)."

    # 1. Получаем свежий access token
    access_token = await get_gigachat_access_token()
    if not access_token:
        return "❌ Не удалось авторизоваться в GigaChat. Попробуйте позже."

    # 2. Создаем или обновляем клиент OpenAI с новым токеном
    openai_client = AsyncOpenAI(
        base_url=GIGACHAT_API_URL,
        api_key=access_token,  # В качестве api_key используем полученный токен
        # Для отключения проверки SSL (только для теста) можно добавить:
        # http_client=AsyncOpenAI.http_client(verify=False) 
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
        # 3. Отправляем запрос в GigaChat
        response = await openai_client.chat.completions.create(
            model="GigaChat-2-Lite",  # или GigaChat-2-Pro, GigaChat-2-Max
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

# --- Далее идет функция premium_stats, она остается практически без изменений ---
@router.message(F.text == "Расширенная статистика (Premium)")
async def premium_stats(message: types.Message):
    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь, отправив /start")
            return

        is_admin = message.from_user.id in config.ADMIN_IDS
        if not user.is_premium and not is_admin:
            await message.answer(
                "❌ *Функция доступна только для премиум-пользователей.*\n\n"
                "Чтобы получить доступ к расширенной статистике с AI-советами, приобретите подписку. "
                "Подписка находится в разработке, скоро будет доступна.",
                parse_mode="Markdown",
                reply_markup=get_stats_submenu()
            )
            return

        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("У вас нет автомобилей.", reply_markup=get_stats_submenu())
            return

        wait_msg = await message.answer("⏳ Запрос обрабатывается, это может занять несколько секунд...")

        car = cars[0]

        # Расчёт среднего расхода
        fuel_events = db.query(FuelEvent).filter(FuelEvent.car_id == car.id).order_by(FuelEvent.date.desc()).limit(10).all()
        if len(fuel_events) >= 2:
            total_liters = sum(ev.liters for ev in fuel_events if ev.liters)
            total_distance = 0
            prev = None
            for ev in sorted(fuel_events, key=lambda x: x.date):
                if prev and ev.mileage and prev.mileage and ev.mileage > prev.mileage:
                    total_distance += ev.mileage - prev.mileage
                prev = ev
            if total_distance > 0:
                avg_consumption = (total_liters / total_distance) * 100
            else:
                avg_consumption = 0
        else:
            avg_consumption = 0

        # Страховка
        insurances = db.query(Insurance).filter(Insurance.car_id == car.id).all()
        if insurances:
            nearest = min(insurances, key=lambda x: x.end_date)
            insurance_date = nearest.end_date.strftime('%d.%m.%Y')
            insurance_days = (nearest.end_date.date() - datetime.now().date()).days
        else:
            insurance_date = "не оформлена"
            insurance_days = "—"

        # Детали к замене
        parts = db.query(Part).filter(Part.car_id == car.id).all()
        parts_list = []
        for part in parts:
            if part.interval_mileage and part.last_mileage is not None:
                next_mileage = part.last_mileage + part.interval_mileage
                remaining = next_mileage - car.current_mileage
                if remaining > 0 and remaining < 10000:
                    parts_list.append(f"{part.name} (осталось {remaining:,.0f} км)")
            if part.interval_months and part.last_date is not None:
                next_date = part.last_date + timedelta(days=30 * part.interval_months)
                days_left = (next_date.date() - datetime.now().date()).days
                if days_left > 0 and days_left < 90:
                    parts_list.append(f"{part.name} (осталось {days_left} дн.)")
        parts_str = ", ".join(parts_list) if parts_list else "нет ближайших замен"

        car_data = {
            "brand": car.brand,
            "model": car.model,
            "year": car.year,
            "mileage": f"{car.current_mileage:,.0f}",
            "consumption": f"{avg_consumption:.1f}" if avg_consumption > 0 else "нет данных",
            "last_to_mileage": f"{car.last_maintenance_mileage:,.0f}" if car.last_maintenance_mileage else "нет данных",
            "last_to_date": car.last_maintenance_date.strftime('%d.%m.%Y') if car.last_maintenance_date else "нет данных",
            "to_mileage_interval": f"{car.to_mileage_interval:,.0f}" if car.to_mileage_interval else "не задан",
            "to_months_interval": f"{car.to_months_interval}" if car.to_months_interval else "не задан",
            "insurance_date": insurance_date,
            "insurance_days": str(insurance_days),
            "parts_list": parts_str
        }

        advice = await get_ai_advice(car_data)

        await wait_msg.delete()
        await message.answer(
            f"🤖 *AI-совет для {car.brand} {car.model}:*\n\n{advice}",
            parse_mode="Markdown",
            reply_markup=get_stats_submenu()
        )
