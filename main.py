"""
====================================================================================================
ПРОГРАММНЫЙ КОМПЛЕКС "G-TRASH: INTELLIGENT WASTE MANAGEMENT SYSTEM" (v7.0)
====================================================================================================
Данный модуль является ядром серверной части (Backend), реализованным на фреймворке FastAPI.
Проект разработан в рамках дипломной работы по направлению "Информационные системы и технологии".

ОСНОВНЫЕ ФУНКЦИОНАЛЬНЫЕ ВОЗМОЖНОСТИ:
1. Интеграция с реляционной базой данных PostgreSQL (через облачный сервис Supabase).
2. Реализация RESTful API для взаимодействия с клиентской частью.
3. Система аутентификации и авторизации пользователей.
4. Управление транзакциями при оформлении заявок на вывоз вторичного сырья.
5. Автоматизированный сбор статистики по экологическим показателям региона.

АРХИТЕКТУРА СИСТЕМЫ:
- Слои доступа к данным (SQLAlchemy ORM).
- Слой бизнес-логики (FastAPI Endpoints).
- Слой валидации (Pydantic Models).
====================================================================================================
"""

import os
import logging
import datetime
from typing import List, Optional, Any

from fastapi import FastAPI, HTTPException, Depends, status, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field, validator
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, create_engine, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

# ==================================================================================================
# СЕКЦИЯ ЛОГИРОВАНИЯ И КОНФИГУРАЦИИ
# ==================================================================================================

# Настройка системного логгера для мониторинга событий в реальном времени на Render
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("G_TRASH_CORE")

# Извлечение строки подключения к БД из переменных окружения сервера
# Ожидается формат: postgresql://user:password@host:port/dbname
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    logger.error("КРИТИЧЕСКАЯ ОШИБКА: Переменная DATABASE_URL не установлена!")
    # В случае локального тестирования можно указать заглушку, 
    # но для Render это приведет к ошибке запуска.
else:
    logger.info("Успешное обнаружение конфигурации базы данных.")

# ==================================================================================================
# СЛОЙ ДОСТУПА К ДАННЫМ (DATABASE LAYER)
# ==================================================================================================

# Инициализация движка SQLAlchemy
# Используем pool_pre_ping для предотвращения обрывов соединений с Supabase
engine = create_engine(
    DATABASE_URL, 
    pool_pre_ping=True,
    pool_recycle=3600
)

# Настройка фабрики сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для всех моделей данных
Base = declarative_base()

class UserDB(Base):
    """
    Модель данных 'Пользователь'.
    Хранит информацию о зарегистрированных эко-активистах системы.
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    registration_date = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Связь с таблицей заказов (Один-ко-многим)
    orders = relationship("OrderDB", back_populates="owner", cascade="all, delete-orphan")

class OrderDB(Base):
    """
    Модель данных 'Заказ'.
    Хранит записи о каждой транзакции по сдаче вторсырья.
    """
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    client_name = Column(String(100), nullable=False)
    waste_type = Column(String(100), nullable=False)
    weight_kg = Column(Float, nullable=False)
    order_status = Column(String(50), default="Принято в обработку")
    order_date = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Внешний ключ для связи с пользователем
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner = relationship("UserDB", back_populates="orders")

# Автоматическое создание таблиц в PostgreSQL при запуске приложения
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Синхронизация структуры БД выполнена успешно.")
except Exception as e:
    logger.error(f"Ошибка синхронизации БД: {str(e)}")

# ==================================================================================================
# СЛОЙ ВАЛИДАЦИИ ДАННЫХ (DTO / SCHEMAS)
# ==================================================================================================

class OrderCreateSchema(BaseModel):
    """Схема валидации входящих данных для создания нового заказа"""
    client_name: str = Field(..., min_length=2, max_length=100)
    waste_type: str = Field(..., min_length=3)
    weight_kg: float = Field(..., gt=0)
    user_id: Optional[int] = None

    class Config:
        schema_extra = {
            "example": {
                "client_name": "Иван Иванов",
                "waste_type": "Пластик PET",
                "weight_kg": 15.5,
                "user_id": 1
            }
        }

class UserAuthSchema(BaseModel):
    """Базовая схема для авторизации"""
    email: EmailStr
    password: str = Field(..., min_length=6)

class UserRegisterSchema(UserAuthSchema):
    """Расширенная схема для регистрации новых пользователей"""
    full_name: str = Field(..., min_length=2)

# ==================================================================================================
# ЯДРО ПРИЛОЖЕНИЯ И MIDDLEWARE
# ==================================================================================================

app = FastAPI(
    title="G-TRASH Intelligence API",
    description="Backend API для системы автоматизации переработки отходов",
    version="7.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Настройка CORS (Cross-Origin Resource Sharing)
# Позволяет вашему фронтенду (на любом домене) безопасно обращаться к API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    """Зависимость (Dependency Injection) для получения сессии базы данных"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==================================================================================================
# КОНТРОЛЛЕРЫ (API ENDPOINTS)
# ==================================================================================================

