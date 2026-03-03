import os
import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

# Настройка БД
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- МОДЕЛИ БД ---

class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String) # В реальном проекте тут должен быть хеш
    full_name = Column(String)
    orders = relationship("OrderDB", back_populates="owner")

class OrderDB(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(String(100))
    waste_type = Column(String) 
    weight_kg = Column(Float)
    order_date = Column(DateTime, default=datetime.datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    owner = relationship("UserDB", back_populates="orders")

# Создание таблиц
Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- СХЕМЫ ДАННЫХ ---

class UserReg(BaseModel):
    email: str
    password: str
    full_name: str

class UserLogin(BaseModel):
    email: str
    password: str

class OrderCreate(BaseModel):
    client_name: str
    waste_type: str
    weight_kg: float
    user_id: Optional[int] = None

# --- ЭНДПОИНТЫ ---

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/register")
def register(user: UserReg, db: Session = Depends(get_db)):
    db_user = UserDB(email=user.email, password=user.password, full_name=user.full_name)
    db.add(db_user)
    try:
        db.commit()
        return {"status": "success"}
    except:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email уже занят")

@app.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(UserDB).filter(UserDB.email == user.email, UserDB.password == user.password).first()
    if not db_user:
        raise HTTPException(status_code=400, detail="Неверный логин или пароль")
    return {"id": db_user.id, "full_name": db_user.full_name, "email": db_user.email}

@app.post("/send")
async def create_order(order: OrderCreate, db: Session = Depends(get_db)):
    new_order = OrderDB(
        client_name=order.client_name,
        waste_type=order.waste_type,
        weight_kg=order.weight_kg,
        user_id=order.user_id
    )
    db.add(new_order)
    db.commit()
    return {"status": "success"}

@app.get("/my-orders/{user_id}")
def get_orders(user_id: int, db: Session = Depends(get_db)):
    return db.query(OrderDB).filter(OrderDB.user_id == user_id).all()

@app.get("/")
def home():
    return {"status": "G-TRASH API 3.0 ACTIVE"}
