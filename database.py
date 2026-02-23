from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from datetime import datetime
from config import config

engine = create_engine(config.DATABASE_URL, pool_pre_ping=True)
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
    is_premium = Column(Boolean, default=False)  # флаг подписки (по умолчанию False)
    
    cars = relationship("Car", back_populates="owner", cascade="all, delete-orphan")

class Car(Base):
    __tablename__ = "cars"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    brand = Column(String, nullable=False)
    model = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    name = Column(String, nullable=True)
    current_mileage = Column(Float, default=0)
    fuel_type = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    last_maintenance_mileage = Column(Float, nullable=True)
    last_maintenance_date = Column(DateTime, nullable=True)
    to_mileage_interval = Column(Float, nullable=True)
    to_months_interval = Column(Integer, nullable=True)
    notified_to_mileage = Column(Boolean, default=False)
    notified_to_date = Column(Boolean, default=False)
    
    owner = relationship("User", back_populates="cars")
    fuel_events = relationship("FuelEvent", back_populates="car", cascade="all, delete-orphan")
    maintenance_events = relationship("MaintenanceEvent", back_populates="car", cascade="all, delete-orphan")
    insurances = relationship("Insurance", back_populates="car", cascade="all, delete-orphan")
    parts = relationship("Part", back_populates="car", cascade="all, delete-orphan")

class FuelEvent(Base):
    __tablename__ = "fuel_events"
    
    id = Column(Integer, primary_key=True, index=True)
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False)
    liters = Column(Float, nullable=False)
    cost = Column(Float, nullable=False)
    mileage = Column(Float, nullable=True)
    fuel_type = Column(String, nullable=True)
    date = Column(DateTime, default=datetime.utcnow)
    
    car = relationship("Car", back_populates="fuel_events")

class MaintenanceEvent(Base):
    __tablename__ = "maintenance_events"
    
    id = Column(Integer, primary_key=True, index=True)
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False)
    category = Column(String, nullable=False)
    description = Column(String, nullable=False)
    cost = Column(Float, nullable=False)
    mileage = Column(Float, nullable=True)
    date = Column(DateTime, default=datetime.utcnow)
    
    car = relationship("Car", back_populates="maintenance_events")

class Insurance(Base):
    __tablename__ = "insurances"
    
    id = Column(Integer, primary_key=True, index=True)
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False)
    policy_number = Column(String, nullable=True)
    company = Column(String, nullable=True)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    cost = Column(Float, nullable=False)
    notes = Column(String, nullable=True)
    notified_7d = Column(Boolean, default=False)
    notified_3d = Column(Boolean, default=False)
    notified_expired = Column(Boolean, default=False)
    
    car = relationship("Car", back_populates="insurances")

class Part(Base):
    __tablename__ = "parts"
    
    id = Column(Integer, primary_key=True, index=True)
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False)
    name = Column(String, nullable=False)
    interval_mileage = Column(Float, nullable=True)
    interval_months = Column(Integer, nullable=True)
    last_mileage = Column(Float, nullable=True)
    last_date = Column(DateTime, nullable=True)
    notified = Column(Boolean, default=False)
    
    car = relationship("Car", back_populates="parts")

def init_db():
    Base.metadata.create_all(bind=engine)
