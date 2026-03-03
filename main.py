import os
import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Подключение к БД
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- МОДЕЛИ ---
class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    full_name = Column(String)

class OrderDB(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(String)
    waste_type = Column(String)
    weight_kg = Column(Float)
    order_date = Column(DateTime, default=datetime.datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

# Пересоздание таблиц
Base.metadata.create_all(bind=engine)

app = FastAPI()

# ОБЯЗАТЕЛЬНО: Разрешаем все домены для диплома
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- СХЕМЫ ---
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

@app.post("/api/register")
def register(user: UserReg, db: Session = Depends(get_db)):
    db_user = db.query(UserDB).filter(UserDB.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email уже занят")
    new_user = UserDB(email=user.email, password=user.password, full_name=user.full_name)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"id": new_user.id, "full_name": new_user.full_name}

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
def get_user_orders(user_id: int, db: Session = Depends(get_db)):
    return db.query(OrderDB).filter(OrderDB.user_id == user_id).order_by(OrderDB.order_date.desc()).all()

@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    all_orders = db.query(OrderDB).all()
    total_kg = sum([o.weight_kg for o in all_orders])
    return {
        "total_kg": total_kg,
        "count": len(all_orders),
        "users": db.query(UserDB).count()
    }

@app.get("/")
def home():
    return {"status": "G-TRASH API v6.0 LIVE"}
