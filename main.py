# =========================
# G-TRASH MEGA PLATFORM
# =========================

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import (
    create_engine, Column, Integer, String,
    Float, DateTime, ForeignKey, Boolean, func
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, Session
from passlib.context import CryptContext
from jose import jwt, JWTError
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
import os

# =========================
# CONFIG
# =========================

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/eco")
SECRET_KEY = "SUPER_SECRET_KEY_CHANGE_ME"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

# =========================
# DB
# =========================

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# =========================
# SECURITY
# =========================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def hash_password(p: str):
    return pwd_context.hash(p)

def verify_password(p: str, h: str):
    return pwd_context.verify(p, h)

def create_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# =========================
# MODELS
# =========================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True)
    full_name = Column(String)
    password = Column(String)
    role = Column(String, default="user")  # user | admin | partner
    points = Column(Integer, default=0)
    created = Column(DateTime, default=datetime.utcnow)

    orders = relationship("Order", back_populates="user")

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    waste_type = Column(String)
    weight_kg = Column(Float)
    price = Column(Float)
    created = Column(DateTime, default=datetime.utcnow)

    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="orders")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    message = Column(String)
    is_read = Column(Boolean, default=False)
    created = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"))

Base.metadata.create_all(engine)

# =========================
# SCHEMAS
# =========================

class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class OrderCreate(BaseModel):
    waste_type: str
    weight_kg: float

# =========================
# APP
# =========================

app = FastAPI(title="G-TRASH MEGA PLATFORM")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_headers=["*"],
    allow_methods=["*"]
)

# =========================
# DEPENDENCIES
# =========================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def require_admin(user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user

# =========================
# AUTH
# =========================

@app.post("/auth/register")
def register(data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(400, "Email exists")

    user = User(
        email=data.email,
        full_name=data.full_name,
        password=hash_password(data.password)
    )
    db.add(user)
    db.commit()
    return {"status": "registered"}

@app.post("/auth/login")
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password):
        raise HTTPException(401, "Invalid credentials")

    token = create_token({"sub": user.id})
    return {"access_token": token, "token_type": "bearer"}

# =========================
# ORDERS
# =========================

@app.post("/orders/create")
def create_order(
    data: OrderCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    price = data.weight_kg * 2.5
    points = int(data.weight_kg * 10)

    order = Order(
        waste_type=data.waste_type,
        weight_kg=data.weight_kg,
        price=price,
        user=user
    )
    user.points += points

    db.add(order)
    db.add(Notification(
        message=f"Начислено {points} баллов",
        user_id=user.id
    ))
    db.commit()

    return {"status": "created", "price": price, "points": points}

@app.get("/orders/my")
def my_orders(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(Order).filter(Order.user_id == user.id).all()

# =========================
# ANALYTICS
# =========================

@app.get("/analytics/global", dependencies=[Depends(require_admin)])
def analytics(db: Session = Depends(get_db)):
    by_type = db.query(
        Order.waste_type,
        func.sum(Order.weight_kg)
    ).group_by(Order.waste_type).all()

    users = db.query(User).count()
    orders = db.query(Order).count()

    return {
        "users": users,
        "orders": orders,
        "by_type": {k: float(v) for k, v in by_type}
    }

# =========================
# NOTIFICATIONS
# =========================

@app.get("/notifications")
def notifications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(Notification)\
        .filter(Notification.user_id == user.id)\
        .order_by(Notification.created.desc())\
        .all()

# =========================
# ROOT
# =========================

@app.get("/")
def root():
    return {
        "project": "G-TRASH",
        "status": "RUNNING",
        "time": datetime.utcnow()
    }

