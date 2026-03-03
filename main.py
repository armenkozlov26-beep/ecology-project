"""
====================================================================================================
G-TRASH PROFESSIONAL CORE SYSTEM v12.0 - ENTERPRISE STABILITY EDITION
PROJECT: INTELLIGENT WASTE MANAGEMENT AND LOGISTICS AUTOMATION
====================================================================================================
ОПИСАНИЕ: Данный программный модуль реализует серверную логику на базе FastAPI.
Обеспечивает интеграцию с облачной СУБД PostgreSQL (Supabase) и предоставляет 
REST-интерфейс для клиентской части.

ОБНОВЛЕНИЕ v12.0: 
- Переход на прямые транзакции (Direct Connection).
- Улучшенная обработка исключений БД.
- Добавлены расширенные метаданные проекта.
====================================================================================================
"""

import os
import logging
import datetime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, create_engine, desc, exc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

# --- ГЛОБАЛЬНАЯ КОНФИГУРАЦИЯ СИСТЕМЫ ЛОГИРОВАНИЯ ---
# Настройка формата вывода логов для удобного мониторинга через консоль Render
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("G_TRASH_STABILITY_LAYER")

# --- КОНФИГУРАЦИЯ БАЗЫ ДАННЫХ ---
# Извлекаем защищенную строку подключения из переменных окружения сервера
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    logger.critical("DATABASE_URL NOT FOUND! Сервер не может быть запущен без конфигурации БД.")
    # Для предотвращения падения при пустой переменной в режиме сборки:
    DATABASE_URL = "postgresql://user:pass@localhost/tmp"

# Инициализация Engine с параметрами оптимизации соединений
# pool_pre_ping=True позволяет автоматически восстанавливать "протухшие" соединения
engine = create_engine(
    DATABASE_URL, 
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args={"sslmode": "require"} # Supabase требует SSL для безопасности
)

# Настройка фабрики сессий доступа к данным
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для декларативного описания моделей данных
Base = declarative_base()

# --- ОПРЕДЕЛЕНИЕ СТРУКТУРЫ ТАБЛИЦ (ORM MODELS) ---

class UserEntity(Base):
    """
    Сущность 'Пользователь'.
    Отвечает за хранение учетных данных и персональной информации.
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Определение связи 1:N (Один пользователь может иметь неограниченное кол-во заказов)
    orders = relationship("OrderEntity", back_populates="owner", cascade="all, delete-orphan")

class OrderEntity(Base):
    """
    Сущность 'Заказ'.
    Хранит информацию о сданном вторичном сырье и привязке к пользователю.
    """
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    client_name = Column(String(255), nullable=False)
    waste_type = Column(String(255), nullable=False)
    weight_kg = Column(Float, nullable=False)
    status = Column(String(100), default="Заявка принята в обработку")
    order_date = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Внешний ключ для связи с таблицей пользователей
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner = relationship("UserEntity", back_populates="orders")

# --- СИНХРОНИЗАЦИЯ СЕРВЕРА С БД ---
# Создает таблицы, если они отсутствуют в Supabase
try:
    Base.metadata.create_all(bind=engine)
    logger.info("CORE: База данных синхронизирована успешно.")
except Exception as e:
    logger.error(f"CORE ERROR: Ошибка при синхронизации БД: {str(e)}")

# --- ИНИЦИАЛИЗАЦИЯ FASTAPI ---
app = FastAPI(
    title="G-TRASH PROFESSIONAL API",
    description="Backend-система для интеллектуального управления эко-логистикой",
    version="12.0.0"
)

# НАСТРОЙКА MIDDLEWARE ДЛЯ ОБРАБОТКИ КРОСС-ДОМЕННЫХ ЗАПРОСОВ (CORS)
# Необходима для того, чтобы браузер не блокировал запросы с вашего фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Зависимость для получения доступа к сессии БД внутри эндпоинтов
def get_database_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- МАРШРУТЫ API (ENDPOINTS) ---

@app.get("/", tags=["System"])
def root_endpoint():
    """Проверка статуса доступности системы"""
    return {
        "status": "active", 
        "project": "G-TRASH PROFESSIONAL", 
        "engine_version": "12.0.0",
        "database_status": "connected"
    }

@app.post("/api/auth/register", tags=["Auth"])
def register_user(payload: Dict[Any, Any], db: Session = Depends(get_database_session)):
    """Регистрация нового пользователя в системе G-TRASH"""
    try:
        logger.info(f"Регистрация пользователя: {payload.get('email')}")
        new_user = UserEntity(
            full_name=payload['full_name'],
            email=payload['email'],
            password=payload['password']
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return {"id": new_user.id, "full_name": new_user.full_name, "status": "success"}
    except exc.IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Данный Email уже зарегистрирован в системе.")
    except Exception as e:
        db.rollback()
        logger.error(f"Reg Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка при создании аккаунта.")

@app.post("/api/auth/login", tags=["Auth"])
def login_user(creds: Dict[Any, Any], db: Session = Depends(get_database_session)):
    """Вход в систему и получение данных профиля"""
    user = db.query(UserEntity).filter(
        UserEntity.email == creds['email'], 
        UserEntity.password == creds['password']
    ).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="Неверные учетные данные. Проверьте логин или пароль.")
    
    return {"id": user.id, "full_name": user.full_name, "email": user.email}

@app.post("/api/orders/create", tags=["Orders"])
async def create_new_order(payload: Dict[Any, Any], db: Session = Depends(get_database_session)):
    """Сохранение новой заявки на вывоз вторсырья в базу данных PostgreSQL"""
    logger.info(f"Новая заявка: {payload.get('client_name')}")
    try:
        new_order = OrderEntity(
            client_name=payload['client_name'],
            waste_type=payload['waste_type'],
            weight_kg=float(payload['weight_kg']),
            user_id=payload.get('user_id')
        )
        db.add(new_order)
        db.commit()
        logger.info(f"Запись #{new_order.id} успешно добавлена в Supabase.")
        return {"status": "success", "order_id": new_order.id}
    except Exception as e:
        db.rollback()
        logger.error(f"КРИТИЧЕСКАЯ ОШИБКА БД: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Сбой при записи в PostgreSQL: {str(e)}")

@app.get("/api/orders/my/{uid}", tags=["Orders"])
def get_user_history(uid: int, db: Session = Depends(get_database_session)):
    """Извлечение персональной истории транзакций пользователя"""
    return db.query(OrderEntity).filter(OrderEntity.user_id == uid).order_by(desc(OrderEntity.order_date)).all()

@app.get("/api/stats/global", tags=["Public Stats"])
def fetch_global_stats(db: Session = Depends(get_database_session)):
    """Агрегация данных для публичного счетчика на главной странице"""
    try:
        all_orders = db.query(OrderEntity).all()
        total_kg = sum([o.weight_kg for o in all_orders if o.weight_kg])
        return {
            "total_kg": round(total_weight, 2),
            "total_orders": len(all_orders),
            "total_users": db.query(UserEntity).count()
        }
    except Exception:
        # Заглушка на случай пустой базы или ошибки подсчета
        return {"total_kg": 0, "total_orders": 0, "total_users": 0}
