import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///carwise.db")
    
    # Администраторы: если переменная ADMIN_IDS задана, используем её, иначе ваш ID по умолчанию
    default_admin_ids = [712843452]  # ваш Telegram ID
    env_admin_ids = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]
    ADMIN_IDS = env_admin_ids if env_admin_ids else default_admin_ids
    
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
