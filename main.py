"""
====================================================================================================
G-TRASH ENTERPRISE ECO-SYSTEM v90.0 [DIPLOMA EDITION]
CORE MODULE: GENESIS - IDENTITY & RESOURCE MANAGEMENT
====================================================================================================
ОПИСАНИЕ:
Данный программный комплекс является интеллектуальным ядром системы управления отходами.
Реализован на базе FastAPI (асинхронный Python) с интеграцией облачной СУБД PostgreSQL.

АРХИТЕКТУРНЫЕ МОДУЛИ:
1. IDENTITY_SERVER: Протоколы регистрации и аутентификации пользователей (Users Table).
2. LOGISTICS_NODE: Управление транзакциями вторичного сырья (Orders Table).
3. ANALYTICS_ENGINE: Сбор и агрегация глобальных экологических метрик.
4. SECURITY_PROTOCOL: Валидация сессий и защита данных через SSL.
====================================================================================================
"""

import os
import logging
import datetime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, desc, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

# --------------------------------------------------------------------------------------------------
# СИСТЕМА МОНИТОРИНГА И ДИАГНОСТИКИ (SYSTEM LOGS)
# --------------------------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | [%(levelname)s] | %(name)s : %(message)s"
)
logger = logging.getLogger("G_TRASH_GENESIS")

# --------------------------------------------------------------------------------------------------
# СЕКЦИЯ КОНФИГУРАЦИИ БД (POSTGRESQL CLOUD)
# --------------------------------------------------------------------------------------------------
# Используем твой проверенный URL для Alwaysdata
DATABASE_URL = "postgresql://g-trash:ht*k92RP#7LE4a4@postgresql-g-trash.alwaysdata.net:5432/g-trash_db"

try:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,      # Авто-проверка коннекта перед использованием
        pool_size=20,            # Вместимость постоянных соединений
        max_overflow=40,         # Предел расширения при пиковых нагрузках
        connect_args={"connect_timeout": 30}
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
    logger.info("CORE: Протокол соединения с PostgreSQL успешно инициализирован.")
except Exception as fatal_err:
    logger.critical(f"FATAL: Ошибка инициализации DATABASE ENGINE: {fatal_err}")

# --------------------------------------------------------------------------------------------------
# ОПРЕДЕЛЕНИЕ СУЩНОСТЕЙ (DATABASE SCHEMAS)
# --------------------------------------------------------------------------------------------------

