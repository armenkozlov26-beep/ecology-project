"""
====================================================================================================
G-TRASH GLOBAL ENTERPRISE SOLUTIONS (v70.0)
MODULE: INTEGRATED ECO-RESOURCE CORE
DEVELOPED FOR: DIPLOMA OF INFORMATION SYSTEMS AND TECHNOLOGIES
====================================================================================================
ОПИСАНИЕ:
Данный программный продукт реализует высокопроизводительное ядро системы управления 
ресурсами. Архитектура построена на принципах микросервисного взаимодействия с 
использованием асинхронных вызовов FastAPI и реляционного слоя SQLAlchemy.

ИНТЕГРАЦИЯ С БД:
- Облачный кластер PostgreSQL (Supabase Direct Node)
- Порт подключения: 5432
- Режим безопасности: SSL (require)
- Пул соединений: SQLAlchemy QueuePool

БИЗНЕС-ЛОГИКА:
- UMS (User Management System): Обработка профилей эко-героев.
- RES (Resource Exchange System): Валидация и фиксация транзакций вторичного сырья.
- AGS (Advanced Global Statistics): Вычисление макро-экологических метрик.
- LRS (Loyalty Reward System): Начисление баллов (коэффициент x12).
====================================================================================================
"""

import os
import logging
import datetime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text, desc, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

# --------------------------------------------------------------------------------------------------
# СИСТЕМА МОНИТОРИНГА И ЛОГИРОВАНИЯ (LOGGING SYSTEM)
# --------------------------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | [%(levelname)s] | %(name)s : %(message)s"
)
logger = logging.getLogger("G_TRASH_TITANIUM_CORE")

# --------------------------------------------------------------------------------------------------
# ИНИЦИАЛИЗАЦИЯ ПОДКЛЮЧЕНИЯ К СУБД (DATABASE LAYER)
# --------------------------------------------------------------------------------------------------
# Ссылка с URL-кодированием пароля (+ -> %2B, ! -> %21)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    logger.critical("FATAL: DATABASE_URL не найден в переменных окружения Render!")
    # Заглушка для локальной разработки
    DATABASE_URL = "postgresql://postgres:pass@localhost:5432/postgres"

# Настройка движка промышленного уровня
try:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,      # Авто-восстановление коннекта
        pool_size=30,            # Вместимость пула
        max_overflow=60,         # Пиковая нагрузка
        connect_args={"sslmode": "require"}
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
    logger.info("DATABASE: PostgreSQL Engine успешно инициализирован.")
except Exception as e:
    logger.error(f"DATABASE ERROR: Ошибка инициализации: {e}")

# --------------------------------------------------------------------------------------------------
# ОПРЕДЕЛЕНИЕ ОБЪЕКТНО-РЕЛЯЦИОННЫХ МОДЕЛЕЙ (ORM)
# --------------------------------------------------------------------------------------------------

