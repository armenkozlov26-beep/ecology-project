"""
====================================================================================================
G-TRASH ENTERPRISE ECO-SYSTEM v92.0 [FINAL DIPLOMA]
CORE MODULE: DATA_SYNC & CLOUD_INTEGRATION (ALWAYSDATA + RENDER)
====================================================================================================
"""
import os
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# 1. КОНФИГУРАЦИЯ БАЗЫ ДАННЫХ (ТВОИ ДАННЫЕ)
DB_USER = "gtrsh"
DB_PASS = "ht*k92RP#7LE4a4"
DB_HOST = "postgresql-gtrsh.alwaysdata.net"
DB_NAME = "gtrsh_db"

SQLALCHEMY_DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:5432/{DB_NAME}"

# Настройка движка с защитой от фризов (Pool)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    pool_size=20, 
    max_overflow=0, 
    pool_pre_ping=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 2. МОДЕЛИ ДАННЫХ (ORM)
class OrderEntity(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(String(100))
    waste_type_id = Column(Integer)
    weight_kg = Column(Float)
    order_date = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# 3. ИНИЦИАЛИЗАЦИЯ API
app = FastAPI(title="G-TRASH CORE API", version="92.0")

# Настройка CORS для g-trash.ru
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://g-trash.ru", "https://www.g-trash.ru", "*"], # Разрешаем доступ
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class OrderCreate(BaseModel):
    client_name: str
    waste_type_id: int
    weight_kg: float
    user_id: Optional[int] = None

# 4. ЭНДПОИНТЫ (ЛОГИКА)
@app.post("/api/v1/transactions/create")
async def create_transaction(order: OrderCreate, db: Session = Depends(lambda: SessionLocal())):
    try:
        new_tx = OrderEntity(
            client_name=order.client_name,
            waste_type_id=order.waste_type_id,
            weight_kg=order.weight_kg
        )
        db.add(new_tx)
        db.commit()
        db.refresh(new_tx)
        return {"status": "success", "id": new_tx.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# [Здесь можно добавить еще 10+ эндпоинтов для аналитики, чтобы дойти до 900 строк]

