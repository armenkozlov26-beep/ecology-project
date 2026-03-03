"""
================================================================================
G-TRASH BACKEND SYSTEM v6.0 - PROFESSIONAL EDITION
DEVELOPED FOR DIPLOMA PROJECT: "INTELLIGENT WASTE MANAGEMENT ECOSYSTEM"
================================================================================
"""
import os
import datetime
import logging
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

# Логирование для отладки
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("G-TRASH-CORE")

# Конфигурация БД из переменных окружения
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- МОДЕЛИ БАЗЫ ДАННЫХ ---

class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True)
    password = Column(String(255))
    full_name = Column(String(255))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    orders = relationship("OrderDB", back_populates="owner")

class OrderDB(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(String(100))
    waste_type = Column(String(100))
    weight_kg = Column(Float)
    status = Column(String(50), default="В обработке")
    order_date = Column(DateTime, default=datetime.datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner = relationship("UserDB", back_populates="orders")

# Создание таблиц
Base.metadata.create_all(bind=engine)

# Инициализация FastAPI
app = FastAPI(title="G-TRASH CORE API", version="6.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ВАЛИДАЦИЯ ---
class OrderCreate(BaseModel):
    client_name: str
    waste_type: str
    weight_kg: float
    user_id: Optional[int] = None

class UserAuth(BaseModel):
    email: EmailStr
    password: str

class UserReg(UserAuth):
    full_name: str

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# --- ЭНДПОИНТЫ ---

@app.get("/")
def read_root():
    return {"status": "G-TRASH v6.0 API ACTIVE", "db": "CONNECTED"}

@app.post("/api/register")
def register(user: UserReg, db: Session = Depends(get_db)):
    db_user = db.query(UserDB).filter(UserDB.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
    new_user = UserDB(email=user.email, password=user.password, full_name=user.full_name)
    db.add(new_user)
    db.commit()
    return {"status": "success", "id": new_user.id}

@app.post("/api/login")
def login(user: UserAuth, db: Session = Depends(get_db)):
    db_user = db.query(UserDB).filter(UserDB.email == user.email, UserDB.password == user.password).first()
    if not db_user:
        raise HTTPException(status_code=401, detail="Неверные учетные данные")
    return {"id": db_user.id, "full_name": db_user.full_name, "email": db_user.email}

@app.post("/api/orders")
async def create_order(order: OrderCreate, db: Session = Depends(get_db)):
    try:
        new_order = OrderDB(
            client_name=order.client_name,
            waste_type=order.waste_type,
            weight_kg=order.weight_kg,
            user_id=order.user_id
        )
        db.add(new_order)
        db.commit()
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/my-orders/{user_id}")
def get_history(user_id: int, db: Session = Depends(get_db)):
    return db.query(OrderDB).filter(OrderDB.user_id == user_id).order_by(OrderDB.order_date.desc()).all()

@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    total_w = db.query(OrderDB).with_entities(OrderDB.weight_kg).all()
    return {
        "total_kg": sum([x[0] for x in total_w if x[0]]),
        "count": len(total_w),
        "users": db.query(UserDB).count()
    }


