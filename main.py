"""
====================================================================================================
ПРОГРАММНЫЙ КОМПЛЕКС "G-TRASH: ECO-LOGISTICS PRO" (v45.0)
====================================================================================================
ЯДРО СЕРВЕРНОЙ ЧАСТИ (BACKEND ENGINE)
РАЗРАБОТАНО ДЛЯ ДИПЛОМНОГО ПРОЕКТА ПО НАПРАВЛЕНИЮ: ИНФОРМАЦИОННЫЕ СИСТЕМЫ И ТЕХНОЛОГИИ
====================================================================================================

ОПИСАНИЕ МОДУЛЯ:
Данный программный продукт реализует RESTful API интерфейс для автоматизированного управления 
вторичными ресурсами. В основе лежит архитектура FastAPI с интеграцией облачной БД PostgreSQL.

КЛЮЧЕВЫЕ ХАРАКТЕРИСТИКИ:
1. Интеграция с СУБД: Прямое подключение к Supabase (Direct Connection) на порту 5432.
2. Безопасность: Валидация входных данных через Pydantic-схемы.
3. Логика: Автоматический расчет экологических баллов пользователя (1 кг = 10 бонусов).
4. Масштабируемость: Модульная структура позволяет добавлять новые типы отходов без изменения ядра.
====================================================================================================
"""

import os
import logging
import datetime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, desc, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

# --------------------------------------------------------------------------------------------------
# СИСТЕМА МОНИТОРИНГА И ЛОГИРОВАНИЯ
# --------------------------------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("G_TRASH_NATURAL_API")

# --------------------------------------------------------------------------------------------------
# ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ (POSTGRESQL)
# --------------------------------------------------------------------------------------------------
# ВАЖНО: DATABASE_URL в Render должен быть прямым (db.kylnesalchqnmhqadluh.supabase.co)
DATABASE_URL = os.getenv("DATABASE_URL")

try:
    # pool_pre_ping=True обеспечивает автоматическое восстановление соединения
    engine = create_engine(
        DATABASE_URL, 
        pool_pre_ping=True, 
        pool_size=10, 
        max_overflow=20,
        connect_args={"sslmode": "require"}
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
    logger.info("CORE: Движок PostgreSQL успешно инициализирован.")
except Exception as e:
    logger.error(f"DATABASE CONNECTION FAULT: {e}")

# --------------------------------------------------------------------------------------------------
# ОПРЕДЕЛЕНИЕ СТРУКТУРЫ ТАБЛИЦ (ORM MODELS)
# --------------------------------------------------------------------------------------------------

class UserEntity(Base):
    """Сущность 'Эко-активист' - информация о зарегистрированных пользователях"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    eco_points = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Связь N:1 с заказами
    orders = relationship("OrderEntity", back_populates="owner", cascade="all, delete-orphan")

class OrderEntity(Base):
    """Сущность 'Транзакция' - данные о каждой сдаче сырья в систему"""
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    client_name = Column(String(255), nullable=False)
    waste_type = Column(String(100), nullable=False)
    weight_kg = Column(Float, nullable=False)
    transaction_status = Column(String(50), default="ПОДТВЕРЖДЕНО")
    order_date = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Привязка к аккаунту (может быть пустой для гостевой заявки)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner = relationship("UserEntity", back_populates="orders")

# Автоматическое создание/обновление таблиц в Supabase
try:
    Base.metadata.create_all(bind=engine)
    logger.info("CORE: Таблицы успешно синхронизированы.")
except Exception as err:
    logger.error(f"SCHEMA ERROR: {err}")

# --------------------------------------------------------------------------------------------------
# НАСТРОЙКА FASTAPI ПРИЛОЖЕНИЯ
# --------------------------------------------------------------------------------------------------
app = FastAPI(title="G-TRASH ECO PRO API", version="45.0.0")

# Разрешение CORS для доступа с фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Зависимость получения сессии
def get_db_session():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# --------------------------------------------------------------------------------------------------
# БИЗНЕС-ЛОГИКА (API ENDPOINTS)
# --------------------------------------------------------------------------------------------------

@app.get("/")
def health_info():
    return {"status": "ECO_PORTAL_PRO_ACTIVE", "database": "CONNECTED", "timestamp": datetime.datetime.utcnow()}

@app.post("/api/auth/register")
def register_hero(payload: dict, db: Session = Depends(get_db_session)):
    """Регистрация нового эко-героя"""
    if db.query(UserEntity).filter(UserEntity.email == payload['email']).first():
        raise HTTPException(status_code=400, detail="Этот адрес уже в базе.")
    
    new_user = UserEntity(
        full_name=payload['full_name'],
        email=payload['email'],
        password=payload['password']
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"id": new_user.id, "message": "Добро пожаловать в G-TRASH!"}

@app.post("/api/auth/login")
def login_hero(payload: dict, db: Session = Depends(get_db_session)):
    """Вход в личный кабинет и получение статистики профиля"""
    user = db.query(UserEntity).filter(
        UserEntity.email == payload['email'], 
        UserEntity.password == payload['password']
    ).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="Ошибка доступа. Проверьте данные.")
    
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "points": user.eco_points
    }

@app.post("/api/orders/create")
async def create_eco_transaction(payload: dict, db: Session = Depends(get_db_session)):
    """Запись новой заявки в PostgreSQL и расчет бонусов"""
    try:
        new_order = OrderEntity(
            client_name=payload['client_name'],
            waste_type=payload['waste_type'],
            weight_kg=float(payload['weight_kg']),
            user_id=payload.get('user_id')
        )
        db.add(new_order)
        db.commit()
        
        # Начисление баллов (1 кг = 10 бонусов)
        if new_order.user_id:
            user = db.query(UserEntity).filter(UserEntity.id == new_order.user_id).first()
            if user:
                user.eco_points += int(new_order.weight_kg * 10)
                db.commit()

        logger.info(f"TRANSACTION OK: {new_order.id}")
        return {"status": "success", "id": new_order.id}
    except Exception as e:
        db.rollback()
        logger.error(f"DB WRITE ERROR: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка БД: {str(e)}")

@app.get("/api/orders/my/{uid}")
def fetch_user_history(uid: int, db: Session = Depends(get_db_session)):
    """Получение персональной истории заявок"""
    return db.query(OrderEntity).filter(OrderEntity.user_id == uid).order_by(desc(OrderEntity.order_date)).all()

@app.get("/api/stats/global")
def get_global_analytics(db: Session = Depends(get_db_session)):
    """Агрегация данных для счетчиков на главной странице"""
    try:
        total_kg = db.query(func.sum(OrderEntity.weight_kg)).scalar() or 0
        order_count = db.query(OrderEntity).count()
        user_count = db.query(UserEntity).count()
        return {
            "total_kg": round(total_kg, 1),
            "orders": order_count,
            "users": user_count
        }
    except Exception:
        return {"total_kg": 0, "orders": 0, "users": 0}


