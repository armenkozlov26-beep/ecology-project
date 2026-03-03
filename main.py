import os
import logging
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("G-TRASH-DEBUG")

# ПОЛУЧАЕМ ССЫЛКУ
DATABASE_URL = os.getenv("DATABASE_URL")

# ЛОГИРУЕМ ХОСТ (Чтобы понять, видит ли Render изменения)
if DATABASE_URL:
    host = DATABASE_URL.split("@")[-1]
    logger.info(f"ПОПЫТКА ПОДКЛЮЧЕНИЯ К ХОСТУ: {host}")
else:
    logger.error("DATABASE_URL НЕ НАЙДЕН!")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(String)
    waste_type = Column(String)
    weight_kg = Column(Float)
    order_date = Column(DateTime, default=datetime.datetime.utcnow)

try:
    Base.metadata.create_all(bind=engine)
    logger.info("БАЗА ДАННЫХ: ПОДКЛЮЧЕНО УСПЕШНО!")
except Exception as e:
    logger.error(f"ОШИБКА БАЗЫ: {e}")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

@app.get("/api/stats/global")
def stats(db: Session = Depends(get_db)):
    try:
        orders = db.query(Order).all()
        return {"total_kg": sum([o.weight_kg for o in orders]), "count": len(orders), "users": 1}
    except:
        return {"total_kg": 0, "count": 0, "users": 0}

@app.post("/api/orders/create")
async def create(data: dict, db: Session = Depends(get_db)):
    try:
        new = Order(client_name=data['client_name'], waste_type=data['waste_type'], weight_kg=float(data['weight_kg']))
        db.add(new)
        db.commit()
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        logger.error(f"ЗАПИСЬ НЕ УДАЛАСЬ: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def home(): return {"status": "v16.0 LIVE"}
