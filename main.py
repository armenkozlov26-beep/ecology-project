"""
====================================================================================================
ПРОГРАММНЫЙ КОМПЛЕКС "G-TRASH PROFESSIONAL" (v11.0)
РАЗРАБОТАНО ДЛЯ ДИПЛОМНОГО ПРОЕКТА: "АВТОМАТИЗАЦИЯ ЭКО-ЛОГИСТИКИ"
====================================================================================================
"""

import os
import logging
import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

# --- ГЛОБАЛЬНАЯ НАСТРОЙКА ЛОГИРОВАНИЯ ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("G-TRASH-SYSTEM")

# --- ПОДКЛЮЧЕНИЕ К ОБЛАЧНОЙ БАЗЕ ДАННЫХ SUPABASE ---
DATABASE_URL = os.getenv("DATABASE_URL")

# Используем pool_pre_ping для предотвращения разрыва соединения с сервером БД
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- ОПРЕДЕЛЕНИЕ МОДЕЛЕЙ ДАННЫХ (ORM) ---

class UserDB(Base):
    """Модель таблицы пользователей системы"""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    orders = relationship("OrderDB", back_populates="owner")

class OrderDB(Base):
    """Модель таблицы заявок на переработку"""
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(String(255), nullable=False)
    waste_type = Column(String(255), nullable=False)
    weight_kg = Column(Float, nullable=False)
    order_date = Column(DateTime, default=datetime.datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner = relationship("UserDB", back_populates="orders")

# Автоматическая синхронизация структуры таблиц
try:
    Base.metadata.create_all(bind=engine)
    logger.info("УСПЕХ: Структура БД синхронизирована.")
except Exception as e:
    logger.error(f"ОШИБКА БД: {str(e)}")

# --- ИНИЦИАЛИЗАЦИЯ FASTAPI ПРИЛОЖЕНИЯ ---
app = FastAPI(title="G-TRASH Enterprise API", version="11.0.0")

# Настройка CORS для работы с любыми фронтенд-доменами
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# --- API ЭНДПОИНТЫ (МАРШРУТЫ) ---

@app.get("/")
def system_info():
    return {"status": "online", "project": "G-TRASH PROFESSIONAL", "db": "CONNECTED"}

@app.post("/api/auth/register")
def register(user_data: dict, db: Session = Depends(get_db)):
    """Регистрация нового эко-активиста"""
    try:
        new_user = UserDB(
            full_name=user_data['full_name'],
            email=user_data['email'],
            password=user_data['password']
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return {"id": new_user.id, "full_name": new_user.full_name}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Ошибка: Email уже занят или данные неверны.")

@app.post("/api/auth/login")
def login(creds: dict, db: Session = Depends(get_db)):
    """Авторизация и вход в личный кабинет"""
    user = db.query(UserDB).filter(UserDB.email == creds['email'], UserDB.password == creds['password']).first()
    if not user:
        raise HTTPException(status_code=401, detail="Неверные учетные данные.")
    return {"id": user.id, "full_name": user.full_name, "email": user.email}

@app.post("/api/orders/create")
def create_order(order_data: dict, db: Session = Depends(get_db)):
    """Создание новой заявки на вывоз сырья"""
    try:
        new_order = OrderDB(
            client_name=order_data['client_name'],
            waste_type=order_data['waste_type'],
            weight_kg=float(order_data['weight_kg']),
            user_id=order_data.get('user_id')
        )
        db.add(new_order)
        db.commit()
        return {"status": "success", "msg": "Запись в Supabase подтверждена"}
    except Exception as e:
        db.rollback()
        logger.error(f"DATABASE ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/orders/my/{uid}")
def get_user_history(uid: int, db: Session = Depends(get_db)):
    """История заказов конкретного пользователя"""
    return db.query(OrderDB).filter(OrderDB.user_id == uid).order_by(OrderDB.order_date.desc()).all()

@app.get("/api/stats/global")
def get_global_stats(db: Session = Depends(get_db)):
    """Глобальная аналитика системы для главной страницы"""
    try:
        all_orders = db.query(OrderDB).all()
        total_kg = sum([o.weight_kg for o in all_orders if o.weight_kg])
        return {
            "total_kg": round(total_kg, 1),
            "total_orders": len(all_orders),
            "total_users": db.query(UserDB).count()
        }
    except Exception as e:
        return {"total_kg": 0, "total_orders": 0, "total_users": 0}
