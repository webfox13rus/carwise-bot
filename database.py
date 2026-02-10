import sqlite3
from datetime import datetime
import os

class Database:
    def __init__(self, db_path="carwise.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Пользователи
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Автомобили
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                brand TEXT NOT NULL,
                model TEXT NOT NULL,
                year INTEGER,
                current_mileage REAL DEFAULT 0,
                fuel_type TEXT DEFAULT 'AI-95',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # События
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                car_id INTEGER,
                type TEXT NOT NULL,
                cost REAL NOT NULL,
                description TEXT,
                mileage REAL,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    # Простые методы
    def add_user(self, telegram_id, username, first_name):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (telegram_id, username, first_name)
            VALUES (?, ?, ?)
        ''', (telegram_id, username, first_name))
        conn.commit()
        conn.close()

# Глобальный экземпляр
db = Database()

def init_db():
    """Инициализация БД для импорта из main.py"""
    return db.init_db()