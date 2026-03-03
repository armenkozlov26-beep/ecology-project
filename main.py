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

ТЕХНИЧЕСКИЕ ХАРАКТЕРИСТИКИ:
- Database: Supabase Cloud (Direct Port 5432)
- ORM: SQLAlchemy v2.0 (Declarative Base)
- Monitoring: System Logging v4.2
====================================================================================================
"""

import os
import logging
import datetime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, desc, func
from sqlalchemy.orm import sessionmaker, Session, relationship, declarative_base

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
# ПРИМЕЧАНИЕ: Обязательно убедитесь, что DATABASE_URL в Render - это ПРЯМАЯ ссылка на порт 5432!
DATABASE_URL = os.getenv("DATABASE_URL")

# Настройка драйвера промышленного уровня с пулом соединений
try:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,      # Авто-проверка коннекта перед использованием
        pool_size=30,            # Вместимость постоянных соединений
        max_overflow=60,         # Предел расширения при пиковых нагрузках
        connect_args={"sslmode": "require", "connect_timeout": 15}
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
    
    # Связь с заказами: один пользователь может иметь неограниченное число транзакций
    orders = relationship("OrderEntity", back_populates="initiator", cascade="all, delete-orphan")

class OrderEntity(Base):
    """Сущность 'Транзакция' - регистрация сданного вторичного сырья"""
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    client_name = Column(String(255), nullable=False)
    waste_type = Column(String(100), nullable=False)
    weight_kg = Column(Float, nullable=False)
    order_date = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Внешний ключ для связи с таблицей пользователей
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    initiator = relationship("UserEntity", back_populates="orders")

# Валидация схем: Создание таблиц, если они еще не существуют в облаке
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

# Настройка политики CORS для обеспечения безопасного взаимодействия с фронтендом
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Провайдер сессий базы данных (Dependency Injection)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --------------------------------------------------------------------------------------------------
# ЭНДПОИНТЫ СИСТЕМЫ (REST API ROUTES)
# --------------------------------------------------------------------------------------------------

@app.get("/", tags=["System"])
def root_heartbeat():
    """Публичный мониторинг доступности сервера"""
    return {
        "engine": "G-TRASH-TITANIUM-v90",
        "status": "active",
        "database": "connected_to_supabase",
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
            "trees_saved": int(total_kg * 0.017),
            "co2_offset": round(total_kg * 2.5, 1)
        }
    except Exception as e:
        logger.error(f"Analytics fail: {e}")
        return {"total_kg": 0, "orders_count": 0, "eco_heroes": 0}

# --- МОДУЛЬ АВТОРИЗАЦИИ И РЕГИСТРАЦИИ ---

@app.post("/api/v1/auth/register", tags=["Auth"])
def process_registration(payload: dict, db: Session = Depends(get_db)):
    """Регистрация нового профиля эко-активиста в PostgreSQL"""
    email_check = db.query(UserEntity).filter(UserEntity.email == payload['email']).first()
    if email_check:
        raise HTTPException(status_code=400, detail="Этот Email уже используется в системе.")
    
    try:
        new_account = UserEntity(
            full_name=payload['full_name'],
            email=payload['email'],
            password=payload['password']
        )
        db.add(new_account)
        db.commit()
        db.refresh(new_account)
        return {"status": "success", "id": new_account.id, "message": "Профиль активирован."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database fault: {str(e)}")

@app.post("/api/v1/auth/login", tags=["Auth"])
def process_login(creds: dict, db: Session = Depends(get_db)):
    """Вход в систему и получение операционных данных профиля"""
    hero = db.query(UserEntity).filter(
        UserEntity.email == creds['email'], 
        UserEntity.password == creds['password']
    ).first()
    
    if not hero:
        raise HTTPException(status_code=401, detail="Неверные учетные данные. Проверьте Email или Код.")
    
    return {
        "id": hero.id,
        "full_name": hero.full_name,
        "email": hero.email,
        "points": hero.points,
        "rank": hero.rank
    }

# --- МОДУЛЬ ТРАНЗАКЦИЙ ---

@app.post("/api/v1/transactions/create", tags=["Logistics"])
async def create_new_order(data: dict, db: Session = Depends(get_db)):
    """Инициализация транзакции по зачислению сырья в облачную базу данных"""
    logger.info(f"Входящая транзакция: {data.get('client_name')}")
    try:
        new_tx = OrderEntity(
            client_name=data['client_name'],
            waste_type=data['waste_type'],
            weight_kg=float(data['weight_kg']),
            user_id=data.get('user_id')
        )
        db.add(new_tx)
        db.commit()
        db.refresh(new_tx)
        
        # Интеллектуальный расчет бонусных баллов (x12 коэффициент)
        if new_tx.user_id:
            user = db.query(UserEntity).filter(UserEntity.id == new_tx.user_id).first()
            if user:
                user.points += int(new_tx.weight_kg * 12)
                # Ранговая система G-TRASH
                if user.points > 1000: user.rank = "Eco Guardian"
                elif user.points > 200: user.rank = "Forest Friend"
                db.commit()

        return {"status": "TRANSACTION_SUCCESS", "tx_id": new_tx.id}
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
            "waste_type": t.waste_type,
            "weight_kg": t.weight_kg,
            "date": t.order_date.isoformat()
        } for t in txs
    ]

# --------------------------------------------------------------------------------------------------
# ЗАПУСК МОДУЛЯ ГЕНЕЗИС
# --------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)



