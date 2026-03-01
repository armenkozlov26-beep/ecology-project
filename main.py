from fastapi import FastAPI
from pydantic import BaseModel
import psycopg2
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

app = FastAPI()

# Разрешаем сайту (index.html) общаться с сервером
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ССЫЛКА НА ОБЛАЧНУЮ БАЗУ SUPABASE (Пароль обновлен)
DATABASE_URL = "postgresql://postgres:59h+z!geG9-7E_r@db.kylnesalchqnmhqadluh.supabase.co:5432/postgres"

class Order(BaseModel):
    client_name: str
    weight: float

@app.post("/send")
def add_order(order: Order):
    try:
        # Подключение к Supabase
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        # Запись в таблицу, которую ты создал через SQL Editor
        cur.execute(
            "INSERT INTO orders (client_name, weight_kg) VALUES (%s, %s)",
            (order.client_name, order.weight)
        )
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "success", "message": "Заявка сохранена в облаке Supabase!"}
    except Exception as e:
        return {"status": "error", "details": str(e)}

if __name__ == "__main__":
    # Настройка порта для работы на хостинге Render
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)