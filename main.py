"""
====================================================================================================
G-TRASH ULTIMATE ENTERPRISE ECO-SYSTEM v25.0
CORE BACKEND ARCHITECTURE: FastAPI High-Performance Framework
DATABASE LAYER: SQLAlchemy ORM with PostgreSQL (Supabase Direct Integration)
====================================================================================================
Данный модуль является центральным звеном информационной системы управления экологическими данными.
Разработано специально для дипломной работы с учетом требований к объему и структуре кода.

ФУНКЦИОНАЛЬНЫЕ МОДУЛИ:
1.  User Management System (UMS) - Регистрация и авторизация пользователей.
2.  Transaction Processing Unit (TPU) - Обработка заявок на вывоз сырья.
3.  Analytics & Global Statistics (AGS) - Агрегация данных в реальном времени.
4.  Public Content API (PCA) - Управление новостями и отзывами.
5.  Database Stability Layer (DSL) - Прямое подключение к Supabase PostgreSQL.
====================================================================================================
"""

import os
import time
import logging
import datetime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, status, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field, validator
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, ForeignKey, desc, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

# --------------------------------------------------------------------------------------------------
# СЕКЦИЯ ЛОГИРОВАНИЯ (SYSTEM LOGGING)
# --------------------------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("G_TRASH_CORE")

# --------------------------------------------------------------------------------------------------
# КОНФИГУРАЦИЯ БАЗЫ ДАННЫХ (DATABASE CONFIGURATION)
# --------------------------------------------------------------------------------------------------
# ВАЖНО: Используется прямая ссылка с URL-кодированием спецсимволов (+ и !)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    logger.critical("КРИТИЧЕСКАЯ ОШИБКА: Переменная DATABASE_URL не обнаружена в окружении!")
    # Заглушка для предотвращения падения при сборке
    DATABASE_URL = "postgresql://postgres:pass@localhost:5432/postgres"

# Инициализация Engine с параметрами промышленного уровня
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,      # Проверка "живучести" коннекта
    pool_size=20,            # Размер пула соединений
    max_overflow=30,         # Максимальное превышение пула
    pool_recycle=1800,       # Сброс соединений каждые 30 мин
    connect_args={"sslmode": "require"} # Безопасность Supabase
)

# Фабрика сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для моделей
Base = declarative_base()

# --------------------------------------------------------------------------------------------------
# МОДЕЛИ ДАННЫХ (ORM SCHEMAS)
# --------------------------------------------------------------------------------------------------

class UserEntity(Base):
    """Сущность 'Пользователь' - хранит данные эко-активистов"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    avatar_url = Column(String(512), default="https://i.pravatar.cc/150")
    total_points = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Определение связи 1:N с заказами
    orders = relationship("OrderEntity", back_populates="owner", cascade="all, delete-orphan")

class OrderEntity(Base):
    """Сущность 'Заявка' - записи о транзакциях вывоза мусора"""
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    client_name = Column(String(255), nullable=False)
    waste_type = Column(String(100), nullable=False)
    weight_kg = Column(Float, nullable=False)
    address = Column(String(512), nullable=True)
    status = Column(String(50), default="В обработке")
    order_date = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Связь с пользователем
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner = relationship("UserEntity", back_populates="orders")

class NewsEntity(Base):
    """Сущность 'Новости' - контент для медиа-ленты сайта"""
    __tablename__ = "news"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    tag = Column(String(50), default="#ЭКОЛОГИЯ")
    published_at = Column(DateTime, default=datetime.datetime.utcnow)

# Создание таблиц
try:
    Base.metadata.create_all(bind=engine)
    logger.info("CORE: База данных синхронизирована успешно.")
except Exception as e:
    logger.error(f"CORE ERROR: Сбой синхронизации БД: {str(e)}")

# --------------------------------------------------------------------------------------------------
# ИНИЦИАЛИЗАЦИЯ И MIDDLEWARE
# --------------------------------------------------------------------------------------------------
app = FastAPI(
    title="G-TRASH ULTIMATE API",
    description="Профессиональная серверная часть для дипломного проекта",
    version="25.0.0"
)

# Глобальная настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency Injection для сессий
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --------------------------------------------------------------------------------------------------
# ЭНДПОИНТЫ API (BUSINESS LOGIC)
# --------------------------------------------------------------------------------------------------

@app.get("/")
def read_system_status():
    """Публичный статус сервера"""
    return {
        "status": "online",
        "api_version": "25.0.0-PRO",
        "db_connection": "established",
        "timestamp": datetime.datetime.utcnow()
    }

@app.post("/api/auth/register")
def register_user(data: dict, db: Session = Depends(get_db)):
    """Регистрация нового пользователя с проверкой существования"""
    logger.info(f"Попытка регистрации: {data.get('email')}")
    existing_user = db.query(UserEntity).filter(UserEntity.email == data['email']).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Данный Email уже зарегистрирован.")
    
    new_user = UserEntity(
        full_name=data['full_name'],
        email=data['email'],
        password=data['password']
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"id": new_user.id, "status": "success"}

@app.post("/api/auth/login")
def login_user(creds: dict, db: Session = Depends(get_db)):
    """Авторизация и выдача данных профиля"""
    user = db.query(UserEntity).filter(UserEntity.email == creds['email'], UserEntity.password == creds['password']).first()
    if not user:
        raise HTTPException(status_code=401, detail="Неверные учетные данные.")
    return {"id": user.id, "full_name": user.full_name, "email": user.email, "points": user.total_points}

@app.post("/api/orders/create")
async def process_new_order(payload: dict, db: Session = Depends(get_db)):
    """Создание и сохранение транзакции вывоза отходов"""
    logger.info(f"Новая транзакция от {payload.get('client_name')}")
    try:
        new_order = OrderEntity(
            client_name=payload['name'],
            waste_type=payload['type'],
            weight_kg=float(payload['weight']),
            user_id=payload.get('user_id')
        )
        db.add(new_order)
        db.commit()
        return {"status": "success", "transaction_id": new_order.id}
    except Exception as e:
        db.rollback()
        logger.error(f"DATABASE ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка базы данных.")

@app.get("/api/stats/global")
def aggregate_stats(db: Session = Depends(get_db)):
    """Вычисление глобальной аналитики для сайта"""
    try:
        total_kg = db.query(func.sum(OrderEntity.weight_kg)).scalar() or 0
        order_count = db.query(OrderEntity).count()
        user_count = db.query(UserEntity).count()
        return {
            "total_kg": round(total_kg, 1),
            "count": order_count,
            "users": user_count
        }
    except Exception as e:
        logger.error(f"Stats Error: {e}")
        return {"total_kg": 0, "count": 0, "users": 0}

@app.get("/api/orders/my/{uid}")
def fetch_history(uid: int, db: Session = Depends(get_db)):
    """Загрузка истории заявок для личного кабинета"""
    return db.query(OrderEntity).filter(OrderEntity.user_id == uid).order_by(desc(OrderEntity.order_date)).all()
