import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    ADMIN_IDS = []
    env_admin_ids = os.getenv("ADMIN_IDS")
    if env_admin_ids:
        ADMIN_IDS = [int(id.strip()) for id in env_admin_ids.split(",") if id.strip()]
    
    FEEDBACK_CHAT_ID = os.getenv("FEEDBACK_CHAT_ID")
    if FEEDBACK_CHAT_ID:
        try:
            FEEDBACK_CHAT_ID = int(FEEDBACK_CHAT_ID)
        except ValueError:
            FEEDBACK_CHAT_ID = None
    
    GIGACHAT_AUTH_KEY = os.getenv("GIGACHAT_AUTH_KEY", "")
    
    PREMIUM_PRICE_MONTH = 50
    PREMIUM_PRICE_YEAR = 500
    
    DEFAULT_FUEL_TYPES = {
        "92": "АИ-92",
        "95": "АИ-95",
        "98": "АИ-98",
        "dt": "ДТ",
        "gas": "Газ",
        "electric": "Электричество"
    }
    
    MAINTENANCE_CATEGORIES = {
        "to": "🔧 ТО",
        "wash": "🧼 Мойка",
        "repair": "🔩 Ремонт",
        "parts": "⚙️ Запчасти",
        "tires": "🛞 Шиномонтаж",
        "fluids": "💧 Жидкости",
        "other": "📦 Другое"
    }

config = Config()
