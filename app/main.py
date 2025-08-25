from fastapi import FastAPI
from app.routes import data_routes
from app.services.db_service import get_database_schema

app = FastAPI()


app.include_router(data_routes.router)
app.state.db_schema = get_database_schema()


@app.get("/")
def read_root():
    return {"message": "API de BI com IA. Use o endpoint /analyze para começar."}