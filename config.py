import os
from dotenv import load_dotenv
from typing import List

load_dotenv()

class Config:
    # Бот
    BOT_TOKEN: str = os.getenv("BOT_TOKEN")
    ADMIN_IDS: List[int] = list(map(int, os.getenv("ADMIN_IDS", "").split(","))) if os.getenv("ADMIN_IDS") else []
    
    # База данных
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///carwise.db")
    
    # Настройки
    DEFAULT_FUEL_TYPES = {
        "AI-92": "⛽ Бензин АИ-92",
        "AI-95": "⛽ Бензин АИ-95",
        "AI-98": "⛽ Бензин АИ-98",
        "ДТ": "⛽ Дизельное топливо",
        "Газ": "⛽ Газ (пропан-бутан)",
        "Электро": "⚡ Электричество"
    }
    
    MAINTENANCE_TYPES = {
        "oil_change": "🛢️ Замена масла",
        "oil_filter": "🔧 Масляный фильтр",
        "air_filter": "💨 Воздушный фильтр",
        "cabin_filter": "🌬️ Салонный фильтр",
        "brakes": "🛑 Тормозные колодки",
        "brake_fluid": "🛑 Тормозная жидкость",
        "coolant": "❄️ Охлаждающая жидкость",
        "spark_plugs": "⚡ Свечи зажигания",
        "timing_belt": "⛓️ Ремень ГРМ",
        "tires": "🚘 Шины",
        "battery": "🔋 Аккумулятор",
        "transmission": "⚙️ Трансмиссия"
    }
    
    EVENT_CATEGORIES = {
        "fuel": "⛽ Заправка",
        "maintenance": "🔧 Обслуживание",
        "repair": "🛠️ Ремонт",
        "washing": "🧼 Мойка",
        "insurance": "📄 Страховка",
        "tax": "💰 Налоги/штрафы",
        "accessories": "🎁 Аксессуары",
        "other": "📝 Прочее"
    }
    
    # Интервалы обслуживания (км)
    MAINTENANCE_INTERVALS = {
        "oil_change": 10000,
        "oil_filter": 10000,
        "air_filter": 30000,
        "cabin_filter": 15000,
        "brakes": 50000,
        "brake_fluid": 60000,
        "coolant": 60000,
        "spark_plugs": 60000,
        "timing_belt": 90000,
        "tires": 50000,
        "battery": 100000,
        "transmission": 60000
    }

config = Config()