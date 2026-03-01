import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///carwise.db")
    AUTODOC_API_KEY = os.getenv("AUTODOC_API_KEY", "")
  
    # Администраторы (ваш ID 712843452)
    default_admin_ids = [712843452]
    env_admin_ids = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]
    ADMIN_IDS = env_admin_ids if env_admin_ids else default_admin_ids
    
    # ID канала обратной связи (супергруппа)
    FEEDBACK_CHAT_ID = os.getenv("FEEDBACK_CHAT_ID")
    if FEEDBACK_CHAT_ID:
        try:
            FEEDBACK_CHAT_ID = int(FEEDBACK_CHAT_ID)
        except ValueError:
            FEEDBACK_CHAT_ID = None
    
    # GigaChat API (Client Secret / Authorization Key)
    GIGACHAT_AUTH_KEY = os.getenv("GIGACHAT_AUTH_KEY", "")
    
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