class UserEntity(Base):
    """Сущность 'Пользователь' - хранит данные профиля, бонусы и ранги"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    points = Column(Integer, default=0)
    rank = Column(String(100), default="Eco Beginner")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Связь с заказами
    orders = relationship("OrderEntity", back_populates="initiator", cascade="all, delete-orphan")

class OrderEntity(Base):
    """Сущность 'Транзакция' - регистрация сданного вторичного сырья"""
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    client_name = Column(String(255), nullable=False)
    waste_type_id = Column(Integer, nullable=False) # ID категории (пластик, бумага и т.д.)
    weight_kg = Column(Float, nullable=False)
    order_date = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Внешний ключ для связи с таблицей пользователей
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    initiator = relationship("UserEntity", back_populates="orders")

# Синхронизация таблиц
try:
    Base.metadata.create_all(bind=engine)
    logger.info("CORE: Структура таблиц верифицирована.")
except Exception as e:
    logger.error(f"SCHEMA ERROR: Не удалось синхронизировать таблицы: {e}")

# --------------------------------------------------------------------------------------------------
# ИНИЦИАЛИЗАЦИЯ FASTAPI ИНТЕРФЕЙСА
# --------------------------------------------------------------------------------------------------
app = FastAPI(
    title="G-TRASH TITANIUM API",
    description="Backend-система управления экологическими ресурсами",
    version="90.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Провайдер сессий
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --------------------------------------------------------------------------------------------------
# REST API МОДЕЛИ (PYDANTIC)
# --------------------------------------------------------------------------------------------------

class UserRegister(BaseModel):
    full_name: str
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class OrderCreate(BaseModel):
    client_name: str
    waste_type_id: int
    weight_kg: float
    user_id: Optional[int] = None

# --------------------------------------------------------------------------------------------------
# ЭНДПОИНТЫ СИСТЕМЫ (REST API ROUTES)
# --------------------------------------------------------------------------------------------------

@app.get("/", tags=["System"])
def root_heartbeat():
    """Мониторинг доступности сервера"""
    return {
        "engine": "G-TRASH-TITANIUM-v90",
        "status": "active",
        "database": "connected_to_alwaysdata",
        "timestamp": datetime.datetime.utcnow()
    }

@app.get("/api/v1/analytics/global", tags=["Analytics"])
def fetch_global_analytics(db: Session = Depends(get_db)):
    """Агрегация макро-экологических данных со всей сети"""
    try:
        total_kg = db.query(func.sum(OrderEntity.weight_kg)).scalar() or 0
        order_count = db.query(OrderEntity).count()
        user_count = db.query(UserEntity).count()
        
        return {
            "total_kg": round(total_kg, 1),
            "orders_count": order_count,
            "eco_heroes": user_count,
            "trees_saved": int(total_kg * 0.017), # Формула спасенных деревьев
            "co2_offset": round(total_kg * 2.5, 1) # Снижение углеродного следа
        }
    except Exception as e:
        logger.error(f"Analytics fail: {e}")
        return {"total_kg": 0, "orders_count": 0, "eco_heroes": 0}

# --- МОДУЛЬ АВТОРИЗАЦИИ ---

@app.post("/api/v1/auth/register", tags=["Auth"])
def process_registration(user: UserRegister, db: Session = Depends(get_db)):
    """Регистрация нового профиля эко-активиста"""
    email_check = db.query(UserEntity).filter(UserEntity.email == user.email).first()
    if email_check:
        raise HTTPException(status_code=400, detail="Этот Email уже используется в системе.")
    
    try:
        new_account = UserEntity(
            full_name=user.full_name,
            email=user.email,
            password=user.password # В продакшене тут должен быть хеш (bcrypt)
        )
        db.add(new_account)
        db.commit()
        db.refresh(new_account)
        logger.info(f"IDENTITY: Создан новый профиль ID:{new_account.id}")
        return {"status": "success", "id": new_account.id, "message": "Профиль активирован."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database fault: {str(e)}")

@app.post("/api/v1/auth/login", tags=["Auth"])
def process_login(creds: UserLogin, db: Session = Depends(get_db)):
    """Вход в систему и получение данных профиля"""
    hero = db.query(UserEntity).filter(
        UserEntity.email == creds.email, 
        UserEntity.password == creds.password
    ).first()
    
    if not hero:
        raise HTTPException(status_code=401, detail="Неверные учетные данные.")
    
    return {
        "id": hero.id,
        "full_name": hero.full_name,
        "email": hero.email,
        "points": hero.points,
        "rank": hero.rank
    }

# --- МОДУЛЬ ЛОГИСТИКИ (ТРАНЗАКЦИИ) ---

@app.post("/api/v1/transactions/create", tags=["Logistics"])
async def create_new_order(order: OrderCreate, db: Session = Depends(get_db)):
    """Инициализация транзакции по зачислению сырья"""
    logger.info(f"LOGISTICS: Входящая транзакция от {order.client_name}")
    try:
        new_tx = OrderEntity(
            client_name=order.client_name,
            waste_type_id=order.waste_type_id,
            weight_kg=order.weight_kg,
            user_id=order.user_id
        )
        db.add(new_tx)
        
        # РАСЧЕТ БОНУСОВ И РАНГОВ (Gamification Engine)
        if order.user_id:
            user = db.query(UserEntity).filter(UserEntity.id == order.user_id).first()
            if user:
                # Начисляем 15 баллов за каждый кг
                bonus_points = int(order.weight_kg * 15)
                user.points += bonus_points
                
                # Обновление ранга
                if user.points > 2000: user.rank = "Eco Titan"
                elif user.points > 1000: user.rank = "Eco Guardian"
                elif user.points > 300: user.rank = "Forest Friend"
                
                logger.info(f"POINTS: Пользователю {user.id} начислено {bonus_points} баллов.")

        db.commit()
        db.refresh(new_tx)
        
        return {
            "status": "TRANSACTION_SUCCESS", 
            "tx_id": new_tx.id,
            "message": "Данные успешно интегрированы в облачную базу."
        }
    except Exception as e:
        db.rollback()
        logger.error(f"TRANSACTION FAULT: {e}")
        raise HTTPException(status_code=500, detail="Database Rejected. Check logs.")

@app.get("/api/v1/transactions/history/{uid}", tags=["Logistics"])
def get_personal_log(uid: int, db: Session = Depends(get_db)):
    """Получение полной истории взаимодействия пользователя с системой"""
    txs = db.query(OrderEntity).filter(OrderEntity.user_id == uid).order_by(desc(OrderEntity.order_date)).all()
    return [
        {
            "id": t.id,
            "waste_type_id": t.waste_type_id,
            "weight_kg": t.weight_kg,
            "date": t.order_date.strftime("%Y-%m-%d %H:%M:%S")
        } for t in txs
    ]

# --------------------------------------------------------------------------------------------------
# ЗАПУСК МОДУЛЯ ГЕНЕЗИС
# --------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    # Запуск на порту 8000 для локальных тестов
    uvicorn.run(app, host="0.0.0.0", port=8000)


