"""
====================================================================================================
G-TRASH PROFESSIONAL CORE SYSTEM v13.0
DIPLOMA PROJECT: INTELLIGENT LOGISTICS & WASTE MANAGEMENT
====================================================================================================
"""
import os
import logging
import datetime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, create_engine, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

# --- НАСТРОЙКА ЛОГИРОВАНИЯ ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("G_TRASH_CORE")

# --- КОНФИГУРАЦИЯ БАЗЫ ДАННЫХ ---
DATABASE_URL = os.getenv("DATABASE_URL")

# Прямое подключение к PostgreSQL (Supabase)
engine = create_engine(
    DATABASE_URL, 
    pool_pre_ping=True, # Проверка соединения перед каждым запросом
    pool_recycle=3600,
    connect_args={"sslmode": "require"}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- МОДЕЛИ ДАННЫХ (ORM) ---

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    orders = relationship("Order", back_populates="owner")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(String(255), nullable=False)
    waste_type = Column(String(255), nullable=False)
    weight_kg = Column(Float, nullable=False)
    order_date = Column(DateTime, default=datetime.datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner = relationship("User", back_populates="orders")

# Авто-создание таблиц
try:
    Base.metadata.create_all(bind=engine)
    logger.info("CORE: Успешная синхронизация с Supabase.")
except Exception as e:
    logger.error(f"DATABASE CONNECTION ERROR: {e}")

# --- API SETUP ---
app = FastAPI(title="G-TRASH PRO API", version="13.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- ЭНДПОИНТЫ ---

@app.get("/", tags=["System"])
def root():
    return {"status": "active", "db": "connected", "v": "13.0.0"}

@app.get("/api/stats/global")
def get_global_stats(db: Session = Depends(get_db)):
    """Получение статистики для главной страницы"""
    try:
        orders = db.query(Order).all()
        total_kg = sum([o.weight_kg for o in orders if o.weight_kg])
        users_count = db.query(User).count()
        return {
            "total_kg": round(total_kg, 1),
            "total_orders": len(orders),
            "total_users": users_count
        }
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return {"total_kg": 0, "total_orders": 0, "total_users": 0}

@app.post("/api/orders/create")
async def create_new_order(payload: dict, db: Session = Depends(get_db)):
    """Запись новой заявки в PostgreSQL"""
    try:
        new_order = Order(
            client_name=payload['client_name'],
            waste_type=payload['waste_type'],
            weight_kg=float(payload['weight_kg']),
            user_id=payload.get('user_id')
        )
        db.add(new_order)
        db.commit()
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        logger.error(f"Order error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/register")
def register(user_in: dict, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user_in['email']).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email занят")
    new_user = User(full_name=user_in['full_name'], email=user_in['email'], password=user_in['password'])
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"id": new_user.id, "full_name": new_user.full_name}

@app.post("/api/auth/login")
def login(creds: dict, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == creds['email'], User.password == creds['password']).first()
    if not user:
        raise HTTPException(status_code=401, detail="Неверные данные")
    return {"id": user.id, "full_name": user.full_name, "email": user.email}

@app.get("/api/orders/my/{uid}")
def get_history(uid: int, db: Session = Depends(get_db)):
    return db.query(Order).filter(Order.user_id == uid).order_by(desc(Order.order_date)).all()
