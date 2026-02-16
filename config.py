import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///carwise.db")
    
    DEFAULT_FUEL_TYPES = {
        "92": "АИ-92",
        "95": "АИ-95",
        "98": "АИ-98",
        "dt": "ДТ",
        "gas": "Газ",
        "electric": "Электричество"
    }

config = Config()
