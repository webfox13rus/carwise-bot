from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from datetime import datetime
from config import config

engine = create_engine(config.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    cars = relationship("Car", back_populates="owner", cascade="all, delete-orphan")

class Car(Base):
    __tablename__ = "cars"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.telegram_id"), nullable=False)
    brand = Column(String, nullable=False)
    model = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    name = Column(String, nullable=True)
    current_mileage = Column(Float, default=0)
    fuel_type = Column(String, nullable=False)  # код типа топлива (92, 95, dt, и т.д.)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    owner = relationship("User", back_populates="cars")
    fuel_events = relationship("FuelEvent", back_populates="car", cascade="all, delete-orphan")
    maintenance_events = relationship("MaintenanceEvent", back_populates="car", cascade="all, delete-orphan")

class FuelEvent(Base):
    __tablename__ = "fuel_events"
    
    id = Column(Integer, primary_key=True, index=True)
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False)
    liters = Column(Float, nullable=False)
    cost = Column(Float, nullable=False)
    mileage = Column(Float, nullable=True)  # пробег на момент заправки
    date = Column(DateTime, default=datetime.utcnow)
    
    car = relationship("Car", back_populates="fuel_events")

class MaintenanceEvent(Base):
    __tablename__ = "maintenance_events"
    
    id = Column(Integer, primary_key=True, index=True)
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False)
    description = Column(String, nullable=False)
    cost = Column(Float, nullable=False)
    mileage = Column(Float, nullable=True)  # пробег на момент ТО
    date = Column(DateTime, default=datetime.utcnow)
    
    car = relationship("Car", back_populates="maintenance_events")

# Создание таблиц (вызывать один раз при старте)
def init_db():
    Base.metadata.create_all(bind=engine)
