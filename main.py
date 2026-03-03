import os
import logging
import datetime
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("G-TRASH-DEBUG")

# Получаем ссылку из Environment Variables
DATABASE_URL = os.getenv("DATABASE_URL")

# Проверка наличия ссылки
if not DATABASE_URL:
    logger.error("DATABASE_URL IS MISSING!")

# Создаем движок базы данных
# pool_pre_ping=True помогает избежать ошибок при долгом простое
try:
    engine = create_engine(
        DATABASE_URL, 
        pool_pre_ping=True,
        connect_args={"sslmode": "require"}
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
    logger.info("Database engine created successfully")
except Exception as e:
    logger.error(f"Failed to create engine: {e}")

# Определение модели данных
class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(String)
    waste_type = Column(String)
    weight_kg = Column(Float)
    order_date = Column(DateTime, default=datetime.datetime.utcnow)

# Создаем таблицы (в блоке try, чтобы сервер не упал при ошибке подключения)
try:
    if DATABASE_URL:
        Base.metadata.create_all(bind=engine)
        logger.info("Tables created or already exist")
except Exception as e:
    logger.error(f"Error creating tables: {e}")

# Инициализация FastAPI
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Зависимость для БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def home():
    return {"status": "G-TRASH v16.1 LIVE", "db_configured": bool(DATABASE_URL)}

@app.get("/api/stats/global")
def get_stats(db: Session = Depends(get_db)):
    try:
        orders = db.query(Order).all()
        total_kg = sum([o.weight_kg for o in orders])
        return {"total_kg": round(total_kg, 2), "count": len(orders)}
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return {"total_kg": 0, "count": 0}

@app.post("/api/orders/create")
async def create_order(data: dict, db: Session = Depends(get_db)):
    try:
        new_order = Order(
            client_name=data.get('client_name'),
            waste_type=data.get('waste_type'),
            weight_kg=float(data.get('weight_kg'))
        )
        db.add(new_order)
        db.commit()
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        logger.error(f"Order creation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
