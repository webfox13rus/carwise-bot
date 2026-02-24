import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Настраиваем логгер для конфига (чтобы видеть, что загружается)
logger = logging.getLogger(__name__)

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///carwise.db")
    
    # Администраторы
    default_admin_ids = [712843452]
    env_admin_ids_str = os.getenv("ADMIN_IDS", "")
    env_admin_ids = [int(id.strip()) for id in env_admin_ids_str.split(",") if id.strip()] if env_admin_ids_str else []
    ADMIN_IDS = env_admin_ids if env_admin_ids else default_admin_ids
    
    # ID канала обратной связи
    feedback_chat_id_str = os.getenv("FEEDBACK_CHAT_ID")
    if feedback_chat_id_str:
        try:
            FEEDBACK_CHAT_ID = int(feedback_chat_id_str)
            logger.info(f"FEEDBACK_CHAT_ID loaded from env: {FEEDBACK_CHAT_ID}")
        except ValueError:
            logger.error(f"Invalid FEEDBACK_CHAT_ID value: {feedback_chat_id_str}, using default")
            FEEDBACK_CHAT_ID = -1003809982177
    else:
        FEEDBACK_CHAT_ID = -1003809982177
        logger.info(f"FEEDBACK_CHAT_ID not set, using default: {FEEDBACK_CHAT_ID}")
    
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
