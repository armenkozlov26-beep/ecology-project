"""
================================================================================
G-TRASH PROFESSIONAL ECO-SYSTEM v8.0
BACKEND ARCHITECTURE: FastAPI + SQLAlchemy + PostgreSQL (Supabase)
================================================================================
"""

import os
import time
import logging
import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

# --- ГЛОБАЛЬНАЯ КОНФИГУРАЦИЯ ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("API_LOGGER")

# Берем ссылку из Render Environment
DATABASE_URL = os.getenv("DATABASE_URL")

# Настройка SQLAlchemy
engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- МОДЕЛИ БАЗЫ ДАННЫХ ---

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255))
    email = Column(String(255), unique=True, index=True)
    password = Column(String(255))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    orders = relationship("Order", back_populates="owner")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(String(255))
    waste_type = Column(String(100))
    weight_kg = Column(Float)
    order_date = Column(DateTime, default=datetime.datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner = relationship("User", back_populates="orders")

# Создаем таблицы (в Supabase они появятся автоматически)
Base.metadata.create_all(bind=engine)

# --- ИНИЦИАЛИЗАЦИЯ ПРИЛОЖЕНИЯ ---

app = FastAPI(title="G-TRASH Enterprise API")

# ВАЖНО: Настройка CORS, чтобы фронтенд мог достучаться
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- СХЕМЫ ДАННЫХ (Pydantic) ---

class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class OrderCreate(BaseModel):
    client_name: str
    waste_type: str
    weight_kg: float
    user_id: Optional[int] = None

# --- ЗАВИСИМОСТИ ---

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- ЭНДПОИНТЫ API ---

@app.get("/")
def root():
    return {"status": "G-TRASH v8.0 Online", "db_url_configured": bool(DATABASE_URL)}

@app.post("/auth/register")
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user_in.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Этот Email уже занят")
    
    new_user = User(
        full_name=user_in.full_name,
        email=user_in.email,
        password=user_in.password
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"status": "success", "id": new_user.id}

@app.post("/auth/login")
def login(user_in: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user_in.email, User.password == user_in.password).first()
    if not db_user:
        raise HTTPException(status_code=401, detail="Неверные учетные данные")
    return {"id": db_user.id, "full_name": db_user.full_name, "email": db_user.email}

@app.post("/orders/create")
def create_order(order_in: OrderCreate, db: Session = Depends(get_db)):
    try:
        new_order = Order(
            client_name=order_in.client_name,
            waste_type=order_in.waste_type,
            weight_kg=order_in.weight_kg,
            user_id=order_in.user_id
        )
        db.add(new_order)
        db.commit()
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        logger.error(f"DATABASE ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/orders/my/{user_id}")
def get_my_orders(user_id: int, db: Session = Depends(get_db)):
    return db.query(Order).filter(Order.user_id == user_id).order_by(Order.order_date.desc()).all()

@app.get("/stats/global")
def get_stats(db: Session = Depends(get_db)):
    orders = db.query(Order).all()
    total_kg = sum([o.weight_kg for o in orders if o.weight_kg])
    return {
        "total_kg": round(total_kg, 1),
        "total_orders": len(orders),
        "total_users": db.query(User).count()
    }

