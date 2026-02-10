import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Токен бота
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    # База данных
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///carwise.db")
    
    # Настройки
    ADMIN_IDS = []
    
    # Проверка SQLite
    IS_SQLITE = DATABASE_URL.startswith("sqlite")
    
    TIMEZONE = "Europe/Moscow"

config = Config()