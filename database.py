from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, BigInteger, Numeric, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from config import config

engine = create_engine(config.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_premium = Column(Boolean, default=False)
    premium_until = Column(DateTime, nullable=True)
    
    cars = relationship("Car", back_populates="owner", cascade="all, delete-orphan")

class Car(Base):
    __tablename__ = "cars"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    brand = Column(String, nullable=False)
    model = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    name = Column(String, nullable=True)
    vin = Column(String, nullable=True, index=True)
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
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False, index=True)
    liters = Column(Float, nullable=False)
    cost = Column(Numeric(10, 2), nullable=False)
    mileage = Column(Float, nullable=True)
    fuel_type = Column(String, nullable=True)
    date = Column(DateTime, default=datetime.utcnow, index=True)
    photo_id = Column(String, nullable=True)
    
    car = relationship("Car", back_populates="fuel_events")

    __table_args__ = (Index('ix_fuel_events_car_id_date', 'car_id', 'date'),)

class MaintenanceEvent(Base):
    __tablename__ = "maintenance_events"
    
    id = Column(Integer, primary_key=True, index=True)
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False, index=True)
    category = Column(String, nullable=False)
    description = Column(String, nullable=False)
    cost = Column(Numeric(10, 2), nullable=False)
    mileage = Column(Float, nullable=True)
    date = Column(DateTime, default=datetime.utcnow, index=True)
    photo_id = Column(String, nullable=True)
    
    car = relationship("Car", back_populates="maintenance_events")

    __table_args__ = (Index('ix_maintenance_events_car_id_date', 'car_id', 'date'),)

class Insurance(Base):
    __tablename__ = "insurances"
    
    id = Column(Integer, primary_key=True, index=True)
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False, index=True)
    policy_number = Column(String, nullable=True)
    company = Column(String, nullable=True)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False, index=True)
    cost = Column(Numeric(10, 2), nullable=False)
    notes = Column(String, nullable=True)
    photo_id = Column(String, nullable=True)
    notified_7d = Column(Boolean, default=False)
    notified_3d = Column(Boolean, default=False)
    notified_expired = Column(Boolean, default=False)
    
    car = relationship("Car", back_populates="insurances")

class Part(Base):
    __tablename__ = "parts"
    
    id = Column(Integer, primary_key=True, index=True)
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    interval_mileage = Column(Float, nullable=True, index=True)
    interval_months = Column(Integer, nullable=True)
    last_mileage = Column(Float, nullable=True, index=True)
    last_date = Column(DateTime, nullable=True, index=True)
    notified = Column(Boolean, default=False)
    
    car = relationship("Car", back_populates="parts")

class Admin(Base):
    __tablename__ = "admins"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    added_by = Column(BigInteger, nullable=True)
    added_at = Column(DateTime, default=datetime.utcnow)

class BannedUser(Base):
    __tablename__ = "banned_users"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    reason = Column(String, nullable=True)
    banned_by = Column(BigInteger, nullable=True)
    banned_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)
