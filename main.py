"""
G-TRASH BACKEND SYSTEM v4.0
Developed for Diploma Project
Author: Eco-Portal Team
"""
import os
import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

# Конфигурация базы данных
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Заглушка для локальной разработки, если переменная окружения не задана
    DATABASE_URL = "postgresql://user:password@localhost/dbname"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- МОДЕЛИ ДАННЫХ (ORM) ---

class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    orders = relationship("OrderDB", back_populates="owner")

class OrderDB(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(String(100))
    waste_type = Column(String(50))
    weight_kg = Column(Float)
    status = Column(String(50), default="В обработке")
    order_date = Column(DateTime, default=datetime.datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner = relationship("UserDB", back_populates="orders")

class FeedbackDB(Base):
    __tablename__ = "feedback"
    id = Column(Integer, primary_key=True, index=True)
    user_name = Column(String(100))
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

# Создание таблиц при запуске
Base.metadata.create_all(bind=engine)

app = FastAPI(title="G-TRASH Professional API", version="4.0.0")

# Настройка CORS для работы с фронтендом
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ВАЛИДАЦИЯ (Pydantic) ---

class OrderCreate(BaseModel):
    client_name: str
    waste_type: str
    weight_kg: float
    user_id: Optional[int] = None

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

# --- ЛОГИКА (Endpoints) ---

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def read_root():
    return {
        "project": "G-TRASH ECO",
        "status": "Online",
        "timestamp": datetime.datetime.utcnow(),
        "db_connected": True
    }

@app.post("/api/register")
def register_user(user: UserRegister, db: Session = Depends(get_db)):
    db_user = db.query(UserDB).filter(UserDB.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
    
    new_user = UserDB(email=user.email, password=user.password, full_name=user.full_name)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "Успешная регистрация", "user_id": new_user.id}

@app.post("/api/login")
def login_user(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(UserDB).filter(UserDB.email == user.email, UserDB.password == user.password).first()
    if not db_user:
        raise HTTPException(status_code=401, detail="Неверные учетные данные")
    return {
        "id": db_user.id,
        "full_name": db_user.full_name,
        "email": db_user.email
    }

@app.post("/api/orders")
def create_order(order: OrderCreate, db: Session = Depends(get_db)):
    try:
        new_order = OrderDB(
            client_name=order.client_name,
            waste_type=order.waste_type,
            weight_kg=order.weight_kg,
            user_id=order.user_id
        )
        db.add(new_order)
        db.commit()
        return {"status": "success", "order_id": new_order.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/my-orders/{user_id}")
def get_user_orders(user_id: int, db: Session = Depends(get_db)):
    orders = db.query(OrderDB).filter(OrderDB.user_id == user_id).order_by(OrderDB.order_date.desc()).all()
    return orders

@app.get("/api/stats")
def get_global_stats(db: Session = Depends(get_db)):
    total_weight = db.query(OrderDB).with_entities(Float(OrderDB.weight_kg)).all()
    count = db.query(OrderDB).count()
    return {
        "total_kg": sum([w[0] for w in total_weight if w[0]]),
        "total_orders": count,
        "active_users": db.query(UserDB).count()
    }