@app.get("/", tags=["System"])
def system_health_check():
    """Эндпоинт для мониторинга работоспособности сервера"""
    return {
        "status": "online",
        "service": "G-TRASH API",
        "version": "7.0.0-PRO",
        "timestamp": datetime.datetime.utcnow(),
        "database": "CONNECTED" if DATABASE_URL else "DISCONNECTED"
    }

@app.post("/api/register", tags=["Auth"])
def account_registration(user: UserRegisterSchema, db: Session = Depends(get_db)):
    """Регистрация нового эко-активиста в системе"""
    logger.info(f"Попытка регистрации нового пользователя: {user.email}")
    
    db_user = db.query(UserDB).filter(UserDB.email == user.email).first()
    if db_user:
        logger.warning(f"Отказ в регистрации: Email {user.email} уже существует.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким Email уже зарегистрирован в системе G-TRASH."
        )
    
    try:
        new_account = UserDB(
            email=user.email,
            password=user.password, # В реальном проекте используйте bcrypt!
            full_name=user.full_name
        )
        db.add(new_account)
        db.commit()
        db.refresh(new_account)
        return {"status": "success", "id": new_account.id, "message": "Аккаунт создан успешно."}
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при создании аккаунта: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера при регистрации.")

@app.post("/api/login", tags=["Auth"])
def account_login(user: UserAuthSchema, db: Session = Depends(get_db)):
    """Аутентификация пользователя и вход в личный кабинет"""
    logger.info(f"Попытка входа: {user.email}")
    
    db_user = db.query(UserDB).filter(
        UserDB.email == user.email, 
        UserDB.password == user.password
    ).first()
    
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль."
        )
    
    return {
        "id": db_user.id,
        "full_name": db_user.full_name,
        "email": db_user.email,
        "status": "authenticated"
    }

@app.post("/api/orders", tags=["Orders"])
async def submit_waste_order(order: OrderCreateSchema, db: Session = Depends(get_db)):
    """Обработка и сохранение новой заявки на вывоз сырья"""
    logger.info(f"Получена новая заявка от {order.client_name}")
    
    try:
        new_entry = OrderDB(
            client_name=order.client_name,
            waste_type=order.waste_type,
            weight_kg=order.weight_kg,
            user_id=order.user_id
        )
        db.add(new_entry)
        db.commit()
        logger.info(f"Заявка #{new_entry.id} успешно сохранена в PostgreSQL.")
        return {"status": "success", "order_id": new_entry.id}
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка записи заявки в БД: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка базы данных: {str(e)}")

@app.get("/api/my-orders/{user_id}", tags=["Orders"])
def fetch_user_history(user_id: int, db: Session = Depends(get_db)):
    """Получение персональной истории заказов пользователя"""
    history = db.query(OrderDB).filter(OrderDB.user_id == user_id).order_by(desc(OrderDB.order_date)).all()
    return history

@app.get("/api/stats", tags=["Analytics"])
def compute_global_stats(db: Session = Depends(get_db)):
    """Вычисление глобальных экологических показателей системы"""
    all_orders = db.query(OrderDB).all()
    total_weight = sum([o.weight_kg for o in all_orders if o.weight_kg])
    user_count = db.query(UserDB).count()
    
    return {
        "total_kg": round(total_weight, 2),
        "count": len(all_orders),
        "users": user_count,
        "efficiency": "High"
    }

# ==================================================================================================
# ТОЧКА ВХОДА ДЛЯ ЛОКАЛЬНОГО ЗАПУСКА
# ==================================================================================================
if __name__ == "__main__":
    import uvicorn
    # На Render запуск осуществляется через команду Start Command
    uvicorn.run(app, host="0.0.0.0", port=8000)
