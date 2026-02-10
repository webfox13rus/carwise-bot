from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import pytz

from config import config

# Создаем базовый класс
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    language = Column(String(10), default='ru')
    created_at = Column(DateTime, default=lambda: datetime.now(pytz.timezone('Europe/Moscow')))
    is_active = Column(Boolean, default=True)
    
    # Связи
    cars = relationship("Car", back_populates="user", cascade="all, delete-orphan")

class Car(Base):
    __tablename__ = 'cars'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.telegram_id'))
    name = Column(String(100))  # Пользовательское имя авто
    brand = Column(String(100))
    model = Column(String(100))
    year = Column(Integer)
    vin = Column(String(50))
    license_plate = Column(String(20))
    current_mileage = Column(Float, default=0)
    average_fuel_consumption = Column(Float, default=0)
    fuel_type = Column(String(20), default='AI-95')
    created_at = Column(DateTime, default=lambda: datetime.now(pytz.timezone('Europe/Moscow')))
    is_active = Column(Boolean, default=True)
    
    # Связи
    user = relationship("User", back_populates="cars")
    events = relationship("Event", back_populates="car", cascade="all, delete-orphan")
    maintenance = relationship("MaintenanceRecord", back_populates="car", cascade="all, delete-orphan")

class Event(Base):
    __tablename__ = 'events'
    
    id = Column(Integer, primary_key=True)
    car_id = Column(Integer, ForeignKey('cars.id'))
    category = Column(String(50))
    type = Column(String(100))  # Конкретный тип (заправка, замена масла и т.д.)
    cost = Column(Float)
    amount = Column(Float)  # Количество литров, часов работы и т.д.
    unit = Column(String(20))  # литры, штуки, часы
    description = Column(Text)
    mileage = Column(Float)
    location = Column(String(200))
    receipt_photo = Column(String(500))  # Ссылка на фото чека
    date = Column(DateTime, default=lambda: datetime.now(pytz.timezone('Europe/Moscow')))
    created_at = Column(DateTime, default=lambda: datetime.now(pytz.timezone('Europe/Moscow')))
    
    # Связи
    car = relationship("Car", back_populates="events")

class MaintenanceRecord(Base):
    __tablename__ = 'maintenance_records'
    
    id = Column(Integer, primary_key=True)
    car_id = Column(Integer, ForeignKey('cars.id'))
    maintenance_type = Column(String(50))
    description = Column(Text)
    cost = Column(Float)
    mileage = Column(Float)
    date = Column(DateTime, default=lambda: datetime.now(pytz.timezone('Europe/Moscow')))
    next_due_mileage = Column(Float)
    next_due_date = Column(DateTime)
    is_completed = Column(Boolean, default=True)
    
    # Связи
    car = relationship("Car", back_populates="maintenance")

class FuelPrice(Base):
    __tablename__ = 'fuel_prices'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.telegram_id'))
    fuel_type = Column(String(20))
    price = Column(Float)
    gas_station = Column(String(100))
    date = Column(DateTime, default=lambda: datetime.now(pytz.timezone('Europe/Moscow')))

class Reminder(Base):
    __tablename__ = 'reminders'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.telegram_id'))
    car_id = Column(Integer, ForeignKey('cars.id'))
    reminder_type = Column(String(50))
    message = Column(Text)
    due_date = Column(DateTime)
    due_mileage = Column(Float)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(pytz.timezone('Europe/Moscow')))

# Создаем движок и таблицы
engine = create_engine(config.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def init_db():
    """Инициализация базы данных"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Получение сессии БД"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()