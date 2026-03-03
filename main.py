import os
import datetime
import logging
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

# --- НАСТРОЙКИ БД ---
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- МОДЕЛИ (ТАБЛИЦЫ) ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255))
    email = Column(String(255), unique=True, index=True)
    password = Column(String(255))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    orders = relationship("Order", back_populates="owner")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(String(255))
    waste_type = Column(String(255))
    weight_kg = Column(Float)
    order_date = Column(DateTime, default=datetime.datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner = relationship("User", back_populates="orders")

# Авто-создание таблиц
Base.metadata.create_all(bind=engine)

# --- FASTAPI ПРИЛОЖЕНИЕ ---
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# --- ПУТИ (ENDPOINTS) ---
@app.get("/")
def home(): return {"status": "G-TRASH v10.0 LIVE"}

@app.post("/auth/register")
def register(user: dict, db: Session = Depends(get_db)):
    new_user = User(full_name=user['full_name'], email=user['email'], password=user['password'])
    db.add(new_user); db.commit(); db.refresh(new_user)
    return {"id": new_user.id, "full_name": new_user.full_name}

@app.post("/auth/login")
def login(user: dict, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user['email'], User.password == user['password']).first()
    if not db_user: raise HTTPException(status_code=401, detail="Ошибка входа")
    return {"id": db_user.id, "full_name": db_user.full_name}

@app.post("/orders/create")
def create_order(order: dict, db: Session = Depends(get_db)):
    try:
        new_order = Order(
            client_name=order['client_name'], 
            waste_type=order['waste_type'], 
            weight_kg=float(order['weight_kg']), 
            user_id=order.get('user_id')
        )
        db.add(new_order); db.commit()
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/orders/my/{uid}")
def get_my(uid: int, db: Session = Depends(get_db)):
    return db.query(Order).filter(Order.user_id == uid).all()

@app.get("/stats")
def stats(db: Session = Depends(get_db)):
    orders = db.query(Order).all()
    return {"total_kg": sum([o.weight_kg for o in orders]), "count": len(orders), "users": db.query(User).count()}