class UserProfile(Base):
    """Сущность зарегистрированного эко-активиста системы"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    
    # Экологические метрики
    points = Column(Integer, default=0)
    level = Column(String(50), default="Eco Beginner")
    total_impact_kg = Column(Float, default=0.0)
    
    registered_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Связи 1:N
    orders = relationship("OrderTransaction", back_populates="initiator", cascade="all, delete-orphan")

class OrderTransaction(Base):
    """Сущность транзакции по сдаче вторичного сырья"""
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    client_name = Column(String(255), nullable=False)
    waste_type = Column(String(100), nullable=False)
    weight_kg = Column(Float, nullable=False)
    
    # Метаданные транзакции
    status = Column(String(50), default="VERIFIED")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Внешний ключ связи
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    initiator = relationship("UserProfile", back_populates="orders")

# Автоматическая синхронизация схемы с Supabase
try:
    Base.metadata.create_all(bind=engine)
    logger.info("DATABASE: Таблицы синхронизированы.")
except Exception as e:
    logger.error(f"SCHEMA ERROR: {e}")

# --------------------------------------------------------------------------------------------------
# ИНИЦИАЛИЗАЦИЯ ИНТЕРФЕЙСА FASTAPI
# --------------------------------------------------------------------------------------------------
app = FastAPI(
    title="G-TRASH PROFESSIONAL CORE",
    description="High-End API для систем управления отходами",
    version="70.0.0"
)

# Настройка CORS (Cross-Origin Resource Sharing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Зависимость получения сессии
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --------------------------------------------------------------------------------------------------
# ПУБЛИЧНЫЕ МАРШРУТЫ (API ENDPOINTS)
# --------------------------------------------------------------------------------------------------

@app.get("/")
def system_check():
    """Проверка доступности серверного узла"""
    return {
        "engine": "G-TRASH-V70-TITANIUM",
        "status": "online",
        "db_status": "connected_to_cloud" if DATABASE_URL else "config_error",
        "timestamp": datetime.datetime.utcnow()
    }

@app.get("/api/v1/stats/global")
def fetch_global_stats(db: Session = Depends(get_db)):
    """Агрегация глобальных макро-данных всей экосистемы"""
    try:
        total_mass = db.query(func.sum(OrderTransaction.weight_kg)).scalar() or 0
        total_orders = db.query(OrderTransaction).count()
        total_activists = db.query(UserProfile).count()
        
        return {
            "total_kg": round(total_mass, 1),
            "orders_count": total_orders,
            "eco_heroes": total_activists,
            "trees_saved": int(total_mass * 0.017),
            "co2_offset_tons": round(total_mass * 2.5 / 1000, 2)
        }
    except Exception as e:
        logger.error(f"Stats failure: {e}")
        return {"total_kg": 0, "orders_count": 0, "eco_heroes": 0}

@app.post("/api/v1/auth/register")
def register_user(data: dict, db: Session = Depends(get_db)):
    """Регистрация нового идентификатора в системе"""
    check = db.query(UserProfile).filter(UserProfile.email == data['email']).first()
    if check:
        raise HTTPException(status_code=400, detail="Этот Email уже зарегистрирован.")
    
    try:
        new_hero = UserProfile(
            full_name=data['full_name'],
            email=data['email'],
            password=data['password']
        )
        db.add(new_hero); db.commit(); db.refresh(new_hero)
        return {"status": "success", "user_id": new_hero.id}
    except Exception as e:
        db.rollback(); raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/auth/login")
def login_user(data: dict, db: Session = Depends(get_db)):
    """Авторизация и получение операционных данных профиля"""
    hero = db.query(UserProfile).filter(
        UserProfile.email == data['email'], 
        UserProfile.password == data['password']
    ).first()
    if not hero:
        raise HTTPException(status_code=401, detail="Ошибка аутентификации.")
    
    return {
        "id": hero.id,
        "full_name": hero.full_name,
        "email": hero.email,
        "points": hero.points,
        "rank": hero.level
    }

@app.post("/api/v1/orders/create")
async def process_transaction(payload: dict, db: Session = Depends(get_db)):
    """Запись новой заявки в PostgreSQL и расчет бонусов"""
    logger.info(f"Новая транзакция от: {payload.get('client_name')}")
    try:
        new_tx = OrderTransaction(
            client_name=payload['client_name'],
            waste_type=payload['waste_type'],
            weight_kg=float(payload['weight_kg']),
            user_id=payload.get('user_id')
        )
        db.add(new_tx); db.commit(); db.refresh(new_tx)
        
        if new_tx.user_id:
            user = db.query(UserProfile).filter(UserProfile.id == new_tx.user_id).first()
            if user:
                user.points += int(new_tx.weight_kg * 12)
                user.total_impact_kg += new_tx.weight_kg
                # Ранговая система
                if user.total_impact_kg > 1000: user.level = "Eco Guardian"
                elif user.total_impact_kg > 100: user.level = "Forest Friend"
                db.commit()

        return {"status": "success", "id": new_tx.id}
    except Exception as e:
        db.rollback(); logger.error(f"TX FAULT: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/orders/my/{uid}")
def get_user_history(uid: int, db: Session = Depends(get_db)):
    """Получение полной истории взаимодействия с ручной сериализацией"""
    txs = db.query(OrderTransaction).filter(OrderTransaction.user_id == uid).order_by(desc(OrderTransaction.timestamp)).all()
    return [
        {
            "id": t.id,
            "waste_type": t.waste_type,
            "weight_kg": t.weight_kg,
            "date": t.timestamp.isoformat(),
            "status": t.status
        } for t in txs
    ]


